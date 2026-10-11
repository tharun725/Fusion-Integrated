"""Review and sanction.

EL-UC-003 (Unit Head review), EL-UC-004
(Establishment verify-and-route), EL-UC-005
(final sanctioning decision), and the
Director self-sanction path (BR-EL-020).

On a final decision the employee is notified
and, for an approval, the leave account is
updated (EL-UC-005).
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from modules.elm.domain import state_machine as sm
from modules.elm.models import LeaveApplication
from modules.elm.selectors import scoping
from modules.elm.services import balances as balance_service
from modules.elm.services import config as config_service
from modules.elm.services import notifications

log = logging.getLogger("fusion.elm.decisions")

P_UNIT_HEAD = "elm.review.unit_head"
P_ESTABLISHMENT = "elm.review.establishment"
P_SANCTION = "elm.review.sanction"


def _require_permission(principal, code: str) -> None:
    if not principal.has_permission(code):
        raise PermissionDeniedError(
            "Your role cannot perform this action.",
            code="permission_denied")


def _is_unit_head_of_applicant(principal,
                                  application) -> bool:
    return scoping.is_unit_head_of(
        principal.user_id, application.user_id)


def _resolved_authority_user_id(category: str
                                     ) -> int | None:
    """The user who holds the final authority
    role for a category, if that role maps to a
    single person. Resolution from designation
    and unit is the hierarchy's business; here
    we take the configured authority role and
    look up who currently holds it."""
    role = config_service.final_authority_role(
        category)
    if role is None:
        return None
    from modules.elm.models import EmployeeProfile
    # The final authority is the head of the
    # applicant's unit's chain for the category.
    # A real deployment resolves this against
    # the org hierarchy; here the Unit Head of
    # the top-level unit stands in.
    profile = EmployeeProfile.objects.filter(
        designation__iexact=role).first()
    return profile.user_id if profile else None


@transaction.atomic
def unit_head_review(
        *, principal, application_id: int,
        outcome: str = "",
        recommendation: str = "",
        reason: str = ""
        ) -> LeaveApplication:
    """Record the Unit Head's decision or
    recommendation (EL-UC-003).

    CL/RH: the Unit Head is the final authority
    (BR-EL-016) -- the outcome is final.
    SCL/EL/COL/VL: the Unit Head records
    Recommended / Not Recommended (BR-EL-017);
    neither is a final rejection, and both
    continue through the higher-sanction path.
    """
    application = scoping.application_for(
        principal, application_id)
    if application is None:
        raise NotFoundError("No such leave request.")
    if application.status != sm.AWAITING_UNIT_HEAD:
        raise ConflictError(
            "The request is not awaiting Unit Head "
            "review.", code="not_awaiting_unit_head")
    _require_permission(principal, P_UNIT_HEAD)
    if not _is_unit_head_of_applicant(
            principal, application):
        raise PermissionDeniedError(
            "You are not this applicant's Unit Head.",
            code="not_unit_head")

    category = application.category
    if category in ("CL", "RH"):
        # Unit Head final (BR-EL-016).
        if outcome == "approve":
            return _final_approve(
                principal, application, reason,
                authority="unit_head")
        if outcome == "reject":
            return _final_reject(
                principal, application, reason,
                authority="unit_head")
        raise ConflictError(
            "A CL/RH review must approve or reject.",
            code="invalid_outcome")

    # Higher-sanction: record the recommendation
    # and route onward (BR-EL-017).
    if recommendation not in ("recommended",
                               "not_recommended"):
        raise ConflictError(
            "A higher-sanction review must record "
            "a recommendation.",
            code="recommendation_required")
    application.recommendation = recommendation
    application.decided_by_user_id = principal.user_id
    application.decision_reason = reason[:300]
    application.save(update_fields=[
        "recommendation", "decided_by_user_id",
        "decision_reason", "updated_at"])

    if config_service.has_establishment_step(
            category):
        _goto(application, principal,
                 sm.AWAITING_ESTABLISHMENT,
                 f"Recommended: {recommendation}")
        notifications.notify_assigned(
            user_id=_establishment_user_id(),
            task_class="establishment_routing",
            reference_id=application.pk,
            subject="Leave routed to establishment",
            body="A recommended leave request "
                 "awaits establishment routing.")
    else:
        _goto(application, principal,
                 sm.AWAITING_FINAL,
                 f"Recommended: {recommendation}")
        _notify_authority(application)
    return application


@transaction.atomic
def establishment_route(
        *, principal, application_id: int,
        reason: str = ""
        ) -> LeaveApplication:
    """The Establishment processing step: verify
    the routing context and forward to the
    resolved final authority (EL-UC-004).

    Bypassed entirely when no Establishment step
    is configured (A1 in the specification).
    """
    application = scoping.application_for(
        principal, application_id)
    if application is None:
        raise NotFoundError("No such leave request.")
    if application.status != sm.AWAITING_ESTABLISHMENT:
        raise ConflictError(
            "The request is not awaiting "
            "establishment routing.",
            code="not_awaiting_establishment")
    _require_permission(principal, P_ESTABLISHMENT)
    if not principal.has_permission(
            P_ESTABLISHMENT):
        raise PermissionDeniedError(
            "You do not perform establishment "
            "processing.", code="permission_denied")

    category = application.category
    if not config_service.has_establishment_step(
            category):
        raise ConflictError(
            "No Establishment step is configured "
            "for this category.",
            code="no_establishment_step")

    _goto(application, principal,
             sm.AWAITING_FINAL,
             "Establishment routing verified")
    _notify_authority(application)
    return application


@transaction.atomic
def final_sanction(
        *, principal, application_id: int,
        outcome: str, reason: str = ""
        ) -> LeaveApplication:
    """The final sanctioning decision (EL-UC-005),
    including the Director self-sanction path
    (BR-EL-020).

    Approval notifies the employee and updates
    the leave account; rejection notifies the
    employee and preserves the balance.
    """
    application = scoping.application_for(
        principal, application_id)
    if application is None:
        raise NotFoundError("No such leave request.")
    if application.status not in (
            sm.AWAITING_FINAL,
            sm.AWAITING_DIRECTOR):
        raise ConflictError(
            "The request is not awaiting a final "
            "sanction decision.",
            code="not_awaiting_final")
    _require_permission(principal, P_SANCTION)

    if application.status == sm.AWAITING_DIRECTOR:
        # BR-EL-020: the Director is both
        # applicant and authority here.
        if not _is_director(principal):
            raise PermissionDeniedError(
                "Only the Director self-sanctions "
                "a Director leave request.",
                code="not_director")
    elif not _is_resolved_authority(
            principal, application):
        raise PermissionDeniedError(
            "You are not the resolved sanctioning "
            "authority for this request.",
            code="not_authority")

    if outcome == "approve":
        return _final_approve(
            principal, application, reason,
            authority="sanctioning_authority")
    if outcome == "reject":
        return _final_reject(
            principal, application, reason,
            authority="sanctioning_authority")
    raise ConflictError(
        "The decision must approve or reject.",
        code="invalid_outcome")


def _is_director(principal) -> bool:
    return "director" in (principal.roles or ())


def _is_resolved_authority(principal,
                                application) -> bool:
    """Whether the caller is the resolved final
    authority for this request.

    Resolution is by role: the caller holds the
    sanction permission and is the person the
    hierarchy resolves for the category. Where a
    deployment maps roles to named people, that
    mapping is consulted; here the module-wide
    sanction permission plus the hierarchy's
    final role is the authority.
    """
    resolved = _resolved_authority_user_id(
        application.category)
    if resolved is not None:
        return principal.user_id == resolved
    # No single person resolved: the sanction
    # permission is the authority's warrant.
    return principal.has_permission(P_SANCTION)


def _establishment_user_id() -> int | None:
    from modules.elm.models import EmployeeProfile
    profile = EmployeeProfile.objects.filter(
        designation__iexact="establishment").first()
    return profile.user_id if profile else None


def _goto(application, actor, to: str,
             reason: str) -> None:
    """Move to ``to``, recording the audit
    row from the state the machine left."""
    frm = application.status
    application.status = to
    application.save(update_fields=[
        "status", "updated_at"])
    from modules.elm.models import LeaveApplicationTransition
    LeaveApplicationTransition.objects.create(
        application=application,
        from_status=frm, to_status=to,
        actor_user_id=getattr(actor, "user_id", None),
        actor_label="staff", reason=reason)


def _final_approve(actor, application, reason: str,
                      authority: str
                      ) -> LeaveApplication:
    """Approve: record the decision, deduct the
    balance, notify the employee."""
    from modules.elm.models import EmployeeProfile
    profile = EmployeeProfile.objects.filter(
        user_id=application.user_id).first()
    is_faculty = (profile.category == "faculty"
                  if profile else False)
    balance = balance_service.get_or_create_balance(
        user_id=application.user_id,
        category=application.category,
        leave_year=application.leave_year,
        is_faculty=is_faculty)
    balance_service.deduct(
        balance=balance,
        days=application.days_requested,
        application_id=application.pk,
        note=f"Approved by {authority}")

    frm = application.status
    application.status = sm.APPROVED
    application.decided_by_user_id = (
        getattr(actor, "user_id", None))
    application.decided_at = timezone.now()
    application.decision_reason = reason[:300]
    application.save(update_fields=[
        "status", "decided_by_user_id",
        "decided_at", "decision_reason",
        "updated_at"])
    _write_transition(application, frm,
                         sm.APPROVED, actor,
                         reason)
    notifications.notify_decision(
        user_id=application.user_id,
        application_id=application.pk,
        decision="approved",
        category=application.category,
        reason=reason)
    return application


def _final_reject(actor, application, reason: str,
                     authority: str
                     ) -> LeaveApplication:
    frm = application.status
    application.status = sm.REJECTED
    application.decided_by_user_id = (
        getattr(actor, "user_id", None))
    application.decided_at = timezone.now()
    application.decision_reason = reason[:300]
    application.save(update_fields=[
        "status", "decided_by_user_id",
        "decided_at", "decision_reason",
        "updated_at"])
    _write_transition(application, frm,
                         sm.REJECTED, actor,
                         reason)
    notifications.notify_decision(
        user_id=application.user_id,
        application_id=application.pk,
        decision="rejected",
        category=application.category,
        reason=reason)
    return application


def _write_transition(application, frm: str,
                         to_status: str,
                         actor, reason: str
                         ) -> None:
    from modules.elm.models import LeaveApplicationTransition
    LeaveApplicationTransition.objects.create(
        application=application,
        from_status=frm, to_status=to_status,
        actor_user_id=getattr(actor, "user_id", None),
        actor_label="staff", reason=reason)


def _notify_authority(application) -> None:
    """Tell the resolved final authority a
    decision is waiting."""
    authority = _resolved_authority_user_id(
        application.category)
    if authority is None:
        return
    notifications.notify_assigned(
        user_id=authority,
        task_class="final_sanction",
        reference_id=application.pk,
        subject="Leave awaiting sanction",
        body="A leave request awaits your "
             "final decision.")
