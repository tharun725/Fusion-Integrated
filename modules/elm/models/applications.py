"""The leave request and its append-only audit trail."""
from django.db import models

from core.db.mixins import TimeStampedModel, UserScopedModel
from modules.elm.domain import state_machine as sm


class LeaveApplication(TimeStampedModel, UserScopedModel):
    """One leave request.

    A submitted pending request is never modified in place
    (BR-EL-034): change before final approval is withdrawal
    followed, if needed, by a fresh application.
    """

    STATUS = [
        (sm.DRAFT, "Draft"),
        (sm.AWAITING_SUBSTITUTE, "Awaiting substitute response"),
        (sm.APPLICANT_ACTION, "Applicant action required"),
        (sm.AWAITING_UNIT_HEAD, "Awaiting Unit Head review"),
        (sm.AWAITING_ESTABLISHMENT, "Awaiting establishment routing"),
        (sm.AWAITING_FINAL, "Awaiting final sanction decision"),
        (sm.AWAITING_DIRECTOR, "Awaiting Director self-sanction"),
        (sm.APPROVED, "Approved"),
        (sm.REJECTED, "Rejected"),
        (sm.WITHDRAWN, "Withdrawn"),
        (sm.ONGOING, "Ongoing"),
        (sm.CANCELLED, "Cancelled"),
    ]

    #: Half of a single CL day (BR-EL-010).
    HALF_DAY = [
        ("", "Full day"),
        ("first", "First half"),
        ("second", "Second half"),
    ]

    category = models.CharField(max_length=8,
                                 choices=[
                                     (c, c) for c in
                                     ("CL", "RH", "SCL", "EL",
                                      "COL", "VL")])
    start_date = models.DateField(db_index=True)
    end_date = models.DateField()
    half_day = models.CharField(max_length=8, choices=HALF_DAY,
                                 default="", blank=True)
    purpose = models.TextField(blank=True)
    leave_year = models.CharField(max_length=9, db_index=True)

    # Frozen at submission, so a later reorganisation never
    # rewrites who decided what.
    applicant_unit = models.ForeignKey(
        "OrgUnit", on_delete=models.PROTECT,
        related_name="applications",
        null=True, blank=True)
    applicant_designation = models.CharField(max_length=80,
                                            blank=True)
    applicant_kind = models.CharField(max_length=8, blank=True,
                                     choices=[
                                         ("faculty", "Faculty"),
                                         ("staff", "Staff")])

    # Station Leave (BR-EL-013): captured inside the same
    # application, never a separate request.
    station_leave = models.BooleanField(default=False)
    station_leave_details = models.TextField(blank=True)

    substitute_required = models.BooleanField(default=False)

    # Days the request consumes, computed at submission.
    days_requested = models.FloatField(default=0.0)

    status = models.CharField(max_length=32, choices=STATUS,
                             default=sm.DRAFT)

    # Populated when a final decision is recorded.
    decided_by_user_id = models.IntegerField(
        null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=300, blank=True)
    withdrawn_reason = models.CharField(max_length=300, blank=True)
    recommendation = models.CharField(
        max_length=16, blank=True,
        choices=[
            ("", "--"),
            ("recommended", "Recommended"),
            ("not_recommended", "Not Recommended"),
        ])

    class Meta:
        db_table = "elm_leave_application"
        indexes = [
            models.Index(fields=["user_id", "status"],
                          name="elm_application_user_idx"),
            models.Index(fields=["status", "start_date"],
                          name="elm_application_status_idx"),
            models.Index(fields=["leave_year", "category"],
                          name="elm_application_year_cat_idx"),
        ]

    def __str__(self) -> str:
        return (f"leave#{self.pk} u{self.user_id} "
                f"{self.category} {self.status}")

    @property
    def is_pending(self) -> bool:
        return self.status in sm.PENDING_STATES


class LeaveApplicationTransition(models.Model):
    """Append-only audit of every state change."""

    application = models.ForeignKey(
        LeaveApplication, on_delete=models.CASCADE,
        related_name="transitions")
    from_status = models.CharField(max_length=32)
    to_status = models.CharField(max_length=32)
    actor_user_id = models.IntegerField(null=True, blank=True)
    actor_label = models.CharField(max_length=40, blank=True)
    reason = models.CharField(max_length=300, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "elm_leave_application_transition"
        indexes = [
            models.Index(fields=["application", "at"],
                          name="elm_transition_app_idx")]
        ordering = ["at"]

    def __str__(self) -> str:
        return (f"leave#{self.application_id} "
                f"{self.from_status}->{self.to_status}")
