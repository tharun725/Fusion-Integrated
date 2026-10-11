"""Validation rules that need no database.

Each function is a pure predicate over plain values, so the
rules test without a database and a service composes them. The
state-machine guards and the services call these; nothing here
imports Django.

    BR-EL-001  category applicability
    BR-EL-003  RH must be an applicable Restricted Holiday
    BR-EL-006  VL only during a vacation period
    BR-EL-012  no impermissible overlap; CL halves excepted
    BR-EL-014  substitute is another employee, not the applicant,
               with no overlapping leave
"""
from __future__ import annotations

from datetime import date, timedelta

from modules.elm.domain import entitlements as ent


def is_supported_category(category: str) -> bool:
    """BR-EL-001: only the six supported categories."""
    return category in ent.CATEGORIES


def overlaps(a_start: date, a_end: date,
             b_start: date, b_end: date) -> bool:
    """Inclusive interval overlap."""
    return a_start <= b_end and b_start <= a_end


def cl_halves_conflict(a_half: str, b_half: str) -> bool:
    """BR-EL-012: first and second CL half on the same date do
    not overlap -- they occupy different halves."""
    return a_half == b_half


def find_overlap(
    start: date,
    end: date,
    *,
    half_day: str = "",
    existing: list[tuple[date, date, str]],
) -> tuple[date, date, str] | None:
    """The first existing interval this request impermissibly
    overlaps, if any (BR-EL-012).

    ``existing`` is a sequence of ``(start, end, half_day)`` for
    the employee's active pending or approved leave. A first-half
    and a second-half CL on the same date are allowed; any other
    overlap is impermissible.
    """
    for ex_start, ex_end, ex_half in existing:
        if not overlaps(start, end, ex_start, ex_end):
            continue
        if (ent.is_half_day_eligible(ent.CL)
                and half_day and ex_half
                and not cl_halves_conflict(half_day, ex_half)):
            continue
        return ex_start, ex_end, ex_half
    return None


def rh_dates_are_applicable(
    start: date,
    end: date,
    *,
    restricted_holidays: frozenset[date],
) -> list[date]:
    """BR-EL-003: every date of an RH request must be a
    Restricted Holiday in the effective published calendar.

    Returns the requested dates that are not applicable, so a
    caller can report exactly which days fail. An empty result
    means the request is fully applicable.
    """
    missing: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor not in restricted_holidays:
            missing.append(cursor)
        cursor += timedelta(days=1)
    return missing


def period_within_vacation(
    start: date,
    end: date,
    *,
    vacation_periods: list[tuple[date, date]],
) -> bool:
    """BR-EL-006: VL may be availed only during an applicable
    vacation period supplied by the Academic Calendar.

    The whole requested interval must fall inside one published
    vacation period.
    """
    return any(v_start <= start and end <= v_end
               for v_start, v_end in vacation_periods)


def substitute_is_eligible(
    *,
    applicant_user_id: int,
    substitute_user_id: int,
    is_employee: bool,
    responsibility_start: date,
    responsibility_end: date,
    substitute_leave: list[tuple[date, date]],
) -> bool:
    """BR-EL-014: the substitute must be another employee and
    must have no overlapping pending or approved leave during
    the responsibility period.
    """
    if not is_employee:
        return False
    if substitute_user_id == applicant_user_id:
        return False
    for s_start, s_end in substitute_leave:
        if overlaps(responsibility_start, responsibility_end,
                    s_start, s_end):
            return False
    return True
