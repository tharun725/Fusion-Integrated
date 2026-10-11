"""Event-triggered SLA processing (EL-UC-021).

When a configured reminder or escalation
threshold is reached for an actionable
task, ELM checks whether the task is
still pending. A still-pending task is
reminded or escalated and the action is
logged; a completed task is never
reminded or escalated (BR-EL-032/033).
"""
from __future__ import annotations

import logging

from django.utils import timezone

from modules.elm.models import (
    LeaveApplication,
    ResumptionRecord,
    SubstituteAssignment,
)
from modules.elm.services import config as config_service
from modules.elm.services import notifications

log = logging.getLogger("fusion.elm.sla")


def process_thresholds(
        *, task_class: str | None = None
        ) -> dict[str, int]:
    """Scan the actionable task classes and
    issue the reminder or escalation each
    pending task has become due for.

    Returns how many reminders and
    escalations were issued.
    """
    classes = ([task_class] if task_class
               else list(
                   config_service
                   .sla_thresholds()))
    reminders = escalations = 0
    for task_class_name in classes:
        issued = _process_class(task_class_name)
        reminders += issued["reminders"]
        escalations += issued["escalations"]
    return {"reminders": reminders,
            "escalations": escalations}


def _process_class(task_class: str
                        ) -> dict[str, int]:
    """One task class: find its pending
    tasks and fire whichever threshold
    each has reached."""
    thresholds = config_service.sla_thresholds(
        ).get(task_class, {})
    reminder_at = thresholds.get("reminder",
                                    24.0)
    escalation_at = thresholds.get(
        "escalation", 72.0)

    reminders = escalations = 0
    for task in _pending_tasks(task_class):
        age_hours = _age_hours(task)
        already = _fired_actions(
            task_class, task["reference_id"])
        if (age_hours >= escalation_at
                and "escalation" not in already):
            _escalate(task_class, task,
                      escalation_at)
            escalations += 1
        elif (age_hours >= reminder_at
                and "reminder" not in already):
            _remind(task_class, task,
                    reminder_at)
            reminders += 1
    return {"reminders": reminders,
            "escalations": escalations}


def _pending_tasks(task_class: str
                        ) -> list[dict]:
    """The still-pending tasks of one
    class, with who is responsible."""
    from modules.elm.domain import state_machine as sm

    now = timezone.now()
    tasks: list[dict] = []

    if task_class == "unit_head_review":
        tasks.extend({
            "reference_id": app.pk,
            "assigned_user_id": _unit_head_of(
                app.user_id),
            "created_at": app.created_at,
            "subject": "Leave awaiting Unit Head review",
        } for app in LeaveApplication.objects.filter(
            status=sm.AWAITING_UNIT_HEAD))
    elif task_class == "final_sanction":
        tasks.extend({
            "reference_id": app.pk,
            "assigned_user_id": _authority_of(app),
            "created_at": app.created_at,
            "subject": "Leave awaiting final sanction",
        } for app in LeaveApplication.objects.filter(
            status__in=(
                sm.AWAITING_FINAL,
                sm.AWAITING_DIRECTOR)))
    elif task_class == "substitute_response":
        tasks.extend({
            "reference_id": sub.pk,
            "assigned_user_id": sub.substitute_user_id,
            "created_at": sub.created_at,
            "subject": "Substitute response requested",
        } for sub in SubstituteAssignment.objects.filter(
            response="pending"))
    elif task_class == "resumption_review":
        tasks.extend({
            "reference_id": rec.pk,
            "assigned_user_id": _authority_of(
                rec.leave),
            "created_at": rec.created_at,
            "subject": "Resumption awaiting review",
        } for rec in ResumptionRecord.objects.filter(
            status=sm.RESUMPTION_PENDING))
    return [t for t in tasks
            if t["assigned_user_id"] is not None
            and t["created_at"] is not None
            and t["created_at"] <= now]


def _unit_head_of(user_id: int) -> int | None:
    from modules.elm.selectors import scoping
    return scoping.unit_head_for(user_id)


def _authority_of(application) -> int | None:
    from modules.elm.models import EmployeeProfile
    from modules.elm.services import config as cfg
    role = cfg.final_authority_role(
        application.category)
    profile = EmployeeProfile.objects.filter(
        designation__iexact=role).first()
    return profile.user_id if profile else None


def _age_hours(task: dict) -> float:
    return (timezone.now()
            - task["created_at"]).total_seconds() / 3600.0


def _fired_actions(task_class: str,
                        reference_id: int
                        ) -> set[str]:
    """The SLA actions already logged for
    this task, so a task is reminded and
    escalated at most once each."""
    from modules.elm.models import SlaEventLog
    return set(
        SlaEventLog.objects.filter(
            task_class=task_class,
            reference_id=reference_id
        ).values_list("action", flat=True))


def _remind(task_class: str, task: dict,
                 threshold: float) -> None:
    """BR-EL-032: the task is still pending,
    so the responsible user is reminded and
    the reminder logged."""
    config_service.log_sla_action(
        task_class=task_class,
        reference_id=task["reference_id"],
        assigned_user_id=task["assigned_user_id"],
        action="reminder", threshold=threshold)
    notifications.notify(
        user_id=task["assigned_user_id"],
        topic="sla.reminder",
        subject=f"Reminder: {task['subject']}",
        body=("This task is still pending "
              "and is due for action."),
        reference_kind=task_class,
        reference_id=task["reference_id"])


def _escalate(task_class: str, task: dict,
                   threshold: float) -> None:
    """BR-EL-033: the task is still pending
    past its escalation threshold, so the
    configured authority is notified and the
    escalation logged."""
    config_service.log_sla_action(
        task_class=task_class,
        reference_id=task["reference_id"],
        assigned_user_id=task["assigned_user_id"],
        action="escalation",
        threshold=threshold,
        notified_user_id=(
            task["assigned_user_id"]))
    notifications.notify(
        user_id=task["assigned_user_id"],
        topic="sla.escalation",
        subject=f"Escalation: {task['subject']}",
        body=("This task remained pending past "
              "its escalation threshold."),
        reference_kind=task_class,
        reference_id=task["reference_id"])
