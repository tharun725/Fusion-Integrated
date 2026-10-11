"""Organisational units, employee profiles and vacation periods.

ELM owns the leave-relevant structure of the organisation:
which unit a person belongs to, their designation, who
heads each unit, and the vacation periods VL is availed in.
"""
from django.db import models

from core.db.mixins import TimeStampedModel


class OrgUnit(TimeStampedModel):
    """A Department, Section or Office.

    ``unit_head_user_id`` is the Unit Head -- a plain
    integer, because there is no user table here.
    """

    UNIT_KINDS = [
        ("department", "Department"),
        ("section", "Section"),
        ("office", "Office"),
    ]

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=16,
                               choices=UNIT_KINDS,
                               default="department")
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT,
        related_name="children",
        null=True, blank=True)
    unit_head_user_id = models.IntegerField(
        null=True, blank=True, db_index=True)

    class Meta:
        db_table = "elm_org_unit"
        indexes = [
            models.Index(fields=["parent"],
                          name="elm_unit_parent_idx")]

    def __str__(self) -> str:
        return f"{self.code} ({self.name})"


class EmployeeProfile(TimeStampedModel):
    """An employee's ELM record: category, designation, unit.

    A local projection of the employee's leave-relevant
    directory data, so routing can be resolved without an
    HTTP round-trip per request. ``user_id`` is the IAM
    id; there is no user table in this database.
    """

    EMPLOYEE_KINDS = [
        ("faculty", "Faculty"),
        ("staff", "Staff"),
    ]

    user_id = models.IntegerField(unique=True,
                                     db_index=True)
    category = models.CharField(max_length=12,
                                   choices=EMPLOYEE_KINDS)
    designation = models.CharField(max_length=80)
    unit = models.ForeignKey(
        "OrgUnit", on_delete=models.PROTECT,
        related_name="members",
        null=True, blank=True)

    class Meta:
        db_table = "elm_employee_profile"

    def __str__(self) -> str:
        return f"u{self.user_id} {self.designation}"


class VacationPeriod(TimeStampedModel):
    """A vacation period during which VL may be availed.

    The Academic Calendar is maintained outside ELM by the
    appropriate academic module/service (EXT-01) and is
    assumed to be available to ELM. This table is the
    projection of those published vacation periods that
    ELM reads; it is synced, never edited by hand.
    """

    academic_year = models.CharField(max_length=9)
    label = models.CharField(max_length=120)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField()

    class Meta:
        db_table = "elm_vacation_period"
        indexes = [
            models.Index(fields=["academic_year",
                                    "start_date"],
                          name="elm_vacation_year_idx")]

    def __str__(self) -> str:
        return f"{self.label} {self.start_date}..{self.end_date}"
