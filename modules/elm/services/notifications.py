"""Recording the notifications ELM issues.

BR-EL-035: an actionable task notifies its assignee.
The final decision notifies the employee. A withdrawal
informs the concerned roles. Each is one row here,
inside the same transaction as the state change it
reports, so a rolled-back change notifies nobody.
"""
from __future__ import annotations

from modules.elm.models import Notification


def notify(*, user_id: int, topic: str,
              subject: str, body: str = "",
              reference_kind: str = "",
              reference_id: int | None = None
              ) -> Notification:
    return Notification.objects.create(
        user_id=user_id, topic=topic, subject=subject,
        body=body, reference_kind=reference_kind,
        reference_id=reference_id)


def notify_assigned(*, user_id: int, task_class: str,
                       reference_id: int,
                       subject: str,
                       body: str = "") -> Notification:
    """BR-EL-035 -- the task was assigned, so the
    assignee hears about it."""
    return notify(
        user_id=user_id, topic="task.assigned",
        subject=subject, body=body,
        reference_kind=task_class,
        reference_id=reference_id)


def notify_decision(*, user_id: int,
                       application_id: int,
                       decision: str,
                       category: str,
                       reason: str = "") -> Notification:
    """The final decision reaches the employee."""
    return notify(
        user_id=user_id,
        topic="leave.decision",
        subject=f"Leave {decision}",
        body=(f"Your {category} request "
              f"(#{application_id}) was {decision}."
              + (f" {reason}" if reason else "")),
        reference_kind="leave",
        reference_id=application_id)


def notify_withdrawal(*, user_ids, application_id: int,
                         category: str,
                         ) -> list[Notification]:
    """A withdrawal informs the concerned roles."""
    return [notify(
                user_id=uid,
                topic="leave.withdrawn",
                subject="Leave request withdrawn",
                body=(f"A {category} request "
                      f"(#{application_id}) was "
                      f"withdrawn."),
                reference_kind="leave",
                reference_id=application_id)
            for uid in user_ids]
