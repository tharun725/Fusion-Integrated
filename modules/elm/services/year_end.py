"""Year-end leave processing (EL-UC-020).

At the configured year-end boundary:
unused CL, RH and SCL lapse; unused
faculty VL converts to EL at 2:1
including fractional conversion and no
VL carry-forward; EL and COL carry
forward. The resulting leave-account
transactions are recorded and processing
exceptions are reported.
"""
from __future__ import annotations

import logging

from django.db import transaction

from modules.elm.domain import entitlements as ent
from modules.elm.models import (
    EmployeeProfile,
    LeaveBalance,
)
from modules.elm.services import balances as balance_service

log = logging.getLogger("fusion.elm.year_end")


@transaction.atomic
def run_year_end(*, leave_year: str
                      ) -> dict:
    """Apply every category outcome for a
    leaving year and open the next year's
    balances.

    Returns the processing summary,
    including any accounts that could not
    be processed consistently and were
    reported as exceptions rather than
    silently adjusted.
    """
    exceptions: list[str] = []
    lapsed = conversions = carried = 0

    balances = list(LeaveBalance.objects
                    .filter(leave_year=leave_year))
    for balance in balances:
        try:
            outcome = _process_account(
                balance, leave_year)
            lapsed += outcome["lapsed"]
            conversions += outcome["converted"]
            carried += outcome["carried"]
        except Exception as exc:
            # An account that cannot be
            # processed consistently is
            # reported, never silently
            # committed.
            exceptions.append(
                f"u{balance.user_id} "
                f"{balance.category}: {exc}")
            log.exception(
                "year_end account failed "
                "u%s %s", balance.user_id,
                balance.category)

    return {
        "leave_year": leave_year,
        "accounts": len(balances),
        "lapsed_days": lapsed,
        "converted_vl_days": conversions,
        "carried_forward_days": carried,
        "exceptions": exceptions,
    }


def _process_account(balance: LeaveBalance,
                          leave_year: str
                          ) -> dict:
    """Apply the year-end outcome for one
    account and open the next year's
    account where the category carries
    forward."""
    category = balance.category
    unused = balance_service.year_end_available(
        balance)
    outcome = {"lapsed": 0.0,
               "converted": 0.0,
               "carried": 0.0}

    if category in ent.LAPSING:
        # CL, RH, SCL: unused days lapse.
        if unused > 0:
            balance_service._post(
                balance, kind="lapse",
                amount=unused,
                note="Year-end lapse")
            outcome["lapsed"] = unused
        return outcome

    if category == ent.VL:
        # Faculty VL converts to EL at
        # 2:1, fractional; VL never
        # carries forward.
        converted = ent.vl_to_el(unused)
        if converted > 0:
            _credit_el_conversion(
                balance.user_id,
                leave_year, converted)
            outcome["converted"] = converted
        # The VL balance itself is closed:
        # its remaining entitlement is
        # lapsed, leaving no VL balance.
        if unused > 0:
            balance_service._post(
                balance, kind="lapse",
                amount=unused,
                note="VL converted at year end")
        return outcome

    # EL and COL carry forward.
    if unused > 0:
        next_year = _next_year(leave_year)
        _carry_forward(
            balance.user_id, category,
            leave_year, next_year, unused)
        outcome["carried"] = unused
    return outcome


def _credit_el_conversion(user_id: int,
                               leave_year: str,
                               days: float
                               ) -> None:
    """Credit EL created by VL conversion
    to the faculty member's EL balance,
    where it may carry forward and be
    availed (BR-EL-008)."""
    next_year = _next_year(leave_year)
    profile = EmployeeProfile.objects.filter(
        user_id=user_id).first()
    is_faculty = (profile.category == "faculty"
                  if profile else False)
    el = balance_service.get_or_create_balance(
        user_id=user_id, category=ent.EL,
        leave_year=next_year,
        is_faculty=is_faculty)
    balance_service._post(
        el, kind="conversion", amount=days,
        note=f"VL conversion from {leave_year}")


def _carry_forward(user_id: int,
                        category: str,
                        leave_year: str,
                        next_year: str,
                        days: float) -> None:
    """Open next year's balance with the
    carried-forward unused days."""
    profile = EmployeeProfile.objects.filter(
        user_id=user_id).first()
    is_faculty = (profile.category == "faculty"
                  if profile else False)
    balance_service.get_or_create_balance(
        user_id=user_id, category=category,
        leave_year=next_year,
        is_faculty=is_faculty)
    next_balance = LeaveBalance.objects.get(
        user_id=user_id, category=category,
        leave_year=next_year)
    balance_service._post(
        next_balance, kind="carry_forward",
        amount=days,
        note=f"Carried forward from {leave_year}")


def _next_year(leave_year: str) -> str:
    """The year that follows ``leave_year``.

    Leave years are recorded as four-digit
    calendar years, so the successor is
    the year plus one.
    """
    try:
        return str(int(leave_year) + 1)
    except ValueError:
        return leave_year
