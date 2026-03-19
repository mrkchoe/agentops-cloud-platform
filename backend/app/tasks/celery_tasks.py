from datetime import datetime

from app.db.session import db_session
from app.models.entities import (
    AssignmentStatus,
    Task,
    TaskAssignment,
    TaskStatus,
    WorkflowStatus,
    WorkflowRun,
)
from app.services.activity_log import log_event
from app.services.agent_execution import AgentExecutionService
from app.workflows.state_machine import WorkflowStateMachine

from .celery_app import celery_app


@celery_app.task(name="app.tasks.execute_agent_task")
def execute_agent_task(assignment_id: int, user_id: int) -> None:
    """
    Celery entrypoint for executing a single agent assignment.
    After task completion, the workflow state machine schedules the next step.
    """

    with db_session() as db:
        assignment = db.query(TaskAssignment).filter(TaskAssignment.id == assignment_id).one()
        task = db.query(Task).filter(Task.id == assignment.task_id).one()
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task.workflow_run_id).one()

        try:
            AgentExecutionService().execute_assignment(db=db, assignment_id=assignment_id, user_id=user_id)

            next_assignment_id = WorkflowStateMachine().on_task_completed(
                db=db,
                workflow_run_id=run.id,
                assignment_id=assignment_id,
                user_id=user_id,
            )

            if next_assignment_id is not None:
                execute_agent_task.delay(next_assignment_id, user_id)
        except Exception as e:
            now = datetime.utcnow()
            assignment.status = AssignmentStatus.FAILED
            assignment.error = str(e)[:4000]
            assignment.completed_at = now

            task.status = TaskStatus.FAILED
            task.error = str(e)[:8000]
            task.completed_at = now

            run.status = WorkflowStatus.FAILED
            run.error = str(e)[:8000]
            run.completed_at = now

            log_event(
                db,
                workspace_id=run.workspace_id,
                workflow_run_id=run.id,
                user_id=user_id,
                event_type="workflow_failed",
                message="Workflow task execution failed.",
                metadata={"assignment_id": assignment_id, "task_id": task.id},
            )

            db.add(assignment)
            db.add(task)
            db.add(run)
            db.commit()
            raise

