"""Submitting, withdrawing and staffing a
leave request.

EL-UC-001 (apply), EL-UC-002 (substitute
response), EL-UC-007 (withdraw), EL-UC-019
(replacement substitute). The service composes
the pure-Python validators, enforces the
state machine, and posts the ledger entry on
approval.
"""
from __future__ import annotations

import logging
from datetime import date

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from modules.elm.domain import entitlements as ent
from modules.elm.domain import state_machine as sm
from modules.elm.domain import validation as rules
from modules.elm.models import (
    LeaveApplication,
    LeaveApplicationTransition,
    SubstituteAssignment,
)
from modules.elm.selectors import scoping
from modules.elm.services import balances as balance_service
from modules.elm.services import calendar as calendar_service
from modules.elm.services import notifications

log = logging.getLogger("fusion.elm.applications")

P_APPLY = "elm.application.create"
P_WITHDRAW = "elm.application.withdraw"


def _actor_kind(principal) -> str:
    return sm.EMPLOYEE


def _transition(application, *, to: str, actor,
                   reason: str = "",
                   actor_kind: str | None = None) -> None:
    """Move one application, enforcing the
    state machine and recording the audit
    row. `resolve_transition` raises if the
    move is illegal, so an illegal state
    change cannot be saved."""
    kind = actor_kind or _actor_kind(actor)
    sm.resolve_transition(
        "leave", application.status, to,
        kind)
    frm = application.status
    application.status = to
    touched = ["status", "updated_at"]
    application.save(update_fields=touched)
    LeaveApplicationTransition.objects.create(
        application=application,
        from_status=frm, to_status=to,
        actor_user_id=getattr(actor, "user_id", None),
        actor_label=kind,
        reason=reason)


def _active_intervals(user_id: int
                         ) -> list[tuple[date, date, str]]:
    """The employee's active pending or approved
    leave. ``half_day`` is carried for the CL
    half-day overlap exception (BR-EL-012)."""
    statuses = [
        *sm.PENDING_STATES,
        sm.APPROVED, sm.ONGOING]
    rows = (LeaveApplication.objects
            .filter(user_id=user_id,
                    status__in=statuses)
            .values_list("start_date", "end_date",
                         "half_day"))
    return [(r[0], r[1], r[2] or "") for r in rows]


def validate_submission(
        *, principal, category: str,
        start_date: date, end_date: date,
        half_day: str = "",
        leave_year: str = "",
        substitute_required: bool = False,
        substitute_user_id: int | None = None,
        ) -> dict:
    """Every gate a new request must pass
    (BR-EL-001..014), as one verdict.

    Raises ``ConflictError`` naming the failed
    condition, so the caller relays exactly
    what to fix.
    """
    if not rules.is_supported_category(category):
        raise ConflictError(
            f"{category!r} is not a supported "
            f"leave category.",
            code="unsupported_category")

    profile = scoping.employee_profile(
        principal.user_id)
    if profile is None:
        raise ConflictError(
            "You are not registered as an ELM "
            "employee.", code="not_an_employee")
    is_faculty = profile.category == "faculty"

    if end_date < start_date:
        raise ConflictError(
            "The leave end precedes its start.",
            code="invalid_period")

    year = leave_year or str(start_date.year)
    closed = calendar_service.closed_holidays(year)
    days = ent.count_leave_days(
        category, start_date, end_date,
        closed_holidays=closed,
        half_day=half_day)

    # Category-specific calendar applicability.
    if category == ent.RH:
        rh = calendar_service.restricted_holidays(year)
        missing = rules.rh_dates_are_applicable(
            start_date, end_date,
            restricted_holidays=rh)
        if missing:
            raise ConflictError(
                "RH may only be availed on a "
                "Restricted Holiday: "
                + ", ".join(str(d) for d in missing),
                code="rh_not_applicable",
                details=[{"dates": [str(d)
                                    for d in missing]}])

    if category == ent.VL:
        from modules.elm.models import VacationPeriod
        periods = list(
            VacationPeriod.objects
            .values_list("start_date", "end_date"))
        if not rules.period_within_vacation(
                start_date, end_date,
                vacation_periods=periods):
            raise ConflictError(
                "VL may be availed only during a "
                "published vacation period.",
                code="vl_not_in_vacation")

    # Balance / entitlement.
    balance = balance_service.get_or_create_balance(
        user_id=principal.user_id, category=category,
        leave_year=year, is_faculty=is_faculty)
    if days > balance_service.available(balance) + 1e-9:
        raise ConflictError(
            f"Only {balance_service.available(balance)} "
            f"{category} day(s) available.",
            code="insufficient_balance",
            details=[{"available":
                      balance_service.available(balance),
                      "requested": days}])

    # Overlap.
    clash = rules.find_overlap(
        start_date, end_date, half_day=half_day,
        existing=_active_intervals(principal.user_id))
    if clash:
        raise ConflictError(
            "The requested period overlaps an "
            "existing pending or approved leave.",
            code="leave_overlap",
            details=[{"overlaps": [str(clash[0]),
                                   str(clash[1])]}])

    # Substitute.
    if substitute_required:
        if substitute_user_id is None:
            raise ConflictError(
                "A substitute must be nominated.",
                code="substitute_required")
        sub_profile = scoping.employee_profile(
            substitute_user_id)
        sub_leave = [(s, e) for s, e, _ in _active_intervals(
            substitute_user_id)]
        if not rules.substitute_is_eligible(
                applicant_user_id=principal.user_id,
                substitute_user_id=substitute_user_id,
                is_employee=sub_profile is not None,
                responsibility_start=start_date,
                responsibility_end=end_date,
                substitute_leave=sub_leave):
            raise ConflictError(
                "The nominated substitute is not "
                "eligible for the responsibility "
                "period.",
                code="substitute_ineligible")

    return {"days": days, "leave_year": year,
            "is_faculty": is_faculty,
            "profile": profile}


