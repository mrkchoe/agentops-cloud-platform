from sqlalchemy.orm import Session

from app.workflows.state_machine import WorkflowStateMachine


class ApprovalService:
    """
    Small service wrapper around the workflow state machine's approval transitions.
    This keeps approval-related orchestration out of the API routes.
    """

    def decide(
        self,
        *,
        db: Session,
        workflow_run_id: int,
        approval_id: int,
        approved: bool,
        notes: str | None,
        user_id: int,
    ) -> int | None:
        return WorkflowStateMachine().on_approval_decision(
            db=db,
            workflow_run_id=workflow_run_id,
            approval_id=approval_id,
            approved=approved,
            user_id=user_id,
            notes=notes,
        )

