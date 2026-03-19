import json

from sqlalchemy.orm import Session

from app.models.entities import (
    Agent,
    Artifact,
    Approval,
    ApprovalStatus,
    CheckpointKind,
    Handoff,
    Task,
    TaskAssignment,
    TaskKind,
    TaskStatus,
    WorkflowRun,
    WorkflowParticipant,
    WorkflowStatus,
    AssignmentStatus,
)
from app.services.activity_log import log_event


class WorkflowStateMachine:
    """
    Deterministic state machine for a workflow run.
    Celery executes tasks; this class decides transitions and next scheduling points.
    """

    def on_task_completed(self, *, db: Session, workflow_run_id: int, assignment_id: int, user_id: int) -> int | None:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == workflow_run_id).one()
        assignment = db.query(TaskAssignment).filter(TaskAssignment.id == assignment_id).one()
        task = db.query(Task).filter(Task.id == assignment.task_id).one()

        artifact = db.query(Artifact).filter(Artifact.task_id == task.id).order_by(Artifact.created_at.asc()).first()
        artifact_text = artifact.content if artifact else ""

        if task.kind == TaskKind.PLAN and run.status == WorkflowStatus.PLANNING:
            return self._handle_plan_completed(db=db, run=run, task=task, artifact_text=artifact_text, user_id=user_id)

        if run.status in (WorkflowStatus.RUNNING, WorkflowStatus.AWAITING_APPROVAL):
            return self._handle_generic_completed(db=db, run=run, task=task, assignment=assignment, artifact_text=artifact_text, user_id=user_id)

        return None

    def _handle_plan_completed(self, *, db: Session, run: WorkflowRun, task: Task, artifact_text: str, user_id: int) -> int | None:
        try:
            payload = json.loads(artifact_text)
        except json.JSONDecodeError:
            payload = {"steps": [{"kind": TaskKind.RESEARCH.value, "objective": run.shared_context.get("goal", "Research context")}]}  # fallback

        steps = payload.get("steps") or []
        if not steps:
            # Fail early if the coordinator returned an empty plan.
            run.status = WorkflowStatus.FAILED
            run.error = "Coordinator produced no steps"
            db.add(run)
            log_event(
                db,
                workspace_id=run.workspace_id,
                workflow_run_id=run.id,
                user_id=user_id,
                event_type="workflow_failed",
                message="Workflow run failed: empty plan.",
            )
            db.commit()
            return None

        participants = (
            db.query(Agent)
            .join(WorkflowParticipant, WorkflowParticipant.agent_id == Agent.id)
            .filter(WorkflowParticipant.workflow_id == run.workflow_id)
            .filter(Agent.is_active == True)  # noqa: E712
            .all()
        )
        if not participants:
            run.status = WorkflowStatus.FAILED
            run.error = "No active agents in workflow participants"
            db.add(run)
            log_event(
                db,
                workspace_id=run.workspace_id,
                workflow_run_id=run.id,
                user_id=user_id,
                event_type="workflow_failed",
                message="Workflow run failed: no active participants.",
            )
            db.commit()
            return None

        created_tasks: list[Task] = []
        created_assignments: list[TaskAssignment] = []
        prev_task_id = task.id
        prev_agent_id = db.query(TaskAssignment).filter(TaskAssignment.task_id == task.id).one().agent_id

        for idx, step in enumerate(steps, start=1):
            step_kind = TaskKind(step["kind"])
            objective = step.get("objective") or f"Perform {step_kind.value}"

            new_task = Task(
                workflow_run_id=run.id,
                kind=step_kind,
                order_index=idx,
                objective=objective,
                status=TaskStatus.PENDING,
            )
            db.add(new_task)
            db.flush()  # obtain task.id

            agent = self._select_agent_for_step(participants=participants, step_kind=step_kind, run=run)
            assignment = TaskAssignment(task_id=new_task.id, agent_id=agent.id, status=AssignmentStatus.PENDING)
            db.add(assignment)
            db.flush()

            created_tasks.append(new_task)
            created_assignments.append(assignment)

            db.add(
                Handoff(
                    workflow_run_id=run.id,
                    from_task_id=prev_task_id,
                    to_task_id=new_task.id,
                    from_agent_id=prev_agent_id,
                    to_agent_id=agent.id,
                    metadata={"kind": "auto_handoff"},
                )
            )
            prev_task_id = new_task.id
            prev_agent_id = agent.id

        run.status = WorkflowStatus.RUNNING
        run.started_at = run.started_at or self._now()
        run.current_step_index = 1  # plan is step 0, first created is 1
        run.shared_context = {**(run.shared_context or {}), "plan": payload}
        db.add(run)

        first_assignment_id = created_assignments[0].id
        log_event(
            db,
            workspace_id=run.workspace_id,
            workflow_run_id=run.id,
            user_id=user_id,
            event_type="workflow_plan_created",
            message=f"Coordinator created plan with {len(steps)} steps.",
            metadata={"steps": [s.get("kind") for s in steps]},
        )
        log_event(
            db,
            workspace_id=run.workspace_id,
            workflow_run_id=run.id,
            user_id=user_id,
            event_type="handoff_performed",
            message=f"Handoff from {task.kind.value} to {created_tasks[0].kind.value}.",
            metadata={"from_task_id": task.id, "to_task_id": created_tasks[0].id},
        )
        db.commit()
        return first_assignment_id

    @staticmethod
    def _select_agent_for_step(*, participants: list[Agent], step_kind: TaskKind, run: WorkflowRun) -> Agent:
        # Basic role-based routing for a portfolio demo.
        def role_matches(agent: Agent, needle: str) -> bool:
            return needle in (agent.role_title or "").lower()

        if step_kind == TaskKind.RESEARCH:
            matches = [a for a in participants if role_matches(a, "research")]
        elif step_kind in (TaskKind.DRAFT, TaskKind.FINALIZE):
            matches = [a for a in participants if role_matches(a, "writer")]
        elif step_kind == TaskKind.REVIEW:
            matches = [a for a in participants if role_matches(a, "review")]
        else:
            matches = []

        if matches:
            return matches[0]

        # Fallback: pick the most recently created active participant.
        return sorted(participants, key=lambda a: a.created_at, reverse=True)[0]

    def _handle_generic_completed(
        self,
        *,
        db: Session,
        run: WorkflowRun,
        task: Task,
        assignment: TaskAssignment,
        artifact_text: str,
        user_id: int,
    ) -> int | None:
        # Persist outputs into shared_context for later tasks.
        ctx = dict(run.shared_context or {})
        if task.kind == TaskKind.RESEARCH:
            ctx["research_notes"] = artifact_text
        elif task.kind == TaskKind.DRAFT:
            ctx["draft"] = artifact_text
        elif task.kind == TaskKind.REVIEW:
            ctx["review"] = artifact_text
            try:
                review_payload = json.loads(artifact_text)
            except json.JSONDecodeError:
                review_payload = {}
            if not review_payload.get("approved", True):
                ctx["revision_notes"] = review_payload.get("revision_notes") or "Revisions requested by reviewer."
        elif task.kind == TaskKind.FINALIZE:
            ctx["final_deliverable"] = artifact_text

        run.shared_context = ctx

        # Find next pending step in order.
        next_task = (
            db.query(Task)
            .filter(Task.workflow_run_id == run.id, Task.order_index > task.order_index)
            .order_by(Task.order_index.asc())
            .first()
        )

        if not next_task:
            if task.kind == TaskKind.FINALIZE:
                run.status = WorkflowStatus.COMPLETED
                run.completed_at = self._now()
                log_event(
                    db,
                    workspace_id=run.workspace_id,
                    workflow_run_id=run.id,
                    user_id=user_id,
                    event_type="workflow_completed",
                    message="Workflow run completed successfully.",
                )
                db.add(run)
                db.commit()
            else:
                # No next task exists; mark as failed to keep operational clarity.
                run.status = WorkflowStatus.FAILED
                run.error = f"No next task found after completed task: {task.kind.value}"
                log_event(
                    db,
                    workspace_id=run.workspace_id,
                    workflow_run_id=run.id,
                    user_id=user_id,
                    event_type="workflow_failed",
                    message=run.error,
                )
                db.add(run)
                db.commit()
            return None

        next_assignment = db.query(TaskAssignment).filter(TaskAssignment.task_id == next_task.id).one()

        # Approval checkpoint between review and finalization.
        if task.kind == TaskKind.REVIEW and next_task.kind == TaskKind.FINALIZE and run.human_approval_required:
            existing = (
                db.query(Approval)
                .filter(
                    Approval.workflow_run_id == run.id,
                    Approval.checkpoint_kind == CheckpointKind.FINAL_DELIVERABLE,
                    Approval.status == ApprovalStatus.PENDING,
                )
                .first()
            )
            if not existing:
                review_notes = None
                try:
                    review_payload = json.loads(artifact_text)
                    review_notes = review_payload.get("revision_notes")
                except json.JSONDecodeError:
                    pass

                approval = Approval(
                    workflow_run_id=run.id,
                    checkpoint_kind=CheckpointKind.FINAL_DELIVERABLE,
                    status=ApprovalStatus.PENDING,
                    notes=review_notes,
                )
                db.add(approval)

                log_event(
                    db,
                    workspace_id=run.workspace_id,
                    workflow_run_id=run.id,
                    user_id=user_id,
                    event_type="approval_requested",
                    message="Human approval requested before final deliverable.",
                    metadata={"checkpoint_kind": CheckpointKind.FINAL_DELIVERABLE.value},
                )

            run.status = WorkflowStatus.AWAITING_APPROVAL
            run.current_step_index = next_task.order_index
            db.add(run)
            db.commit()
            return None

        # Schedule next task.
        run.status = WorkflowStatus.RUNNING
        run.current_step_index = next_task.order_index
        db.add(run)

        db.add(
            Handoff(
                workflow_run_id=run.id,
                from_task_id=task.id,
                to_task_id=next_task.id,
                from_agent_id=assignment.agent_id,
                to_agent_id=next_assignment.agent_id,
                metadata={"kind": "auto_handoff"},
            )
        )
        log_event(
            db,
            workspace_id=run.workspace_id,
            workflow_run_id=run.id,
            user_id=user_id,
            event_type="handoff_performed",
            message=f"Handoff from {task.kind.value} to {next_task.kind.value}.",
            metadata={"from_task_id": task.id, "to_task_id": next_task.id},
        )

        db.commit()
        return next_assignment.id

    def on_approval_decision(
        self, *, db: Session, workflow_run_id: int, approval_id: int, approved: bool, user_id: int, notes: str | None = None
    ) -> int | None:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == workflow_run_id).one()
        approval = db.query(Approval).filter(Approval.id == approval_id, Approval.workflow_run_id == workflow_run_id).one()

        if approval.status != ApprovalStatus.PENDING:
            return None

        approval.decided_at = self._now()
        approval.notes = notes if notes else approval.notes
        approval.status = ApprovalStatus.GRANTED if approved else ApprovalStatus.REJECTED

        if not approved:
            run.status = WorkflowStatus.FAILED
            run.completed_at = self._now()
            run.error = "Human rejected approval checkpoint."

            log_event(
                db,
                workspace_id=run.workspace_id,
                workflow_run_id=run.id,
                user_id=user_id,
                event_type="approval_rejected",
                message="Approval checkpoint rejected by human.",
            )
            db.add(approval)
            db.add(run)
            db.commit()
            return None

        log_event(
            db,
            workspace_id=run.workspace_id,
            workflow_run_id=run.id,
            user_id=user_id,
            event_type="approval_granted",
            message="Approval checkpoint granted by human.",
        )

        # Continue to finalize step.
        finalize_task = (
            db.query(Task)
            .filter(Task.workflow_run_id == run.id, Task.kind == TaskKind.FINALIZE)
            .order_by(Task.order_index.asc())
            .first()
        )
        if not finalize_task:
            run.status = WorkflowStatus.COMPLETED
            run.completed_at = self._now()
            db.add(run)
            db.commit()
            return None

        finalize_assignment = db.query(TaskAssignment).filter(TaskAssignment.task_id == finalize_task.id).one()

        # Record handoff from the latest completed task.
        prev_task = (
            db.query(Task)
            .filter(Task.workflow_run_id == run.id, Task.order_index < finalize_task.order_index)
            .order_by(Task.order_index.desc())
            .first()
        )
        prev_assignment = db.query(TaskAssignment).filter(TaskAssignment.task_id == prev_task.id).one() if prev_task else None

        run.status = WorkflowStatus.RUNNING
        run.current_step_index = finalize_task.order_index
        db.add(run)

        if prev_assignment:
            db.add(
                Handoff(
                    workflow_run_id=run.id,
                    from_task_id=prev_task.id,
                    to_task_id=finalize_task.id,
                    from_agent_id=prev_assignment.agent_id,
                    to_agent_id=finalize_assignment.agent_id,
                    metadata={"kind": "approval_resume"},
                )
            )

            log_event(
                db,
                workspace_id=run.workspace_id,
                workflow_run_id=run.id,
                user_id=user_id,
                event_type="handoff_performed",
                message=f"Handoff resumed after approval to {finalize_task.kind.value}.",
                metadata={"from_task_id": prev_task.id if prev_task else None, "to_task_id": finalize_task.id},
            )

        db.commit()
        return finalize_assignment.id

    @staticmethod
    def _now():
        from datetime import datetime

        return datetime.utcnow()