@transaction.atomic
def submit(*, principal, category: str,
              start_date: date, end_date: date,
              half_day: str = "",
              purpose: str = "",
              station_leave: bool = False,
              station_leave_details: str = "",
              substitute_required: bool = False,
              substitute_user_id: int | None = None,
              ) -> LeaveApplication:
    """Create and route a new leave application
    (EL-UC-001).

    Validation happens first; a request that
    fails any gate never becomes a row. The
    opening state depends on whether a
    substitute is required and whether the
    Director is the applicant (BR-EL-020).
    """
    if not principal.has_permission(P_APPLY):
        raise PermissionDeniedError(
            "You may not apply for leave.",
            code="permission_denied")

    verdict = validate_submission(
        principal=principal, category=category,
        start_date=start_date, end_date=end_date,
        half_day=half_day,
        substitute_required=substitute_required,
        substitute_user_id=substitute_user_id)

    profile = verdict["profile"]
    application = LeaveApplication.objects.create(
        user_id=principal.user_id,
        category=category,
        start_date=start_date, end_date=end_date,
        half_day=half_day, purpose=purpose,
        leave_year=verdict["leave_year"],
        applicant_unit=profile.unit,
        applicant_designation=profile.designation,
        applicant_kind=profile.category,
        station_leave=station_leave,
        station_leave_details=station_leave_details,
        substitute_required=substitute_required,
        days_requested=verdict["days"],
        status=sm.DRAFT)

    # Open the correct gate (BW-EL-01..09).
    director = _is_director(principal)
    if substitute_required:
        _transition(
            application,
            to=sm.AWAITING_SUBSTITUTE, actor=principal,
            reason="Substitute consent required")
        SubstituteAssignment.objects.create(
            kind="leave", application=application,
            applicant_user_id=principal.user_id,
            substitute_user_id=substitute_user_id,
            responsibility_start=start_date,
            responsibility_end=end_date)
        notifications.notify_assigned(
            user_id=substitute_user_id,
            task_class="substitute_response",
            reference_id=application.pk,
            subject="Substitute requested",
            body=(f"{principal.display_name} "
                  f"nominated you as substitute for "
                  f"a {category} leave."))
    elif director:
        _transition(
            application,
            to=sm.AWAITING_DIRECTOR, actor=principal,
            reason="Director self-sanction path")
    else:
        _transition(
            application,
            to=sm.AWAITING_UNIT_HEAD, actor=principal,
            reason="Submitted for Unit Head review")
        unit_head = scoping.unit_head_for(
            principal.user_id)
        if unit_head is not None:
            notifications.notify_assigned(
                user_id=unit_head,
                task_class="unit_head_review",
                reference_id=application.pk,
                subject="Leave awaiting your review",
                body=(f"A {category} leave request "
                      f"from {principal.display_name} "
                      f"awaits your review."))
    return application


def _is_director(principal) -> bool:
    """BR-EL-020: the Director's own leave follows
    the self-sanction path."""
    return "director" in (principal.roles or ())


@transaction.atomic
def withdraw(*, principal, application_id: int,
                reason: str = "") -> LeaveApplication:
    """Withdraw a pending request immediately
    (EL-UC-007, BR-EL-022).

    Termination is immediate and total: every
    remaining approval step ends, and later
    approve/reject actions are prevented.
    """
    application = scoping.application_for(
        principal, application_id)
    if application is None:
        raise NotFoundError("No such leave request.")
    if application.user_id != principal.user_id:
        raise PermissionDeniedError(
            "Only the applicant may withdraw.",
            code="permission_denied")
    if application.status not in sm.PENDING_STATES:
        raise ConflictError(
            "Only a pending request may be "
            "withdrawn; after a final decision "
            "cancellation applies instead.",
            code="not_pending")

    _transition(application, to=sm.WITHDRAWN,
                   actor=principal, reason=reason)
    application.withdrawn_reason = reason[:300]
    application.save(update_fields=[
        "withdrawn_reason", "updated_at"])

    # Inform the roles already in the loop.
    concerned = _concerned_roles(application)
    notifications.notify_withdrawal(
        user_ids=concerned,
        application_id=application.pk,
        category=application.category)
    return application


