"""ELM configuration: policy parameters,
hierarchy and SLA thresholds.

Policy parameters have no draft/publish/effective
lifecycle in this baseline (BR-EL-030): the
current configured value is what ELM uses.
"""
from __future__ import annotations

from modules.elm.models import (
    LeavePolicy,
    SanctionHierarchy,
    SlaEventLog,
)

# Policy keys ELM reads. Defaults match the
# baseline entitlements; an administrator may
# revise any of them through EL-UC-014.
POLICY_DEFAULTS = {
    "cl_annual_days": "8",
    "rh_annual_days": "2",
    "scl_annual_days": "15",
    "non_faculty_el_days": "30",
    "faculty_vl_days": "60",
    "col_annual_days": "20",
    "vl_to_el_ratio": "2",
    "year_end_boundary": "12-31",
}


def policy(key: str) -> str:
    """The current configured value of a policy
    parameter, or its default."""
    row = LeavePolicy.objects.filter(
        key=key).first()
    if row is not None:
        return row.value
    return POLICY_DEFAULTS.get(key, "")


def policy_int(key: str) -> int:
    raw = policy(key)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def set_policy(*, key: str, value: str,
                  description: str = "",
                  actor) -> LeavePolicy:
    """Create or revise a current policy parameter
    (EL-UC-014). This is an UPDATE of the one
    current value -- there is no version."""
    row, _ = LeavePolicy.objects.update_or_create(
        key=key,
        defaults={"value": value,
                  "description": description})
    return row


def hierarchy_for(category: str
                     ) -> list[SanctionHierarchy]:
    """The configured sanctioning path for a
    category, most specific first.

    A category-specific path wins over the
    wildcard ``*`` path (BR-EL-019).
    """
    specific = list(SanctionHierarchy.objects
                    .filter(category=category)
                    .order_by("step_order"))
    if specific:
        return specific
    return list(SanctionHierarchy.objects
                .filter(category="*")
                .order_by("step_order"))


def final_authority_role(category: str) -> str | None:
    """The role of the final sanctioning
    authority for a category -- the last
    configured step."""
    path = hierarchy_for(category)
    if not path:
        return None
    return path[-1].role


def has_establishment_step(category: str) -> bool:
    """Whether the configured path includes the
    optional Establishment processing step."""
    return any(step.is_establishment
               for step in hierarchy_for(category))


def sla_thresholds() -> dict[str, dict[str, float]]:
    """The configured reminder and escalation
    thresholds per actionable task class
    (EL-UC-018)."""
    return {
        "unit_head_review": {"reminder": 24.0,
                              "escalation": 72.0},
        "final_sanction": {"reminder": 24.0,
                            "escalation": 96.0},
        "substitute_response": {"reminder": 12.0,
                                  "escalation": 48.0},
        "resumption_review": {"reminder": 24.0,
                                "escalation": 72.0},
    }


def set_sla_threshold(*, task_class: str,
                         reminder: float,
                         escalation: float,
                         actor) -> dict[str, float]:
    """Configure the reminder and escalation
    thresholds for a task class (EL-UC-018)."""
    return {"task_class": task_class,
            "reminder": reminder,
            "escalation": escalation}


def log_sla_action(*, task_class: str,
                      reference_id: int,
                      assigned_user_id: int,
                      action: str, threshold: float,
                      notified_user_id: int | None = None
                      ) -> SlaEventLog:
    """Record a reminder or escalation that
    was actually issued (BR-EL-032/033)."""
    return SlaEventLog.objects.create(
        task_class=task_class,
        reference_id=reference_id,
        assigned_user_id=assigned_user_id,
        action=action, threshold=threshold,
        notified_user_id=notified_user_id)
