"""Cancellation and extension requests.

Both are separate requests that reference the leave they
affect: an approved leave is never edited in place
(BR-EL-023, BR-EL-025).
"""
from django.db import models

from core.db.mixins import TimeStampedModel
from modules.elm.domain import state_machine as sm


class LeaveCancellation(TimeStampedModel):
    """Pre-start cancellation of an approved leave (EL-UC-008).

    Follows the same applicable hierarchy as the original
    leave. Approval marks the leave Cancelled and restores
    the deducted balance; rejection leaves it unchanged.
    """

    STATUS = [
        (sm.CANCEL_PENDING_UH, "Pending Unit Head review"),
        (sm.CANCEL_PENDING_EST, "Pending establishment"),
        (sm.CANCEL_PENDING_FINAL, "Pending final decision"),
        (sm.CANCEL_APPROVED, "Cancellation approved"),
        (sm.CANCEL_REJECTED, "Cancellation rejected"),
    ]

    leave = models.ForeignKey(
        "LeaveApplication", on_delete=models.PROTECT,
        related_name="cancellations")
    user_id = models.IntegerField(db_index=True)
    reason = models.TextField(blank=True)
    requested_on = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=40, choices=STATUS,
                             default=sm.CANCEL_PENDING_UH)
    decided_by_user_id = models.IntegerField(
        null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = "elm_leave_cancellation"
        indexes = [
            models.Index(fields=["leave", "status"],
                          name="elm_cancellation_leave_idx"),
            models.Index(fields=["user_id", "status"],
                          name="elm_cancellation_user_idx")]

    def __str__(self) -> str:
        return f"cancel#{self.pk} leave#{self.leave_id}"


class LeaveExtension(TimeStampedModel):
    """Additional leave time while EL/COL/VL is ongoing
    (EL-UC-009).

    Approval posts only the incremental additional period;
    the original approved leave remains the base.
    """

    STATUS = [
        (sm.EXT_AWAITING_SUBSTITUTE,
         "Awaiting extension substitute response"),
        (sm.EXT_APPLICANT_ACTION,
         "Extension applicant action required"),
        (sm.EXT_AWAITING_UNIT_HEAD,
         "Awaiting extension Unit Head review"),
        (sm.EXT_PENDING_EST,
         "Extension pending establishment"),
        (sm.EXT_PENDING_FINAL,
         "Extension pending final decision"),
        (sm.EXT_APPROVED, "Extension approved"),
        (sm.EXT_REJECTED, "Extension rejected"),
    ]

    leave = models.ForeignKey(
        "LeaveApplication", on_delete=models.PROTECT,
        related_name="extensions")
    user_id = models.IntegerField(db_index=True)
    additional_start = models.DateField()
    additional_end = models.DateField()
    purpose = models.TextField(blank=True)
    additional_days = models.FloatField(default=0.0)
    substitute_required = models.BooleanField(default=False)
    status = models.CharField(max_length=40, choices=STATUS,
                             default=sm.EXT_AWAITING_UNIT_HEAD)
    decided_by_user_id = models.IntegerField(
        null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = "elm_leave_extension"
        indexes = [
            models.Index(fields=["leave", "status"],
                          name="elm_extension_leave_idx"),
            models.Index(fields=["user_id", "status"],
                          name="elm_extension_user_idx")]

    def __str__(self) -> str:
        return f"extend#{self.pk} leave#{self.leave_id}"
