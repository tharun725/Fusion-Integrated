"""Extension of ongoing EL/COL/VL (EL-UC-009).

Extension is available only for ongoing
EL/COL/VL. It uses the applicable
eligibility, balance, substitute, calendar
and sanction rules. Approval posts only
the incremental additional period;
rejection preserves the original approved
leave (BR-EL-025).
"""
from __future__ import annotations

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
from modules.elm.models import (
    EmployeeProfile,
    LeaveExtension,
    SubstituteAssignment,
)
from modules.elm.selectors import scoping
from modules.elm.services import applications as application_service
from modules.elm.services import balances as balance_service
from modules.elm.services import config as config_service
from modules.elm.services import decisions as decision_service
from modules.elm.services import notifications

P_EXTENSION = "elm.extension.request"


@transaction.atomic
def request_extension(
        *, principal, leave_id: int,
        additional_start: date,
        additional_end: date,
        purpose: str = "",
        substitute_required: bool = False,
        substitute_user_id: int | None = None,
        ) -> LeaveExtension:
    """Request additional leave time while
    ongoing EL/COL/VL is being availed."""
    leave = scoping.application_for(
        principal, leave_id)
    if leave is None:
        raise NotFoundError("No such leave.")
    if leave.user_id != principal.user_id:
        raise PermissionDeniedError(
            "Only the applicant may extend.",
            code="permission_denied")
    if not principal.has_permission(P_EXTENSION):
        raise PermissionDeniedError(
            "You may not request an extension.",
            code="permission_denied")
    if leave.status != sm.ONGOING:
        raise ConflictError(
            "An extension applies only to an "
            "ongoing EL/COL/VL leave.",
            code="not_ongoing")
    if leave.category not in ent.EXTENDABLE:
        raise ConflictError(
            f"{leave.category} may not be "
            f"extended.", code="not_extendable")
    if additional_end < additional_start:
        raise ConflictError(
            "The extension end precedes its "
            "start.", code="invalid_period")
    if additional_start <= leave.end_date:
        raise ConflictError(
            "The extension must begin after "
            "the current leave ends.",
            code="overlaps_current")

    # Validate the additional period with the
    # same rules as a new request.
    verdict = application_service.validate_submission(
        principal=principal,
        category=leave.category,
        start_date=additional_start,
        end_date=additional_end,
        leave_year=leave.leave_year,
        substitute_required=substitute_required,
        substitute_user_id=substitute_user_id)

    extension = LeaveExtension.objects.create(
        leave=leave, user_id=principal.user_id,
        additional_start=additional_start,
        additional_end=additional_end,
        purpose=purpose,
        additional_days=verdict["days"],
        substitute_required=substitute_required,
        status=sm.EXT_AWAITING_UNIT_HEAD)

    director = decision_service._is_director(
        principal)
    if substitute_required:
        _goto(extension, principal,
                 sm.EXT_AWAITING_SUBSTITUTE,
                 "Substitute consent required")
        SubstituteAssignment.objects.create(
            kind="extension", extension=extension,
            applicant_user_id=principal.user_id,
            substitute_user_id=substitute_user_id,
            responsibility_start=additional_start,
            responsibility_end=additional_end)
        notifications.notify_assigned(
            user_id=substitute_user_id,
            task_class="substitute_response",
            reference_id=extension.pk,
            subject="Substitute requested",
            body=("You are nominated as "
                  "substitute for a leave "
                  "extension."))
    elif director:
        _goto(extension, principal,
                 sm.EXT_PENDING_FINAL,
                 "Director self-sanction path")
        _notify_authority(extension)
    else:
        _goto(extension, principal,
                 sm.EXT_AWAITING_UNIT_HEAD,
                 "Extension awaiting Unit Head "
                 "review")
        _notify_unit_head(extension)
    return extension


@transaction.atomic
def unit_head_extension(
        *, principal, extension_id: int,
        outcome: str = "",
        recommendation: str = "",
        reason: str = ""
        ) -> LeaveExtension:
    """The Unit Head's extension review
    (EL-UC-003 for extensions).

    Higher-sanction only: the Unit Head
    records a recommendation and routes
    onward.
    """
    extension = _get(extension_id)
    if extension.status != sm.EXT_AWAITING_UNIT_HEAD:
        raise ConflictError(
            "The extension is not awaiting "
            "Unit Head review.",
            code="not_awaiting_unit_head")
    decision_service._require_permission(
        principal, decision_service.P_UNIT_HEAD)
    if not scoping.is_unit_head_of(
            principal.user_id, extension.user_id):
        raise PermissionDeniedError(
            "You are not this applicant's "
            "Unit Head.", code="not_unit_head")
    if recommendation not in ("recommended",
                               "not_recommended"):
        raise ConflictError(
            "A recommendation is required.",
            code="recommendation_required")

    category = extension.leave.category
    if config_service.has_establishment_step(
            category):
        _goto(extension, principal,
                 sm.EXT_PENDING_EST,
                 f"Recommended: {recommendation}")
    else:
        _goto(extension, principal,
                 sm.EXT_PENDING_FINAL,
                 f"Recommended: {recommendation}")
        _notify_authority(extension)
    return extension


@transaction.atomic
def establishment_extension(
        *, principal, extension_id: int,
        reason: str = ""
        ) -> LeaveExtension:
    """The Establishment routing step for an
    extension, where configured."""
    extension = _get(extension_id)
    if extension.status != sm.EXT_PENDING_EST:
        raise ConflictError(
            "The extension is not awaiting "
            "establishment routing.",
            code="not_awaiting_establishment")
    decision_service._require_permission(
        principal,
        decision_service.P_ESTABLISHMENT)
    _goto(extension, principal,
             sm.EXT_PENDING_FINAL,
             "Establishment routing verified")
    _notify_authority(extension)
    return extension


