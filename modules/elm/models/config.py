"""ELM policy parameters and sanction hierarchy.

Policy parameters have no draft/publish/effective-version
lifecycle in this baseline (BR-EL-030): ELM uses the
current configured values directly.
"""
from django.db import models

from core.db.mixins import TimeStampedModel


class LeavePolicy(TimeStampedModel):
    """A single current policy parameter.

    One row per key, so revising a parameter is an UPDATE
    of the current value, never a new version. There is
    deliberately no status, no effective date and no
    published flag.
    """

    key = models.CharField(max_length=80, unique=True)
    value = models.CharField(max_length=500)
    description = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = "elm_leave_policy"

    def __str__(self) -> str:
        return f"{self.key}={self.value}"


class SanctionHierarchy(TimeStampedModel):
    """The configured processing/sanctioning path.

    One ordered row per step for a leave category
    (or ``*`` for every category). The path is resolved
    from the applicant, their unit, designation and this
    configuration (BR-EL-019).

    ``role`` names an authority role: ``unit_head``,
    ``establishment``, ``deputy_registrar_estt``,
    ``dean``, ``registrar``, ``director``. The final
    authority is the last step. ``is_establishment``
    marks the optional Establishment processing step.
    """

    ROLES = [
        ("unit_head", "Unit Head"),
        ("establishment", "Establishment (Dep. Registrar Estt.)"),
        ("deputy_registrar_estt", "Deputy Registrar (Estt.)"),
        ("dean", "Dean"),
        ("registrar", "Registrar"),
        ("director", "Director"),
    ]

    category = models.CharField(max_length=8,
                                   default="*")
    step_order = models.PositiveSmallIntegerField()
    role = models.CharField(max_length=32, choices=ROLES)
    is_establishment = models.BooleanField(default=False)

    class Meta:
        db_table = "elm_sanction_hierarchy"
        constraints = [
            models.UniqueConstraint(
                fields=["category", "step_order"],
                name="elm_hierarchy_unique_step"),
        ]
        ordering = ["category", "step_order"]

    def __str__(self) -> str:
        return f"{self.category} #{self.step_order} {self.role}"
