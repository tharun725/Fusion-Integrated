"""Cancellation of approved leave before it
starts (EL-UC-008).

Cancellation follows the same applicable
hierarchy as the original leave and never
edits the approved leave in place
(BR-EL-023). Approval marks the leave
Cancelled and restores the deducted
balance; rejection leaves it unchanged.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from modules.elm.domain import state_machine as sm
from modules.elm.models import (
    LeaveCancellation,
)
from modules.elm.selectors import scoping
from modules.elm.services import balances as balance_service
from modules.elm.services import config as config_service
from modules.elm.services import decisions as decision_service
from modules.elm.services import notifications

P_CANCEL = "elm.application.cancel_request"


@transaction.atomic
def request_cancellation(
        *, principal, leave_id: int,
        reason: str = ""
        ) -> LeaveCancellation:
    """Request pre-start cancellation of an
    approved leave (EL-UC-008).

    The leave must be approved and must not
    have started. The approved leave itself
    is left untouched until the cancellation
    is finally decided.
    """
    application = scoping.application_for(
        principal, leave_id)
    if application is None:
        raise NotFoundError("No such leave.")
    if application.user_id != principal.user_id:
        raise PermissionDeniedError(
            "Only the applicant may request "
            "cancellation.", code="permission_denied")
    if application.status not in (sm.APPROVED,
                                     sm.ONGOING):
        raise ConflictError(
            "Only an approved leave may be "
            "cancelled.", code="not_approved")
    if application.start_date <= timezone.now(
            ).date():
        raise ConflictError(
            "The leave has already started; "
            "pre-start cancellation no longer "
            "applies.", code="already_started")

    cancellation = LeaveCancellation.objects.create(
        leave=application,
        user_id=principal.user_id,
        reason=reason,
        status=sm.CANCEL_PENDING_UH)

    # Route through the applicable hierarchy.
    category = application.category
    if category in ("CL", "RH"):
        _goto(cancellation, principal,
                 sm.CANCEL_PENDING_UH,
                 "Cancellation awaiting Unit Head")
        _notify_unit_head(cancellation)
    elif config_service.has_establishment_step(
            category):
        _goto(cancellation, principal,
                 sm.CANCEL_PENDING_UH,
                 "Cancellation awaiting Unit Head "
                 "recommendation")
        _notify_unit_head(cancellation)
    else:
        _goto(cancellation, principal,
                 sm.CANCEL_PENDING_FINAL,
                 "Cancellation awaiting final "
                 "decision")
        _notify_authority(cancellation)
    return cancellation


@transaction.atomic
def unit_head_cancellation(
        *, principal, cancellation_id: int,
        outcome: str = "", recommendation: str = "",
        reason: str = ""
        ) -> LeaveCancellation:
    """The Unit Head's cancellation decision
    or recommendation (EL-UC-003 for
    cancellations).

    CL/RH: final. Higher-sanction: a
    recommendation that routes onward.
    """
    cancellation = _get(cancellation_id)
    if cancellation.status != sm.CANCEL_PENDING_UH:
        raise ConflictError(
            "The cancellation is not awaiting "
            "Unit Head review.",
            code="not_awaiting_unit_head")
    decision_service._require_permission(
        principal,
        decision_service.P_UNIT_HEAD)
    if not scoping.is_unit_head_of(
            principal.user_id, cancellation.user_id):
        raise PermissionDeniedError(
            "You are not this applicant's "
            "Unit Head.", code="not_unit_head")

    category = cancellation.leave.category
    if category in ("CL", "RH"):
        if outcome == "approve":
            return _approve(
                cancellation, principal, reason)
        if outcome == "reject":
            return _reject(
                cancellation, principal, reason)
        raise ConflictError(
            "The decision must approve or "
            "reject.", code="invalid_outcome")

    if recommendation not in ("recommended",
                               "not_recommended"):
        raise ConflictError(
            "A recommendation is required.",
            code="recommendation_required")
    if config_service.has_establishment_step(
            category):
        _goto(cancellation, principal,
                 sm.CANCEL_PENDING_EST,
                 f"Recommended: {recommendation}")
    else:
        _goto(cancellation, principal,
                 sm.CANCEL_PENDING_FINAL,
                 f"Recommended: {recommendation}")
        _notify_authority(cancellation)
    return cancellation


@transaction.atomic
def establishment_cancellation(
        *, principal, cancellation_id: int,
        reason: str = ""
        ) -> LeaveCancellation:
    """The Establishment routing step for a
    cancellation, where configured."""
    cancellation = _get(cancellation_id)
    if cancellation.status != sm.CANCEL_PENDING_EST:
        raise ConflictError(
            "The cancellation is not awaiting "
            "establishment routing.",
            code="not_awaiting_establishment")
    decision_service._require_permission(
        principal,
        decision_service.P_ESTABLISHMENT)
    _goto(cancellation, principal,
             sm.CANCEL_PENDING_FINAL,
             "Establishment routing verified")
    _notify_authority(cancellation)
    return cancellation


@transaction.atomic
def final_cancellation(
        *, principal, cancellation_id: int,
        outcome: str, reason: str = ""
        ) -> LeaveCancellation:
    """The final cancellation decision
    (EL-UC-005 for cancellations)."""
    cancellation = _get(cancellation_id)
    if cancellation.status != sm.CANCEL_PENDING_FINAL:
        raise ConflictError(
            "The cancellation is not awaiting "
            "a final decision.",
            code="not_awaiting_final")
    decision_service._require_permission(
        principal, decision_service.P_SANCTION)
    if outcome == "approve":
        return _approve(cancellation, principal,
                           reason)
    if outcome == "reject":
        return _reject(cancellation, principal,
                          reason)
    raise ConflictError(
        "The decision must approve or reject.",
        code="invalid_outcome")


def cancellation_review(
        *, principal, cancellation_id: int,
        outcome: str = "",
        recommendation: str = "",
        reason: str = ""
        ) -> LeaveCancellation:
    """Dispatch a cancellation decision
    to the handler for the stage it has
    reached (EL-UC-003/004/005 for
    cancellations)."""
    cancellation = (LeaveCancellation.objects
                    .filter(pk=cancellation_id)
                    .first())
    if cancellation is None:
        raise NotFoundError(
            "No such cancellation request.")
    status = cancellation.status
    if status == sm.CANCEL_PENDING_UH:
        return unit_head_cancellation(
            principal=principal,
            cancellation_id=cancellation_id,
            outcome=outcome,
            recommendation=recommendation,
            reason=reason)
    if status == sm.CANCEL_PENDING_EST:
        return establishment_cancellation(
            principal=principal,
            cancellation_id=cancellation_id,
            reason=reason)
    if status == sm.CANCEL_PENDING_FINAL:
        return final_cancellation(
            principal=principal,
            cancellation_id=cancellation_id,
            outcome=outcome,
            reason=reason)
    raise ConflictError(
        "The cancellation is already "
        "decided.", code="already_decided")


def _goto(cancellation, actor, to: str,
             reason: str) -> None:
    """Move a cancellation and record it on
    the parent leave's audit trail."""
    frm = cancellation.status
    cancellation.status = to
    cancellation.save(update_fields=[
        "status", "updated_at"])
    _write(cancellation, frm, to, actor,
           reason)


