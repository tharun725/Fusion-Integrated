"""Resumption of duty after EL/COL/VL
(EL-UC-010, EL-UC-011).

The employee submits the actual resumption
date; the applicable Sanctioning Authority
reviews it. A normal return changes nothing.
An early or late return records the actual
period, adjusts the balance and
synchronises leave/attendance records
(BR-EL-028).
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from modules.elm.domain import entitlements as ent
from modules.elm.domain import state_machine as sm
from modules.elm.models import (
    EmployeeProfile,
    ResumptionRecord,
)
from modules.elm.selectors import scoping
from modules.elm.services import balances as balance_service
from modules.elm.services import decisions as decision_service
from modules.elm.services import notifications

P_RESUME = "elm.resumption.submit"


@transaction.atomic
def submit_resumption(
        *, principal, leave_id: int,
        actual_resumption_date,
        details: str = ""
        ) -> ResumptionRecord:
    """Declare actual return to duty
    (EL-UC-010).

    Formal resumption review applies to
    EL/COL/VL only (BR-EL-027).
    """
    leave = scoping.application_for(
        principal, leave_id)
    if leave is None:
        raise NotFoundError("No such leave.")
    if leave.user_id != principal.user_id:
        raise PermissionDeniedError(
            "Only the applicant may submit "
            "a resumption.", code="permission_denied")
    if not principal.has_permission(P_RESUME):
        raise PermissionDeniedError(
            "You may not submit a resumption.",
            code="permission_denied")
    if leave.category not in ent.RESUMABLE:
        raise ConflictError(
            "Resumption applies to EL/COL/VL "
            "only.", code="not_resumable")
    if leave.status not in (sm.APPROVED,
                               sm.ONGOING):
        raise ConflictError(
            "The leave is not approved or "
            "ongoing.", code="not_approved")
    if actual_resumption_date < leave.start_date:
        raise ConflictError(
            "Resumption precedes the leave "
            "start.", code="invalid_resumption")

    record = ResumptionRecord.objects.create(
        leave=leave, user_id=principal.user_id,
        actual_resumption_date=(
            actual_resumption_date),
        details=details,
        status=sm.RESUMPTION_PENDING)
    _notify_authority(record)
    return record


@transaction.atomic
def review_resumption(
        *, principal, resumption_id: int,
        outcome: str, note: str = ""
        ) -> ResumptionRecord:
    """Review a submitted resumption
    (EL-UC-011).

    On the approved end date: no adjustment.
    Earlier or later: after review, the
    actual period is recorded, the balance
    adjusted, and leave/attendance
    records synchronised.
    """
    record = _get(resumption_id)
    if record.status != sm.RESUMPTION_PENDING:
        raise ConflictError(
            "The resumption is not awaiting "
            "review.", code="not_pending")
    decision_service._require_permission(
        principal, decision_service.P_SANCTION)

    leave = record.leave
    approved_end = leave.end_date
    actual = record.actual_resumption_date

    if actual == approved_end:
        # Normal return: nothing changes.
        return _finalize(
            record, principal,
            sm.RESUMPTION_NO_ADJUSTMENT,
            "Resumption on the approved end "
            "date", note)

    if actual < approved_end:
        # Early return: restore the unused
        # portion, after review.
        unused = (approved_end - actual).days
        _restore(leave, unused, record)
        return _finalize(
            record, principal,
            sm.RESUMPTION_ADJUSTED,
            f"Early resumption: {unused} day(s) "
            f"restored", note)

    # Late return: the extra days are
    # debited, after review.
    extra = (actual - approved_end).days
    _debit(leave, extra, record)
    return _finalize(
        record, principal,
        sm.RESUMPTION_ADJUSTED,
        f"Late resumption: {extra} day(s) "
        f"deducted", note)


def _get(resumption_id: int) -> ResumptionRecord:
    record = (ResumptionRecord.objects
              .select_for_update()
              .select_related("leave")
              .filter(pk=resumption_id)
              .first())
    if record is None:
        raise NotFoundError(
            "No such resumption record.")
    return record


def _restore(leave, days: int,
                  record) -> None:
    """Restore the unused portion of an
    early return, and shorten the recorded
    period to the actual return."""
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
        balance=balance, days=float(days),
        application_id=leave.pk,
        note=f"Early resumption "
             f"#{record.pk}")
    # Record the actual, shorter period.
    leave.end_date = record.actual_resumption_date
    leave.save(update_fields=[
        "end_date", "updated_at"])


def _debit(leave, days: int,
                record) -> None:
    """Debit the extra days of a late
    return, and lengthen the recorded
    period to the actual return."""
    profile = EmployeeProfile.objects.filter(
        user_id=leave.user_id).first()
    is_faculty = (profile.category == "faculty"
                  if profile else False)
    balance = balance_service.get_or_create_balance(
        user_id=leave.user_id,
        category=leave.category,
        leave_year=leave.leave_year,
        is_faculty=is_faculty)
    balance_service.deduct(
        balance=balance, days=float(days),
        application_id=leave.pk,
        note=f"Late resumption "
             f"#{record.pk}")
    leave.end_date = record.actual_resumption_date
    leave.save(update_fields=[
        "end_date", "updated_at"])


def _finalize(record, principal, to: str,
                   summary: str,
                   note: str) -> ResumptionRecord:
    frm = record.status
    record.status = to
    record.reviewed_by_user_id = (
        getattr(principal, "user_id", None))
    record.reviewed_at = timezone.now()
    record.review_note = (note or summary)[:300]
    record.save(update_fields=[
        "status", "reviewed_by_user_id",
        "reviewed_at", "review_note",
        "updated_at"])
    from modules.elm.models import LeaveApplicationTransition
    LeaveApplicationTransition.objects.create(
        application=record.leave,
        from_status=frm, to_status=to,
        actor_user_id=getattr(principal, "user_id", None),
        actor_label="staff",
        reason=summary)
    notifications.notify_decision(
        user_id=record.user_id,
        application_id=record.leave.pk,
        decision="resumption reviewed",
        category=record.leave.category,
        reason=summary)
    return record


def _notify_authority(record) -> None:
    from modules.elm.models import EmployeeProfile
    from modules.elm.services import config as config_service
    authority = config_service.final_authority_role(
        record.leave.category)
    profile = EmployeeProfile.objects.filter(
        designation__iexact=authority).first()
    if profile is None:
        return
    notifications.notify_assigned(
        user_id=profile.user_id,
        task_class="resumption_review",
        reference_id=record.pk,
        subject="Resumption awaiting review",
        body="A resumption of duty awaits "
             "your review.")
