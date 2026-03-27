from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import WorkflowRun


def notify_workflow_run_event(
    _db: Session,
    run: WorkflowRun,
    message: str,
    *,
    body_structured: dict[str, Any] | None = None,
    event_type: str = "workflow_progress",
) -> None:
    """If this run was started from WhatsApp, enqueue an outbound notification."""
    ctx = run.shared_context or {}
    if not ctx.get("messaging_conversation_id"):
        return

    from app.tasks.celery_tasks import send_conversation_notification_task

    send_conversation_notification_task.delay(
        int(ctx["messaging_conversation_id"]),
        message,
        body_structured or {},
        event_type,
    )


__all__ = ["notify_workflow_run_event"]