@transaction.atomic
def final_extension(
        *, principal, extension_id: int,
        outcome: str, reason: str = ""
        ) -> LeaveExtension:
    """The final extension decision
    (EL-UC-005 for extensions).

    Approval posts only the incremental
    additional period; the original leave
    remains the base. Rejection preserves
    the original approved leave.
    """
    extension = _get(extension_id)
    if extension.status != sm.EXT_PENDING_FINAL:
        raise ConflictError(
            "The extension is not awaiting "
            "a final decision.",
            code="not_awaiting_final")
    decision_service._require_permission(
        principal, decision_service.P_SANCTION)

    if outcome == "approve":
        return _approve(extension, principal,
                           reason)
    if outcome == "reject":
        return _reject(extension, principal,
                          reason)
    raise ConflictError(
        "The decision must approve or reject.",
        code="invalid_outcome")


def _goto(extension, actor, to: str,
             reason: str) -> None:
    """Move an extension and record it on
    the parent leave's audit trail."""
    frm = extension.status
    extension.status = to
    extension.save(update_fields=[
        "status", "updated_at"])
    _write(extension, frm, to, actor, reason)


def extension_review(
        *, principal, extension_id: int,
        outcome: str = "",
        recommendation: str = "",
        reason: str = ""
        ) -> LeaveExtension:
    """Dispatch an extension decision
    to the handler for the stage it has
    reached (EL-UC-003/004/005 for
    extensions)."""
    extension = _get(extension_id)
    status = extension.status
    if status == sm.EXT_AWAITING_UNIT_HEAD:
        return unit_head_extension(
            principal=principal,
            extension_id=extension_id,
            outcome=outcome,
            recommendation=recommendation,
            reason=reason)
    if status == sm.EXT_PENDING_EST:
        return establishment_extension(
            principal=principal,
            extension_id=extension_id,
            reason=reason)
    if status == sm.EXT_PENDING_FINAL:
        return final_extension(
            principal=principal,
            extension_id=extension_id,
            outcome=outcome,
            reason=reason)
    raise ConflictError(
        "The extension is already "
        "decided.", code="already_decided")


def _get(extension_id: int) -> LeaveExtension:
    extension = (LeaveExtension.objects
                 .select_for_update()
                 .select_related("leave")
                 .filter(pk=extension_id)
                 .first())
    if extension is None:
        raise NotFoundError(
            "No such extension request.")
    return extension


def _approve(extension, actor,
                  reason: str) -> LeaveExtension:
    """Post only the incremental additional
    period (BR-EL-025)."""
    leave = extension.leave
    profile = EmployeeProfile.objects.filter(
        user_id=extension.user_id).first()
    is_faculty = (profile.category == "faculty"
                  if profile else False)
    balance = balance_service.get_or_create_balance(
        user_id=extension.user_id,
        category=leave.category,
        leave_year=leave.leave_year,
        is_faculty=is_faculty)
    balance_service.deduct(
        balance=balance,
        days=extension.additional_days,
        application_id=leave.pk,
        note=f"Extension #{extension.pk} "
             f"approved")

    frm = extension.status
    extension.status = sm.EXT_APPROVED
    extension.decided_by_user_id = (
        getattr(actor, "user_id", None))
    extension.decided_at = timezone.now()
    extension.decision_reason = reason[:300]
    extension.save(update_fields=[
        "status", "decided_by_user_id",
        "decided_at", "decision_reason",
        "updated_at"])
    # The base leave now ends later.
    leave.end_date = extension.additional_end
    leave.save(update_fields=[
        "end_date", "updated_at"])
    _write(extension, frm, sm.EXT_APPROVED,
              actor, reason)
    notifications.notify_decision(
        user_id=extension.user_id,
        application_id=leave.pk,
        decision="extension approved",
        category=leave.category, reason=reason)
    return extension


def _reject(extension, actor,
                 reason: str) -> LeaveExtension:
    frm = extension.status
    extension.status = sm.EXT_REJECTED
    extension.decided_by_user_id = (
        getattr(actor, "user_id", None))
    extension.decided_at = timezone.now()
    extension.decision_reason = reason[:300]
    extension.save(update_fields=[
        "status", "decided_by_user_id",
        "decided_at", "decision_reason",
        "updated_at"])
    _write(extension, frm, sm.EXT_REJECTED,
              actor, reason)
    notifications.notify_decision(
        user_id=extension.user_id,
        application_id=extension.leave.pk,
        decision="extension rejected",
        category=extension.leave.category,
        reason=reason)
    return extension


def _write(extension, frm: str, to: str,
              actor, reason: str) -> None:
    from modules.elm.models import LeaveApplicationTransition
    LeaveApplicationTransition.objects.create(
        application=extension.leave,
        from_status=frm, to_status=to,
        actor_user_id=getattr(actor, "user_id", None),
        actor_label="staff",
        reason=f"extension: {reason}")


def _notify_unit_head(extension) -> None:
    unit_head = scoping.unit_head_for(
        extension.user_id)
    if unit_head is None:
        return
    notifications.notify_assigned(
        user_id=unit_head,
        task_class="unit_head_review",
        reference_id=extension.pk,
        subject="Extension awaiting review",
        body="A leave extension awaits "
             "your review.")


def _notify_authority(extension) -> None:
    authority = config_service.final_authority_role(
        extension.leave.category)
    profile = EmployeeProfile.objects.filter(
        designation__iexact=authority).first()
    if profile is None:
        return
    notifications.notify_assigned(
        user_id=profile.user_id,
        task_class="final_sanction",
        reference_id=extension.pk,
        subject="Extension awaiting decision",
        body="A leave extension awaits "
             "your final decision.")
