from sqlalchemy.orm import Session

from app.models.entities import (
    Agent,
    ApprovalStatus,
    AssignmentStatus,
    CheckpointKind,
    Task,
    TaskAssignment,
    TaskKind,
    TaskStatus,
    Workflow,
    WorkflowParticipant,
    WorkflowRun,
    WorkflowStatus,
)
from app.services.activity_log import log_event
from app.workflows.state_machine import WorkflowStateMachine


class WorkflowOrchestrator:
    def __init__(self) -> None:
        self.state_machine = WorkflowStateMachine()

    def start_workflow_run(
        self,
        *,
        db: Session,
        workflow_id: int,
        user_id: int,
        shared_context_extra: dict | None = None,
    ) -> int:
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).one()

        participants = (
            db.query(Agent)
            .join(WorkflowParticipant, WorkflowParticipant.agent_id == Agent.id)
            .filter(WorkflowParticipant.workflow_id == workflow_id)
            .filter(Agent.is_active == True)  # noqa: E712
            .all()
        )

        if not participants:
            raise ValueError("Workflow has no active agents selected")

        coordinator = self._select_coordinator(participants)
        human_required = bool(workflow.require_human_approval) and any(a.approval_required for a in participants)

        ctx: dict = {"goal": workflow.goal}
        if shared_context_extra:
            ctx.update(shared_context_extra)

        run = WorkflowRun(
            workflow_id=workflow_id,
            workspace_id=workflow.workspace_id,
            status=WorkflowStatus.PLANNING,
            current_step_index=0,
            human_approval_required=human_required,
            shared_context=ctx,
        )
        db.add(run)
        db.flush()

        task = Task(
            workflow_run_id=run.id,
            kind=TaskKind.PLAN,
            order_index=0,
            objective=workflow.goal,
            status=TaskStatus.PENDING,
        )
        db.add(task)
        db.flush()

        assignment = TaskAssignment(
            task_id=task.id,
            agent_id=coordinator.id,
            status=AssignmentStatus.PENDING,
        )
        db.add(assignment)

        log_event(
            db,
            workspace_id=run.workspace_id,
            workflow_run_id=run.id,
            user_id=user_id,
            event_type="workflow_run_created",
            message="Workflow run created and coordinator plan task queued.",
            metadata={"workflow_id": workflow_id, "coordinator_agent_id": coordinator.id},
        )
        log_event(
            db,
            workspace_id=run.workspace_id,
            workflow_run_id=run.id,
            user_id=user_id,
            event_type="agent_assigned_task",
            message=f"Assigned coordinator to task {task.kind.value}.",
            metadata={"task_id": task.id, "agent_id": coordinator.id, "assignment_id": assignment.id},
        )

        db.commit()

        # Kick off coordinator plan in background.
        from app.tasks.celery_tasks import execute_agent_task

        execute_agent_task.delay(assignment.id, user_id)
        return run.id

    def decide_approval(
        self,
        *,
        db: Session,
        workflow_run_id: int,
        approval_id: int,
        approved: bool,
        notes: str | None,
        user_id: int,
    ) -> int | None:
        next_assignment_id = self.state_machine.on_approval_decision(
            db=db,
            workflow_run_id=workflow_run_id,
            approval_id=approval_id,
            approved=approved,
            user_id=user_id,
            notes=notes,
        )
        db.commit()

        if next_assignment_id is None:
            return None

        from app.tasks.celery_tasks import execute_agent_task

        execute_agent_task.delay(next_assignment_id, user_id)
        return next_assignment_id

    @staticmethod
    def _select_coordinator(participants: list[Agent]) -> Agent:
        for a in participants:
            if "coordinator" in (a.role_title or "").lower():
                return a
        # Fallback: first participant
        return sorted(participants, key=lambda x: x.created_at)[0]

