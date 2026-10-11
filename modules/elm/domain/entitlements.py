"""Leave categories, entitlements, counting and year-end rules.

These are the ELM business rules expressed as pure Python data:

    BR-EL-001  supported categories
    BR-EL-002  CL 8/year, no carry-forward
    BR-EL-003  RH 2/year, must be an applicable Restricted Holiday
    BR-EL-004  SCL 15/year, admissibility is the authority's judgement
    BR-EL-005  non-faculty EL 30/year, carries forward
    BR-EL-006  faculty VL 60, only during a vacation period
    BR-EL-007  year-end VL -> EL at 2:1, fractional, VL does not carry
    BR-EL-008  converted EL is credited, carries forward, is availed
    BR-EL-009  COL 20/year, balance/evidence controlled, carries forward
    BR-EL-010  half-day CL consumes 0.5 day
    BR-EL-011  EL/COL/VL count continuously; CL/SCL/RH do not
"""
from __future__ import annotations

from datetime import date, timedelta

# -- Category registry (BR-EL-001) -----------------------------------------
CL = "CL"
RH = "RH"
SCL = "SCL"
EL = "EL"
COL = "COL"
VL = "VL"

#: The closed set ELM supports. Anything else is not a leave request.
CATEGORIES = (CL, RH, SCL, EL, COL, VL)

#: Human-readable names.
CATEGORY_LABELS = {
    CL: "Casual Leave",
    RH: "Restricted Holiday",
    SCL: "Special Casual Leave",
    EL: "Earned Leave",
    COL: "Commuted Leave",
    VL: "Vacation Leave",
}

#: Categories that count continuously across the interval -- intervening
#: weekends and closed holidays count as leave days (BR-EL-011).
CONTINUOUS_COUNTING = frozenset({EL, COL, VL})

#: Categories that lapse unused at year end (BR-EL-002/003/004).
LAPSING = frozenset({CL, RH, SCL})

#: Categories that carry forward unused balance (BR-EL-005/009).
CARRY_FORWARD = frozenset({EL, COL})

#: Categories whose higher sanction path skips the Unit Head's final
#: authority -- the Unit Head only recommends (BR-EL-016/017).
HIGHER_SANCTION = frozenset({SCL, EL, COL, VL})

#: Categories Unit Head decides outright (BR-EL-016).
UNIT_HEAD_FINAL = frozenset({CL, RH})

#: Categories that may be extended while ongoing (BR-EL-025).
EXTENDABLE = frozenset({EL, COL, VL})

#: Categories with a formal reviewed resumption (BR-EL-027).
RESUMABLE = frozenset({EL, COL, VL})


def default_entitlement(category: str, *, is_faculty: bool) -> int:
    """Annual entitlement in days, by category and employee kind.

    EL is faculty-specific in the other direction: faculty have no
    direct EL entitlement -- they earn it from VL conversion (BR-EL-008).
    Non-faculty staff receive 30 directly (BR-EL-005).
    """
    table = {
        CL: 8,
        RH: 2,
        SCL: 15,
        COL: 20,
    }
    if category in table:
        return table[category]
    if category == EL:
        return 0 if is_faculty else 30
    if category == VL:
        return 60 if is_faculty else 0
    raise ValueError(f"unknown leave category {category!r}")


def carries_forward(category: str) -> bool:
    return category in CARRY_FORWARD


def lapses_at_year_end(category: str) -> bool:
    return category in LAPSING


def counts_continuously(category: str) -> bool:
    return category in CONTINUOUS_COUNTING


def is_half_day_eligible(category: str) -> bool:
    """Only CL supports first/second-half requests (BR-EL-010)."""
    return category == CL


# -- Day counting (BR-EL-010, BR-EL-011) --------------------------------
def count_leave_days(
    category: str,
    start: date,
    end: date,
    *,
    closed_holidays: frozenset[date] = frozenset(),
    half_day: str = "",
) -> float:
    """Days a request consumes, by category.

    EL/COL/VL count every calendar day in the interval, weekends and
    closed holidays included (BR-EL-011). CL/SCL/RH count working days
    only -- Saturdays, Sundays and closed holidays inside the interval are
    skipped. A half-day CL consumes exactly 0.5 day (BR-EL-010).
    """
    if end < start:
        raise ValueError("leave end precedes its start")
    if half_day:
        if category != CL:
            raise ValueError("only CL may be a half day")
        return 0.5

    if category in CONTINUOUS_COUNTING:
        return float((end - start).days + 1)

    # Working-day counting for CL / SCL / RH.
    days = 0.0
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5 and cursor not in closed_holidays:
            days += 1.0
        cursor += timedelta(days=1)
    return days


# -- Year-end VL -> EL conversion (BR-EL-007, BR-EL-008) ----------------
def vl_to_el(vl_days: float) -> float:
    """Convert unused faculty VL to EL at 2 VL : 1 EL, fractional.

    ``2.5`` VL becomes ``1.25`` EL. The result is credited to the
    faculty member's EL balance, may carry forward and may be availed
    (BR-EL-008). VL itself never carries forward.
    """
    if vl_days < 0:
        raise ValueError("negative VL balance")
    return round(vl_days / 2.0, 2)


__all__ = [
    "CARRY_FORWARD",
    "CATEGORIES",
    "CATEGORY_LABELS",
    "CL",
    "COL",
    "CONTINUOUS_COUNTING",
    "EL",
    "EXTENDABLE",
    "HIGHER_SANCTION",
    "LAPSING",
    "RESUMABLE",
    "RH",
    "SCL",
    "UNIT_HEAD_FINAL",
    "VL",
    "carries_forward",
    "count_leave_days",
    "counts_continuously",
    "default_entitlement",
    "is_half_day_eligible",
    "lapses_at_year_end",
    "vl_to_el",
]