def _get(cancellation_id: int
              ) -> LeaveCancellation:
    cancellation = (LeaveCancellation.objects
                    .select_for_update()
                    .select_related("leave")
                    .filter(pk=cancellation_id)
                    .first())
    if cancellation is None:
        raise NotFoundError(
            "No such cancellation request.")
    return cancellation


def _approve(cancellation, actor,
                  reason: str) -> LeaveCancellation:
    """Approve the cancellation: mark the
    leave Cancelled and restore the deducted
    balance."""
    leave = cancellation.leave
    frm = cancellation.status
    cancellation.status = sm.CANCEL_APPROVED
    cancellation.decided_by_user_id = (
        getattr(actor, "user_id", None))
    cancellation.decided_at = timezone.now()
    cancellation.decision_reason = reason[:300]
    cancellation.save(update_fields=[
        "status", "decided_by_user_id",
        "decided_at", "decision_reason",
        "updated_at"])
    _write(cancellation, frm,
              sm.CANCEL_APPROVED, actor, reason)

    # Mark the leave cancelled and restore
    # what its approval deducted.
    _mark_leave_cancelled(leave, actor)
    _restore_balance(leave)
    notifications.notify_decision(
        user_id=leave.user_id,
        application_id=leave.pk,
        decision="cancelled",
        category=leave.category, reason=reason)
    return cancellation


