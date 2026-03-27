from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id, workspace_user_scope
from app.db.session import get_db
from app.models.entities import (
    Agent,
    AgentTemplate,
    Approval,
    ApprovalStatus,
    Artifact,
    CheckpointKind,
    Task,
    TaskAssignment,
    Workflow,
    WorkflowParticipant,
    WorkflowRun,
    Workspace,
    ActivityLog,
)
from app.schemas.schemas import (
    AgentCreateIn,
    AgentOut,
    AgentTemplateOut,
    AgentUpdateIn,
    ApprovalDecisionIn,
    ApprovalOut,
    ActivityLogOut,
    TaskAssignmentOut,
    TaskOut,
    ArtifactOut,
    WorkflowCreateIn,
    WorkflowOut,
    WorkflowRunCreateResponse,
    WorkflowRunDetailOut,
    WorkflowRunOut,
    WorkspaceCreateIn,
    WorkspaceOut,
)
from app.services.workflow_orchestrator import WorkflowOrchestrator
from app.services.activity_log import log_event
from app.api.v1.messaging_routes import router as messaging_router


router = APIRouter(prefix="/api/v1")
router.include_router(messaging_router)


@router.get("/agent-templates", response_model=list[AgentTemplateOut])
def list_agent_templates(db: Session = Depends(get_db)) -> list[AgentTemplateOut]:
    templates = db.query(AgentTemplate).filter(AgentTemplate.is_active == True).order_by(AgentTemplate.id.asc()).all()  # noqa: E712
    return templates


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[WorkspaceOut]:
    workspaces = db.query(Workspace).filter(Workspace.user_id == user_id).order_by(Workspace.created_at.desc()).all()
    return workspaces


