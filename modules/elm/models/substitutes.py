"""Substitute / responsibility-holder assignments."""
from django.db import models

from core.db.mixins import TimeStampedModel


class SubstituteAssignment(TimeStampedModel):
    """One nominated substitute for one request (EL-UC-002).

    The substitute must be another employee, must not be
    the applicant, and must have no overlapping leave
    during the responsibility period (BR-EL-014).
    Routing does not proceed until the substitute accepts
    (BR-EL-015).
    """

    RESPONSE = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
    ]

    # What the assignment covers: a new leave, an extension.
    KINDS = [
        ("leave", "Leave application"),
        ("extension", "Leave extension"),
    ]

    kind = models.CharField(max_length=12, choices=KINDS,
                             default="leave")
    application = models.ForeignKey(
        "LeaveApplication", on_delete=models.CASCADE,
        related_name="substitute_assignments",
        null=True, blank=True)
    extension = models.ForeignKey(
        "LeaveExtension", on_delete=models.CASCADE,
        related_name="substitute_assignments",
        null=True, blank=True)

    applicant_user_id = models.IntegerField(db_index=True)
    substitute_user_id = models.IntegerField(db_index=True)

    responsibility_start = models.DateField()
    responsibility_end = models.DateField()

    response = models.CharField(max_length=12,
                                 choices=RESPONSE,
                                 default="pending")
    responded_at = models.DateTimeField(
        null=True, blank=True)
    decline_reason = models.CharField(max_length=300,
                                       blank=True)

    class Meta:
        db_table = "elm_substitute_assignment"
        indexes = [
            models.Index(fields=["substitute_user_id",
                                    "response"],
                          name="elm_substitute_user_idx")]

    def __str__(self) -> str:
        return (f"substitute#{self.pk} "
                f"for u{self.applicant_user_id}: "
                f"u{self.substitute_user_id} {self.response}")
