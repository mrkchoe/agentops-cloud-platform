import json

from sqlalchemy.orm import Session

from app.models.entities import (
    Agent,
    AgentTemplate,
    Artifact,
    ArtifactKind,
    Approval,
    ApprovalStatus,
    CheckpointKind,
    AssignmentStatus,
    Task,
    TaskAssignment,
    TaskKind,
    TaskStatus,
    User,
    Workspace,
    Workflow,
    WorkflowParticipant,
    WorkflowRun,
    WorkflowStatus,
    ActivityLog,
)
from app.services.activity_log import log_event


DEFAULT_TEMPLATES: list[dict] = [
    {
        "name": "Coordinator",
        "role_title": "Coordinator",
        "description": "Orchestrates the workflow plan and routes steps to other agents.",
        "system_instructions": "You are the Coordinator. Break down the goal into step-by-step tasks and route them to specialized agents.",
        "allowed_tools": {},
        "allowed_handoff_targets": ["Research Analyst", "Writer", "Reviewer"],
        "output_format_hint": "Return JSON with a list of steps: kind, objective.",
        "approval_required": False,
        "is_active": True,
    },
    {
        "name": "Research Analyst",
        "role_title": "Research Analyst",
        "description": "Gathers context and produces structured research notes.",
        "system_instructions": "You are the Research Analyst. Produce research notes as structured JSON-like output.",
        "allowed_tools": {},
        "allowed_handoff_targets": ["Writer", "Reviewer"],
        "output_format_hint": "Return JSON with key_points[] and open_questions[].",
        "approval_required": False,
        "is_active": True,
    },
    {
        "name": "Writer",
        "role_title": "Writer",
        "description": "Drafts and finalizes deliverables using approved context.",
        "system_instructions": "You are the Writer. Draft a polished memo/report and finalize after approval. Use markdown.",
        "allowed_tools": {},
        "allowed_handoff_targets": ["Reviewer"],
        "output_format_hint": "Return markdown text.",
        "approval_required": False,
        "is_active": True,
    },
    {
        "name": "Reviewer",
        "role_title": "Reviewer",
        "description": "Critiques quality and checks requirements; requests revisions if needed.",
        "system_instructions": "You are the Reviewer. Validate requirements and respond with JSON {approved, issues[], revision_notes}.",
        "allowed_tools": {},
        "allowed_handoff_targets": ["Writer"],
        "output_format_hint": "Return JSON with approved boolean and revision_notes.",
        "approval_required": True,
        "is_active": True,
    },
]


