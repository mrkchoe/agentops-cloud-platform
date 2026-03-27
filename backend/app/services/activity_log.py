from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import ActivityLog


def log_event(
    db: Session,
    *,
    workspace_id: int,
    workflow_run_id: int | None,
    user_id: int,
    event_type: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        ActivityLog(
            workspace_id=workspace_id,
            workflow_run_id=workflow_run_id,
            user_id=user_id,
            event_type=event_type,
            message=message,
            metadata_=metadata or {},
        )
    )

