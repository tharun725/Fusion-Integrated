"""The effective holiday/RH calendar.

Date and RH validation use the currently
effective published calendar until a replacement
is published (BR-EL-031). An unpublished draft
never displaces the governing one.
"""
from __future__ import annotations

from datetime import date

from core.api.exceptions import ConflictError
from modules.elm.models import (
    Holiday,
    HolidayCalendar,
)


def effective_calendar(year: str) -> HolidayCalendar | None:
    """The calendar currently governing ``year``."""
    return HolidayCalendar.objects.filter(
        year=year, is_published=True,
        is_effective=True).first()


def restricted_holidays(year: str
                          ) -> frozenset[date]:
    """The applicable Restricted Holidays in the
    effective calendar -- the days an RH request
    may correspond to (BR-EL-003)."""
    calendar = effective_calendar(year)
    if calendar is None:
        return frozenset()
    return frozenset(
        Holiday.objects.filter(
            calendar=calendar,
            is_restricted_holiday=True
        ).values_list("date", flat=True))


def closed_holidays(year: str) -> frozenset[date]:
    """Days the institute is closed, which count
    as leave days inside a continuous
    EL/COL/VL interval (BR-EL-011)."""
    calendar = effective_calendar(year)
    if calendar is None:
        return frozenset()
    return frozenset(
        Holiday.objects.filter(
            calendar=calendar,
            is_closed=True
        ).values_list("date", flat=True))


def publish(*, calendar_id: int,
               actor) -> HolidayCalendar:
    """Publish a replacement calendar, making it
    the effective one (EL-UC-015).

    Publishing a calendar retires the previous
    effective one for the same year, so exactly
    one calendar governs at any time.
    """
    calendar = HolidayCalendar.objects.select_for_update(
        ).get(pk=calendar_id)
    if calendar.is_published:
        raise ConflictError(
            "This calendar is already published.",
            code="already_published")
    HolidayCalendar.objects.filter(
        year=calendar.year,
        is_effective=True
    ).update(is_effective=False)
    calendar.is_published = True
    calendar.is_effective = True
    calendar.save(update_fields=[
        "is_published", "is_effective",
        "published_at", "updated_at"])
    return calendar


def create_calendar(*, year: str, label: str,
                       holidays: list[dict],
                       actor) -> HolidayCalendar:
    """Create (a draft of) a calendar with its
    days, for an authorised administrator."""
    calendar = HolidayCalendar.objects.create(
        year=year, label=label)
    for day in holidays:
        Holiday.objects.create(
            calendar=calendar,
            date=day["date"],
            label=day.get("label", ""),
            is_restricted_holiday=day.get(
                "is_restricted_holiday", False),
            is_closed=day.get("is_closed", True))
    return calendar