@router.post("/workspaces", response_model=WorkspaceOut)
def create_workspace(
    payload: WorkspaceCreateIn,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    ws = Workspace(user_id=user_id, name=payload.name)
    db.add(ws)
    db.commit()
    db.refresh(ws)

    log_event(
        db,
        workspace_id=ws.id,
        workflow_run_id=None,
        user_id=user_id,
        event_type="workspace_created",
        message=f"Workspace created: {ws.name}",
    )
    db.commit()
    return ws


@router.get("/workspaces/{workspace_id}/agents", response_model=list[AgentOut])
def list_agents(
    workspace_id: int,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[AgentOut]:
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).one()
    workspace_user_scope(ws.user_id, user_id)
    agents = db.query(Agent).filter(Agent.workspace_id == workspace_id).order_by(Agent.id.asc()).all()
    return agents


@router.post("/workspaces/{workspace_id}/agents", response_model=AgentOut)
def create_custom_agent(
    workspace_id: int,
    payload: AgentCreateIn,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AgentOut:
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).one()
    workspace_user_scope(ws.user_id, user_id)

    agent = Agent(
        workspace_id=workspace_id,
        agent_template_id=None,
        name=payload.name,
        role_title=payload.role_title,
        description=payload.description,
        system_instructions=payload.system_instructions,
        allowed_tools=payload.allowed_tools,
        allowed_handoff_targets=payload.allowed_handoff_targets,
        output_format_hint=payload.output_format_hint,
        approval_required=payload.approval_required,
        is_active=payload.is_active,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    log_event(
        db,
        workspace_id=workspace_id,
        workflow_run_id=None,
        user_id=user_id,
        event_type="agent_created",
        message=f"Custom agent created: {agent.name}",
        metadata={"agent_id": agent.id},
    )
    db.commit()
    return agent


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: int,
    payload: AgentUpdateIn,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AgentOut:
    agent = db.query(Agent).filter(Agent.id == agent_id).one()
    ws = db.query(Workspace).filter(Workspace.id == agent.workspace_id).one()
    workspace_user_scope(ws.user_id, user_id)

    agent.is_active = payload.is_active
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/workspaces/{workspace_id}/workflows", response_model=list[WorkflowOut])
def list_workflows(
    workspace_id: int,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[WorkflowOut]:
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).one()
    workspace_user_scope(ws.user_id, user_id)
    workflows = db.query(Workflow).filter(Workflow.workspace_id == workspace_id).order_by(Workflow.created_at.desc()).all()
    return workflows


@router.get("/workspaces/{workspace_id}/workflow-runs", response_model=list[WorkflowRunOut])
def list_workflow_runs(
    workspace_id: int,
    limit: int = 20,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[WorkflowRunOut]:
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).one()
    workspace_user_scope(ws.user_id, user_id)
    limit = max(1, min(limit, 100))
    runs = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.workspace_id == workspace_id)
        .order_by(WorkflowRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return runs


@router.post("/workspaces/{workspace_id}/workflows", response_model=WorkflowOut)
def create_workflow(
    workspace_id: int,
    payload: WorkflowCreateIn,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WorkflowOut:
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).one()
    workspace_user_scope(ws.user_id, user_id)

    # Validate participant agents belong to the workspace.
    participants = db.query(Agent).filter(Agent.id.in_(payload.participant_agent_ids), Agent.workspace_id == workspace_id).all()
    if len(participants) != len(payload.participant_agent_ids):
        raise HTTPException(status_code=400, detail="One or more participant agents are invalid for this workspace")

    workflow = Workflow(
        workspace_id=workspace_id,
        name=payload.name,
        goal=payload.goal,
        require_human_approval=payload.require_human_approval,
    )
    db.add(workflow)
    db.flush()

    for agent in participants:
        db.add(WorkflowParticipant(workflow_id=workflow.id, agent_id=agent.id))

    db.commit()
    db.refresh(workflow)
    return workflow


@router.post("/workflows/{workflow_id}/runs", response_model=WorkflowRunCreateResponse)
def start_workflow_run(
    workflow_id: int,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WorkflowRunCreateResponse:
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).one()
    ws = db.query(Workspace).filter(Workspace.id == workflow.workspace_id).one()
    workspace_user_scope(ws.user_id, user_id)

    orchestrator = WorkflowOrchestrator()
    run_id = orchestrator.start_workflow_run(db=db, workflow_id=workflow_id, user_id=user_id)
    return WorkflowRunCreateResponse(run_id=run_id)


@router.get("/workflow-runs/{run_id}", response_model=WorkflowRunDetailOut)
def get_workflow_run_detail(
    run_id: int,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WorkflowRunDetailOut:
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).one()
    ws = db.query(Workspace).filter(Workspace.id == run.workspace_id).one()
    workspace_user_scope(ws.user_id, user_id)

    tasks = db.query(Task).filter(Task.workflow_run_id == run.id).order_by(Task.order_index.asc()).all()
    task_ids = [t.id for t in tasks]
    assignments = db.query(TaskAssignment).filter(TaskAssignment.task_id.in_(task_ids)).order_by(TaskAssignment.id.asc()).all()
    artifacts = db.query(Artifact).filter(Artifact.task_id.in_(task_ids)).order_by(Artifact.created_at.asc()).all()
    approvals = db.query(Approval).filter(Approval.workflow_run_id == run.id).order_by(Approval.id.asc()).all()
    activity_logs = db.query(ActivityLog).filter(ActivityLog.workflow_run_id == run.id).order_by(ActivityLog.created_at.asc()).all()

    # Pydantic response assembly
    return WorkflowRunDetailOut(
        run=run,
        tasks=tasks,
        assignments=assignments,
        artifacts=artifacts,
        approvals=approvals,
        activity_logs=activity_logs,
    )


@router.post("/workflow-runs/{run_id}/approvals/{approval_id}/decision")
def decide_approval(
    run_id: int,
    approval_id: int,
    payload: ApprovalDecisionIn,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).one()
    ws = db.query(Workspace).filter(Workspace.id == run.workspace_id).one()
    workspace_user_scope(ws.user_id, user_id)

    approval = db.query(Approval).filter(Approval.id == approval_id, Approval.workflow_run_id == run_id).one()
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail="Approval checkpoint is not pending")

    orchestrator = WorkflowOrchestrator()
    orchestrator.decide_approval(
        db=db,
        workflow_run_id=run_id,
        approval_id=approval_id,
        approved=payload.approved,
        notes=payload.notes,
        user_id=user_id,
    )
    return {"ok": True}


@router.get("/activity-logs", response_model=list[ActivityLogOut])
def list_activity_logs(
    limit: int = 50,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[ActivityLogOut]:
    limit = max(1, min(limit, 200))
    logs = db.query(ActivityLog).filter(ActivityLog.user_id == user_id).order_by(ActivityLog.created_at.desc()).limit(limit).all()
    return list(reversed(logs))

