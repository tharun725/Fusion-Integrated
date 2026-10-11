"""Leave balances: entitlement, deduction,
restoration and the ledger.

Every balance movement is one append-only
``LeaveTransaction`` inside the same transaction
as the application change that caused it, so the
account and the request never disagree.
"""
from __future__ import annotations

from django.db import transaction

from core.api.exceptions import ConflictError
from modules.elm.domain import entitlements as ent
from modules.elm.models import (
    LeaveBalance,
    LeaveTransaction,
)


def get_or_create_balance(
        *, user_id: int, category: str,
        leave_year: str, is_faculty: bool
        ) -> LeaveBalance:
    """The employee's balance for a category and
    year, created on first touch with the current
    entitlement (BR-EL-002..009)."""
    balance, _ = LeaveBalance.objects.get_or_create(
        user_id=user_id, category=category,
        leave_year=leave_year,
        defaults={
            "entitled": ent.default_entitlement(
                category, is_faculty=is_faculty),
        })
    return balance


def available(balance: LeaveBalance) -> float:
    return balance.available


def _post(balance: LeaveBalance, *, kind: str,
             amount: float,
             reference_id: int | None = None,
             reference_kind: str = "",
             note: str = "") -> LeaveTransaction:
    """Append one ledger row and fold it into the
    balance's running totals."""
    txn = LeaveTransaction.objects.create(
        balance=balance, user_id=balance.user_id,
        category=balance.category,
        leave_year=balance.leave_year,
        kind=kind, amount=amount,
        reference_id=reference_id,
        reference_kind=reference_kind, note=note)
    if kind == "debit":
        balance.used = round(balance.used + amount, 2)
    elif kind == "restore":
        balance.used = round(balance.used - amount, 2)
    elif kind == "offline":
        # Leave already taken offline, recorded
        # retrospectively, still debits the
        # balance (EL-UC-016).
        balance.used = round(balance.used + amount, 2)
    elif kind == "credit":
        balance.entitled = round(
            balance.entitled + amount, 2)
    elif kind == "adjust":
        # A signed correction to the used total.
        balance.used = round(balance.used + amount, 2)
    elif kind == "carry_forward" or kind == "conversion":
        balance.opening = round(
            balance.opening + amount, 2)
    elif kind == "lapse":
        balance.lapsed = round(
            balance.lapsed + amount, 2)
    balance.save(update_fields=[
        "entitled", "opening", "used", "lapsed",
        "updated_at"])
    return txn


@transaction.atomic
def deduct(*, balance: LeaveBalance, days: float,
              application_id: int,
              note: str = "") -> LeaveTransaction:
    """Deduct an approved leave's days (EL-UC-005).

    Refuses to overdraw the available balance --
    an approval never creates a negative account.
    """
    if days <= 0:
        raise ConflictError(
            "Leave must consume at least one day.",
            code="invalid_leave_days")
    if days > available(balance) + 1e-9:
        raise ConflictError(
            f"Only {available(balance)} "
            f"{balance.category} day(s) available; "
            f"{days} were requested.",
            code="insufficient_balance",
            details=[{"available": available(balance),
                      "requested": days}])
    return _post(balance, kind="debit", amount=days,
                    reference_id=application_id,
                    reference_kind="leave", note=note)


@transaction.atomic
def restore(*, balance: LeaveBalance, days: float,
               application_id: int,
               note: str = "") -> LeaveTransaction:
    """Restore deducted balance -- a cancellation or
    an early resumption (EL-UC-005, BR-EL-028)."""
    return _post(balance, kind="restore",
                    amount=days,
                    reference_id=application_id,
                    reference_kind="leave", note=note)


@transaction.atomic
def adjust(*, balance: LeaveBalance, days: float,
              application_id: int,
              note: str = "") -> LeaveTransaction:
    """Adjust by a signed amount -- a late resumption
    that consumed more than was approved."""
    return _post(balance, kind="adjust", amount=days,
                    reference_id=application_id,
                    reference_kind="leave", note=note)


@transaction.atomic
def record_offline(*, balance: LeaveBalance,
                      days: float,
                      reference: str,
                      note: str = ""
                      ) -> LeaveTransaction:
    """Post a retrospectively-recorded offline leave
    (EL-UC-016). Synchronisation, not a sanction."""
    return _post(balance, kind="offline",
                    amount=days,
                    reference_kind="offline",
                    note=f"{reference} {note}".strip())


def year_end_available(balance: LeaveBalance) -> float:
    """The balance that carries into year-end
    processing: what was entitled and carried in,
    less what was used and already lapsed."""
    return round(
        balance.opening + balance.entitled
        - balance.used - balance.lapsed, 2)
