"""Resumption, offline-sanctioned records and the SLA log."""
from django.db import models

from core.db.mixins import TimeStampedModel
from modules.elm.domain import state_machine as sm


class ResumptionRecord(TimeStampedModel):
    """An employee's declaration of actual return to duty
    after EL/COL/VL (EL-UC-010).

    Reviewed by the applicable Sanctioning Authority
    (EL-UC-011). A normal return changes nothing; an
    early or late return records the actual period,
    adjusts the balance and synchronises leave and
    attendance records (BR-EL-028).
    """

    STATUS = [
        (sm.RESUMPTION_PENDING, "Resumption review pending"),
        (sm.RESUMPTION_NO_ADJUSTMENT,
         "Reviewed -- no adjustment"),
        (sm.RESUMPTION_ADJUSTED,
         "Reviewed -- adjusted"),
    ]

    leave = models.ForeignKey(
        "LeaveApplication", on_delete=models.PROTECT,
        related_name="resumptions")
    user_id = models.IntegerField(db_index=True)
    actual_resumption_date = models.DateField()
    details = models.TextField(blank=True)
    submitted_at = models.DateTimeField(
        auto_now_add=True)
    status = models.CharField(max_length=40,
                             choices=STATUS,
                             default=sm.RESUMPTION_PENDING)
    reviewed_by_user_id = models.IntegerField(
        null=True, blank=True)
    reviewed_at = models.DateTimeField(
        null=True, blank=True)
    review_note = models.CharField(max_length=300,
                                  blank=True)

    class Meta:
        db_table = "elm_resumption_record"
        indexes = [
            models.Index(fields=["leave", "status"],
                          name="elm_resumption_leave_idx")]

    def __str__(self) -> str:
        return (f"resumption#{self.pk} "
                f"leave#{self.leave_id}")


class OfflineLeaveRecord(TimeStampedModel):
    """Leave already sanctioned through an authorised
    paper/offline process, entered retrospectively
    (EL-UC-016).

    Record synchronisation, not a second approval
    workflow (BR-EL-029): the sanction happened
    offline, this only brings ELM in line.
    """

    user_id = models.IntegerField(db_index=True)
    category = models.CharField(max_length=8)
    leave_year = models.CharField(max_length=9)
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.FloatField()
    sanction_reference = models.CharField(
        max_length=120,
        help_text="The paper sanction/reference evidence")
    reason_unavailable = models.CharField(
        max_length=300, blank=True,
        help_text="Why ELM could not be used")
    entered_by_user_id = models.IntegerField()
    recorded_at = models.DateTimeField(
        auto_now_add=True)

    class Meta:
        db_table = "elm_offline_leave_record"
        indexes = [
            models.Index(fields=["user_id",
                                    "leave_year"],
                          name="elm_offline_user_idx")]

    def __str__(self) -> str:
        return (f"offline#{self.pk} u{self.user_id} "
                f"{self.category}")


class Notification(TimeStampedModel):
    """A notification ELM issued to a user.

    Records who was notified, about what, and why --
    the evidence that an assignment, decision or
    withdrawal reached the people it concerned
    (BR-EL-035).
    """

    user_id = models.IntegerField(db_index=True)
    topic = models.CharField(max_length=80)
    subject = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    reference_kind = models.CharField(max_length=24,
                                         blank=True)
    reference_id = models.IntegerField(
        null=True, blank=True)

    class Meta:
        db_table = "elm_notification"
        indexes = [
            models.Index(fields=["user_id", "-created_at"],
                          name="elm_notification_user_idx")]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"notify#{self.pk} u{self.user_id} {self.topic}"


class SlaEventLog(TimeStampedModel):
    """Every reminder and escalation ELM issues (EL-UC-021).

    A threshold fires only for a task still pending;
    the log records which action was taken so a
    completed task is never reminded or escalated.
    """

    ACTIONS = [
        ("reminder", "Reminder"),
        ("escalation", "Escalation"),
    ]

    task_class = models.CharField(
        max_length=40,
        help_text="The actionable task class")
    reference_id = models.IntegerField(
        help_text="The pending task's id")
    assigned_user_id = models.IntegerField()
    action = models.CharField(max_length=12,
                              choices=ACTIONS)
    threshold = models.FloatField(
        help_text="Hours at which this fired")
    notified_user_id = models.IntegerField(
        null=True, blank=True,
        help_text="The authority an escalation named")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "elm_sla_event_log"
        indexes = [
            models.Index(fields=["task_class",
                                    "reference_id"],
                          name="elm_sla_ref_idx")]

    def __str__(self) -> str:
        return (f"sla#{self.pk} {self.action} "
                f"{self.task_class}#{self.reference_id}")
