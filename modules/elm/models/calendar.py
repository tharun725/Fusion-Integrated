"""The holiday / Restricted-Holiday calendar."""
from django.db import models

from core.db.mixins import TimeStampedModel


class HolidayCalendar(TimeStampedModel):
    """A publishable holiday/RH calendar.

    Date and RH validation use the currently effective
    published calendar until a replacement is published
    (BR-EL-031). Policy parameters have no such lifecycle,
    but the calendar does: an unpublished draft never
    displaces the governing one.
    """

    year = models.CharField(max_length=9, db_index=True)
    label = models.CharField(max_length=120)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(
        null=True, blank=True)
    is_effective = models.BooleanField(
        default=False, db_index=True,
        help_text="The currently effective published calendar")

    class Meta:
        db_table = "elm_holiday_calendar"
        constraints = [
            models.UniqueConstraint(
                fields=["year", "label"],
                name="elm_calendar_unique_per_year"),
        ]

    def __str__(self) -> str:
        return f"calendar {self.year} {self.label}"


class Holiday(TimeStampedModel):
    """One day in a calendar.

    ``is_restricted_holiday`` marks an RH -- a day an
    RH request may correspond to (BR-EL-003).
    ``is_closed`` marks a day that closes the institute
    and counts as a leave day inside a continuous
    EL/COL/VL interval.
    """

    calendar = models.ForeignKey(
        "HolidayCalendar", on_delete=models.CASCADE,
        related_name="holidays")
    date = models.DateField(db_index=True)
    label = models.CharField(max_length=160)
    is_restricted_holiday = models.BooleanField(
        default=False)
    is_closed = models.BooleanField(default=True)

    class Meta:
        db_table = "elm_holiday"
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "date"],
                name="elm_holiday_unique_per_calendar"),
        ]
        indexes = [
            models.Index(fields=["calendar", "date"],
                          name="elm_holiday_cal_idx")]

    def __str__(self) -> str:
        return f"{self.date} {self.label}"