def _concerned_roles(application
                          ) -> list[int]:
    """The people a withdrawal must inform: the
    Unit Head and any assigned authority."""
    ids: list[int] = []
    unit_head = scoping.unit_head_for(
        application.user_id)
    if unit_head is not None:
        ids.append(unit_head)
    if application.decided_by_user_id:
        ids.append(application.decided_by_user_id)
    return ids


@transaction.atomic
def respond_to_substitute(
        *, principal, assignment_id: int,
        accept: bool,
        decline_reason: str = ""
        ) -> SubstituteAssignment:
    """Accept or decline a responsibility
    assignment (EL-UC-002).

    Accepting releases the consent gate so the
    request proceeds; declining leaves it closed
    and puts the request in Applicant Action
    Required (BR-EL-015).
    """
    assignment = (SubstituteAssignment.objects
                  .select_for_update()
                  .filter(pk=assignment_id,
                          substitute_user_id=principal.user_id)
                  .first())
    if assignment is None:
        raise NotFoundError(
            "No such substitute assignment.")
    if assignment.response != "pending":
        raise ConflictError(
            "This assignment has already been "
            "answered.", code="stale_response")

    application = assignment.application
    if application is None or (
            application.status
            not in (sm.AWAITING_SUBSTITUTE,)):
        raise ConflictError(
            "The request is no longer awaiting a "
            "substitute response.",
            code="not_awaiting_substitute")

    assignment.response = (
        "accepted" if accept else "declined")
    assignment.responded_at = timezone.now()
    assignment.decline_reason = decline_reason[:300]
    assignment.save(update_fields=[
        "response", "responded_at",
        "decline_reason", "updated_at"])

    director = _is_director(
        _principal_for(application.user_id))
    if accept:
        to = (sm.AWAITING_DIRECTOR if director
              else sm.AWAITING_UNIT_HEAD)
        _transition(
            application, to=to, actor=principal,
            actor_kind=sm.SUBSTITUTE,
            reason=("Substitute accepted"
                    + ("; Director self-sanction"
                       if director else "")))
        notifications.notify_assigned(
            user_id=application.user_id,
            task_class="substitute_response",
            reference_id=application.pk,
            subject="Substitute accepted",
            body="Your nominated substitute "
                 "accepted the assignment.")
    else:
        _transition(
            application,
            to=sm.APPLICANT_ACTION, actor=principal,
            actor_kind=sm.SUBSTITUTE,
            reason="Substitute declined")
        notifications.notify(
            user_id=application.user_id,
            topic="substitute.declined",
            subject="Substitute declined",
            body=("Your nominated substitute "
                  "declined. Nominate a replacement "
                  "or withdraw the request."),
            reference_kind="leave",
            reference_id=application.pk)
    return assignment


def _principal_for(user_id: int):
    """A stand-in principal for the applicant,
    used only to read role flags."""
    from fusion_auth.principal import Principal
    return Principal(
        user_id=user_id, username="",
        display_name="", kind="",
        active_role=None, roles=(),
        permissions=frozenset(), modules=())


@transaction.atomic
def nominate_replacement(
        *, principal, application_id: int,
        substitute_user_id: int
        ) -> SubstituteAssignment:
    """Nominate a replacement after a decline
    (EL-UC-019)."""
    application = scoping.application_for(
        principal, application_id)
    if application is None:
        raise NotFoundError("No such leave request.")
    if application.user_id != principal.user_id:
        raise PermissionDeniedError(
            "Only the applicant may nominate.",
            code="permission_denied")
    if application.status != sm.APPLICANT_ACTION:
        raise ConflictError(
            "A replacement may be nominated only "
            "after a substitute declines.",
            code="not_action_required")

    # Re-validate the replacement's eligibility.
    sub_profile = scoping.employee_profile(
        substitute_user_id)
    sub_leave = [(s, e) for s, e, _ in _active_intervals(
        substitute_user_id)]
    if not rules.substitute_is_eligible(
            applicant_user_id=principal.user_id,
            substitute_user_id=substitute_user_id,
            is_employee=sub_profile is not None,
            responsibility_start=application.start_date,
            responsibility_end=application.end_date,
            substitute_leave=sub_leave):
        raise ConflictError(
            "The replacement substitute is not "
            "eligible.", code="substitute_ineligible")

    assignment = SubstituteAssignment.objects.create(
        kind="leave", application=application,
        applicant_user_id=principal.user_id,
        substitute_user_id=substitute_user_id,
        responsibility_start=application.start_date,
        responsibility_end=application.end_date)
    _transition(
        application,
        to=sm.AWAITING_SUBSTITUTE, actor=principal,
        reason="Replacement substitute nominated")
    notifications.notify_assigned(
        user_id=substitute_user_id,
        task_class="substitute_response",
        reference_id=application.pk,
        subject="Substitute requested",
        body=(f"{principal.display_name} "
              f"nominated you as substitute."))
    return assignment
