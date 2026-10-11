"""ELM's public surface. Plural by signature.

The ONLY thing other modules may import.
An N+1 is unwritable: callers pass a
sequence of ids and get a mapping back.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from modules.elm.models import LeaveBalance


@dataclass(frozen=True)
class LeaveBalanceDTO:
    user_id: int
    category: str
    leave_year: str
    entitled: float
    opening: float
    used: float
    lapsed: float
    available: float


@dataclass(frozen=True)
class LeaveStatusDTO:
    user_id: int
    pending_count: int
    approved_count: int
    ongoing_count: int


def get_leave_balances(
        user_ids: Sequence[int],
        leave_year: str
        ) -> dict[int, dict[str, LeaveBalanceDTO]]:
    """Current balances per employee and
    category. Plural, so a caller checks
    a whole unit in one round trip."""
    ids = {int(i) for i in user_ids
           if i is not None}
    if not ids:
        return {}
    rows = (LeaveBalance.objects
            .filter(user_id__in=ids,
                    leave_year=leave_year))
    out: dict[int, dict[str,
                          LeaveBalanceDTO]] = {
        uid: {} for uid in ids}
    for row in rows:
        out[row.user_id][row.category] = (
            LeaveBalanceDTO(
                user_id=row.user_id,
                category=row.category,
                leave_year=row.leave_year,
                entitled=row.entitled,
                opening=row.opening,
                used=row.used,
                lapsed=row.lapsed,
                available=row.available))
    return out


def get_leave_status(
        user_ids: Sequence[int]
        ) -> dict[int, LeaveStatusDTO]:
    """A compact leave-activity summary per
    employee -- enough for a portal widget
    without leaking another employee's
    requests."""
    ids = {int(i) for i in user_ids
           if i is not None}
    if not ids:
        return {}
    from django.db.models import Count, Q

    from modules.elm.domain import state_machine as sm
    from modules.elm.models import LeaveApplication
    apps = (LeaveApplication.objects
            .filter(user_id__in=ids)
            .values("user_id")
            .annotate(
                pending=Count("pk", filter=Q(
                    status__in=tuple(
                        sm.PENDING_STATES))),
                approved=Count("pk", filter=Q(
                    status__in=("approved",
                                    "ongoing"))),
                ongoing=Count("pk", filter=Q(
                    status="ongoing")),
            ))
    by_user = {r["user_id"]: r for r in apps}
    return {
        uid: LeaveStatusDTO(
            user_id=uid,
            pending_count=by_user
              .get(uid, {}).get("pending", 0),
            approved_count=by_user
              .get(uid, {}).get("approved", 0),
            ongoing_count=by_user
              .get(uid, {}).get("ongoing", 0),
        )
        for uid in ids}
