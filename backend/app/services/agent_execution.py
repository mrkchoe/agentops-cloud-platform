from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import (
    Artifact,
    ArtifactKind,
    Agent,
    AssignmentStatus,
    Task,
    TaskAssignment,
    TaskKind,
    TaskStatus,
    WorkflowRun,
    Workflow,
)
from app.services.activity_log import log_event
from app.services.llm import get_provider
from app.services.prompt_builder import PromptBuilder


class AgentExecutionService:
    def __init__(self) -> None:
        self.prompt_builder = PromptBuilder()

    @staticmethod
    def _task_kind_to_artifact_kind(task_kind: TaskKind) -> ArtifactKind:
        return {
            TaskKind.PLAN: ArtifactKind.PLANNING_NOTES,
            TaskKind.RESEARCH: ArtifactKind.RESEARCH_NOTES,
            TaskKind.DRAFT: ArtifactKind.DRAFT_MEMO,
            TaskKind.REVIEW: ArtifactKind.REVIEW_REPORT,
            TaskKind.FINALIZE: ArtifactKind.FINAL_DELIVERABLE,
        }[task_kind]

    def execute_assignment(self, *, db: Session, assignment_id: int, user_id: int) -> None:
        assignment = db.query(TaskAssignment).filter(TaskAssignment.id == assignment_id).one()
        task = db.query(Task).filter(Task.id == assignment.task_id).one()

        # Workflow metadata for prompt construction.
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task.workflow_run_id).one()
        workflow_goal = db.query(Workflow).filter(Workflow.id == run.workflow_id).one()
        goal_text = workflow_goal.goal

        agent = db.query(Agent).filter(Agent.id == assignment.agent_id).one()

        assignment.status = AssignmentStatus.RUNNING
        task.status = TaskStatus.RUNNING
        assignment.started_at = assignment.started_at or self._now()
        task.started_at = task.started_at or self._now()

        db.add(assignment)
        db.add(task)
        db.commit()

        log_event(
            db,
            workspace_id=run.workspace_id,
            workflow_run_id=run.id,
            user_id=user_id,
            event_type="task_started",
            message=f"Task {task.kind.value} started by agent {agent.role_title}.",
            metadata={"task_id": task.id, "assignment_id": assignment.id, "agent_id": agent.id},
        )
        db.commit()

        # Gather prior artifacts as plain strings; state machine can parse JSON.
        prior_tasks = (
            db.query(Task)
            .filter(Task.workflow_run_id == run.id, Task.order_index < task.order_index)
            .order_by(Task.order_index.asc())
            .all()
        )
        prior_artifacts: list[str] = []
        if prior_tasks:
            for t in prior_tasks:
                artifacts = db.query(Artifact).filter(Artifact.task_id == t.id).order_by(Artifact.created_at.asc()).all()
                for a in artifacts:
                    prior_artifacts.append(a.content)

        prior_artifacts_text = prior_artifacts[-5:]

        messages, response_hint = self.prompt_builder.build_messages(
            agent=agent,
            task_kind=task.kind,
            objective=task.objective,
            workflow_goal=goal_text,
            shared_context=run.shared_context or {},
            prior_artifacts=prior_artifacts_text,
        )

        provider = get_provider()
        result = provider.generate(agent=agent, task_kind=task.kind, messages=messages, response_hint=response_hint)

        artifact_kind = self._task_kind_to_artifact_kind(task.kind)
        db.add(
            Artifact(
                task_id=task.id,
                agent_id=agent.id,
                kind=artifact_kind,
                content=result.text,
            )
        )

        assignment.status = AssignmentStatus.COMPLETED
        task.status = TaskStatus.COMPLETED
        assignment.completed_at = self._now()
        task.completed_at = self._now()

        db.add(assignment)
        db.add(task)
        db.commit()

        log_event(
            db,
            workspace_id=run.workspace_id,
            workflow_run_id=run.id,
            user_id=user_id,
            event_type="task_completed",
            message=f"Task {task.kind.value} completed by agent {agent.role_title}.",
            metadata={"task_id": task.id, "assignment_id": assignment.id, "agent_id": agent.id, "artifact_kind": artifact_kind.value},
        )
        db.commit()

    @staticmethod
    def _now() -> Any:
        # Local helper to avoid datetime import churn.
        from datetime import datetime

        return datetime.utcnow()

