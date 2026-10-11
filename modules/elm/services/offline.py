"""Retrospective recording of
already-sanctioned offline leave
(EL-UC-016).

Only leave already sanctioned through an
authorised paper/offline process may be
recorded. Sanction/reference evidence is
captured, the entry is validated for
record consistency, balances and history
are synchronised, and no second approval
workflow begins (BR-EL-029).
"""
from __future__ import annotations

from django.db import transaction

from core.api.exceptions import (
    ConflictError,
    PermissionDeniedError,
)
from modules.elm.domain import entitlements as ent
from modules.elm.models import (
    EmployeeProfile,
    OfflineLeaveRecord,
)
from modules.elm.services import balances as balance_service

P_OFFLINE = "elm.offline.record"


@transaction.atomic
def record_offline(
        *, principal, user_id: int,
        category: str, leave_year: str,
        start_date, end_date, days: float,
        sanction_reference: str,
        reason_unavailable: str = ""
        ) -> OfflineLeaveRecord:
    """Record leave already sanctioned
    offline (EL-UC-016).

    This is synchronisation, not a second
    approval: the sanction happened on
    paper, this only brings ELM in line.
    """
    if not principal.has_permission(P_OFFLINE):
        raise PermissionDeniedError(
            "Only a Leave Administrator may "
            "record offline-sanctioned leave.",
            code="permission_denied")
    if not sanction_reference.strip():
        raise ConflictError(
            "Sanction/reference evidence is "
            "required.", code="evidence_required")
    if category not in ent.CATEGORIES:
        raise ConflictError(
            f"{category!r} is not a supported "
            f"leave category.",
            code="unsupported_category")
    if end_date < start_date:
        raise ConflictError(
            "The leave end precedes its "
            "start.", code="invalid_period")
    if days <= 0:
        raise ConflictError(
            "Recorded leave must consume at "
            "least one day.", code="invalid_days")

    # Record-consistency validation: the
    # entry must not double-count an
    # overlapping recorded period.
    overlapping = OfflineLeaveRecord.objects.filter(
        user_id=user_id, category=category,
        leave_year=leave_year,
        start_date__lte=end_date,
        end_date__gte=start_date).exists()
    if overlapping:
        raise ConflictError(
            "An offline entry already covers "
            "part of this period.",
            code="record_inconsistent")

    profile = EmployeeProfile.objects.filter(
        user_id=user_id).first()
    is_faculty = (profile.category == "faculty"
                  if profile else False)
    balance = balance_service.get_or_create_balance(
        user_id=user_id, category=category,
        leave_year=leave_year,
        is_faculty=is_faculty)

    record = OfflineLeaveRecord.objects.create(
        user_id=user_id, category=category,
        leave_year=leave_year,
        start_date=start_date, end_date=end_date,
        days=days,
        sanction_reference=sanction_reference,
        reason_unavailable=reason_unavailable,
        entered_by_user_id=principal.user_id)

    balance_service.record_offline(
        balance=balance, days=days,
        reference=sanction_reference,
        note="Offline-sanctioned leave "
             "recorded")
    return record