def seed_demo(db: Session) -> None:
    # 1) Templates
    existing_templates = db.query(AgentTemplate).count()
    if existing_templates == 0:
        for t in DEFAULT_TEMPLATES:
            db.add(
                AgentTemplate(
                    name=t["name"],
                    role_title=t["role_title"],
                    description=t["description"],
                    system_instructions=t["system_instructions"],
                    allowed_tools=t["allowed_tools"],
                    allowed_handoff_targets=t["allowed_handoff_targets"],
                    output_format_hint=t["output_format_hint"],
                    approval_required=t["approval_required"],
                    is_active=t["is_active"],
                )
            )
        db.commit()

    # 2) Demo user + workspace
    user = db.query(User).filter(User.email == "demo@agentops.local").one_or_none()
    if not user:
        user = User(email="demo@agentops.local", api_key="dev-demo-token")
        db.add(user)
        db.commit()
        db.refresh(user)

    workspace = db.query(Workspace).filter(Workspace.user_id == user.id, Workspace.name == "Demo Workspace").one_or_none()
    if not workspace:
        workspace = Workspace(user_id=user.id, name="Demo Workspace")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        log_event(
            db,
            workspace_id=workspace.id,
            workflow_run_id=None,
            user_id=user.id,
            event_type="workspace_seeded",
            message="Seeded demo workspace.",
        )
        db.commit()

    # 3) Workspace agents cloned from templates
    templates = db.query(AgentTemplate).filter(AgentTemplate.is_active == True).all()  # noqa: E712
    for tmpl in templates:
        existing_agent = (
            db.query(Agent).filter(Agent.workspace_id == workspace.id, Agent.agent_template_id == tmpl.id).one_or_none()
        )
        if not existing_agent:
            db.add(
                Agent(
                    workspace_id=workspace.id,
                    agent_template_id=tmpl.id,
                    name=tmpl.name,
                    role_title=tmpl.role_title,
                    description=tmpl.description,
                    system_instructions=tmpl.system_instructions,
                    allowed_tools=tmpl.allowed_tools,
                    allowed_handoff_targets=tmpl.allowed_handoff_targets,
                    output_format_hint=tmpl.output_format_hint,
                    approval_required=tmpl.approval_required,
                    is_active=True,
                )
            )
    db.commit()

    # 4) Demo workflow + participants
    goal = "Design and implement a cloud-based multi-agent workflow platform with orchestration, shared state, approvals, and audit logging."
    workflow = db.query(Workflow).filter(Workflow.workspace_id == workspace.id, Workflow.name == "AgentOps Demo").one_or_none()
    if not workflow:
        workflow = Workflow(workspace_id=workspace.id, name="AgentOps Demo", goal=goal, require_human_approval=True)
        db.add(workflow)
        db.flush()

        agents_for_participants = db.query(Agent).filter(Agent.workspace_id == workspace.id, Agent.is_active == True).all()  # noqa: E712
        for agent in agents_for_participants:
            db.add(WorkflowParticipant(workflow_id=workflow.id, agent_id=agent.id))
        db.commit()
        db.refresh(workflow)

    # 5) Seed one workflow run awaiting approval (after review)
    run = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.workspace_id == workspace.id, WorkflowRun.workflow_id == workflow.id)
        .order_by(WorkflowRun.created_at.desc())
        .first()
    )
    if run:
        return

    run = WorkflowRun(
        workflow_id=workflow.id,
        workspace_id=workspace.id,
        status=WorkflowStatus.AWAITING_APPROVAL,
        current_step_index=4,
        human_approval_required=True,
        shared_context={"goal": workflow.goal},
    )
    db.add(run)
    db.flush()

    # Create tasks + assignments + artifacts
    coordinator = db.query(Agent).filter(Agent.workspace_id == workspace.id, Agent.role_title == "Coordinator").one()
    research = db.query(Agent).filter(Agent.workspace_id == workspace.id, Agent.role_title == "Research Analyst").one()
    writer = db.query(Agent).filter(Agent.workspace_id == workspace.id, Agent.role_title == "Writer").one()
    reviewer = db.query(Agent).filter(Agent.workspace_id == workspace.id, Agent.role_title == "Reviewer").one()

    plan_task = Task(workflow_run_id=run.id, kind=TaskKind.PLAN, order_index=0, objective=workflow.goal, status=TaskStatus.COMPLETED)
    db.add(plan_task)
    db.flush()
    plan_assignment = TaskAssignment(task_id=plan_task.id, agent_id=coordinator.id, status=AssignmentStatus.COMPLETED)
    db.add(plan_assignment)
    db.flush()
    plan_artifact = Artifact(
        task_id=plan_task.id,
        agent_id=coordinator.id,
        kind=ArtifactKind.PLANNING_NOTES,
        content=json.dumps(
            {
                "steps": [
                    {"kind": TaskKind.RESEARCH.value, "objective": "Collect context for the goal."},
                    {"kind": TaskKind.DRAFT.value, "objective": "Draft the report."},
                    {"kind": TaskKind.REVIEW.value, "objective": "Review for requirements and quality."},
                    {"kind": TaskKind.FINALIZE.value, "objective": "Finalize after approval."},
                ]
            },
            indent=2,
        ),
    )
    db.add(plan_artifact)

    research_task = Task(workflow_run_id=run.id, kind=TaskKind.RESEARCH, order_index=1, objective="Collect context", status=TaskStatus.COMPLETED)
    db.add(research_task)
    db.flush()
    research_assignment = TaskAssignment(task_id=research_task.id, agent_id=research.id, status=AssignmentStatus.COMPLETED)
    db.add(research_assignment)
    db.flush()
    db.add(
        Artifact(
            task_id=research_task.id,
            agent_id=research.id,
            kind=ArtifactKind.RESEARCH_NOTES,
            content=json.dumps(
                {
                    "key_points": [
                        "Use Celery + Redis for async execution.",
                        "Persist shared state in Postgres per workflow run.",
                        "Store artifacts and activity logs for auditability.",
                    ],
                    "open_questions": ["Human approval gating strategy."],
                },
                indent=2,
            ),
        )
    )

    draft_task = Task(workflow_run_id=run.id, kind=TaskKind.DRAFT, order_index=2, objective="Draft deliverable", status=TaskStatus.COMPLETED)
    db.add(draft_task)
    db.flush()
    draft_assignment = TaskAssignment(task_id=draft_task.id, agent_id=writer.id, status=AssignmentStatus.COMPLETED)
    db.add(draft_assignment)
    db.flush()
    db.add(
        Artifact(
            task_id=draft_task.id,
            agent_id=writer.id,
            kind=ArtifactKind.DRAFT_MEMO,
            content="# Draft\nA draft memo is ready for review.\n",
        )
    )

    review_task = Task(workflow_run_id=run.id, kind=TaskKind.REVIEW, order_index=3, objective="Review draft", status=TaskStatus.COMPLETED)
    db.add(review_task)
    db.flush()
    review_assignment = TaskAssignment(task_id=review_task.id, agent_id=reviewer.id, status=AssignmentStatus.COMPLETED)
    db.add(review_assignment)
    db.flush()

    review_payload = {
        "approved": False,
        "issues": ["Ensure state transitions are explicit."],
        "revision_notes": "Update state machine handling and document audit log semantics.",
    }
    run.shared_context = {
        "goal": workflow.goal,
        "review": json.dumps(review_payload, indent=2),
        "revision_notes": review_payload["revision_notes"],
    }
    db.add(
        Artifact(
            task_id=review_task.id,
            agent_id=reviewer.id,
            kind=ArtifactKind.REVIEW_REPORT,
            content=json.dumps(review_payload, indent=2),
        )
    )

    finalize_task = Task(workflow_run_id=run.id, kind=TaskKind.FINALIZE, order_index=4, objective="Finalize deliverable", status=TaskStatus.PENDING)
    db.add(finalize_task)
    db.flush()
    finalize_assignment = TaskAssignment(task_id=finalize_task.id, agent_id=writer.id, status=AssignmentStatus.PENDING)
    db.add(finalize_assignment)

    approval = Approval(
        workflow_run_id=run.id,
        checkpoint_kind=CheckpointKind.FINAL_DELIVERABLE,
        status=ApprovalStatus.PENDING,
        notes="Revision requested by reviewer before final output.",
    )
    db.add(approval)

    # Audit trail (minimal but meaningful)
    log_event(
        db,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        user_id=user.id,
        event_type="workflow_run_seeded",
        message="Seeded workflow run awaiting final approval.",
    )
    log_event(
        db,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        user_id=user.id,
        event_type="approval_requested",
        message="Human approval requested before final deliverable.",
    )

    db.commit()