def _reject(cancellation, actor,
                 reason: str) -> LeaveCancellation:
    frm = cancellation.status
    cancellation.status = sm.CANCEL_REJECTED
    cancellation.decided_by_user_id = (
        getattr(actor, "user_id", None))
    cancellation.decided_at = timezone.now()
    cancellation.decision_reason = reason[:300]
    cancellation.save(update_fields=[
        "status", "decided_by_user_id",
        "decided_at", "decision_reason",
        "updated_at"])
    _write(cancellation, frm,
              sm.CANCEL_REJECTED, actor, reason)
    notifications.notify_decision(
        user_id=cancellation.leave.user_id,
        application_id=cancellation.leave.pk,
        decision="cancellation rejected",
        category=cancellation.leave.category,
        reason=reason)
    return cancellation


def _mark_leave_cancelled(leave, actor
                               ) -> None:
    from modules.elm.models import LeaveApplicationTransition
    frm = leave.status
    leave.status = sm.CANCELLED
    leave.save(update_fields=[
        "status", "updated_at"])
    LeaveApplicationTransition.objects.create(
        application=leave, from_status=frm,
        to_status=sm.CANCELLED,
        actor_user_id=getattr(actor, "user_id", None),
        actor_label="staff",
        reason="Cancellation approved")


def _restore_balance(leave) -> None:
    from modules.elm.models import EmployeeProfile
    profile = EmployeeProfile.objects.filter(
        user_id=leave.user_id).first()
    is_faculty = (profile.category == "faculty"
                  if profile else False)
    balance = balance_service.get_or_create_balance(
        user_id=leave.user_id,
        category=leave.category,
        leave_year=leave.leave_year,
        is_faculty=is_faculty)
    balance_service.restore(
        balance=balance,
        days=leave.days_requested,
        application_id=leave.pk,
        note="Cancellation approved")


def _write(cancellation, frm: str, to: str,
              actor, reason: str) -> None:
    # A cancellation's history is written to
    # the parent leave's audit trail -- the
    # cancellation is a request about that
    # leave, and the leave's trail is the
    # record of everything that touched it.
    from modules.elm.models import LeaveApplicationTransition
    LeaveApplicationTransition.objects.create(
        application=cancellation.leave,
        from_status=frm, to_status=to,
        actor_user_id=getattr(actor, "user_id", None),
        actor_label="staff",
        reason=f"cancellation: {reason}")


def _notify_unit_head(cancellation) -> None:
    unit_head = scoping.unit_head_for(
        cancellation.user_id)
    if unit_head is None:
        return
    notifications.notify_assigned(
        user_id=unit_head,
        task_class="unit_head_review",
        reference_id=cancellation.pk,
        subject="Cancellation awaiting review",
        body="A leave cancellation awaits "
             "your review.")


def _notify_authority(cancellation) -> None:
    authority = config_service.final_authority_role(
        cancellation.leave.category)
    from modules.elm.models import EmployeeProfile
    profile = EmployeeProfile.objects.filter(
        designation__iexact=authority).first()
    if profile is None:
        return
    notifications.notify_assigned(
        user_id=profile.user_id,
        task_class="final_sanction",
        reference_id=cancellation.pk,
        subject="Cancellation awaiting decision",
        body="A leave cancellation awaits "
             "your final decision.")
