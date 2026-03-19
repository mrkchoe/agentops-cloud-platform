from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.entities import (
    ArtifactKind,
    ApprovalStatus,
    CheckpointKind,
    TaskKind,
    TaskStatus,
    AssignmentStatus,
    WorkflowStatus,
)


class AgentTemplateOut(BaseModel):
    id: int
    name: str
    role_title: str
    description: str
    system_instructions: str
    allowed_tools: dict[str, Any] = Field(default_factory=dict)
    allowed_handoff_targets: list[str] = Field(default_factory=list)
    output_format_hint: str
    approval_required: bool
    is_active: bool

    model_config = {"from_attributes": True}


class AgentOut(BaseModel):
    id: int
    workspace_id: int
    # SQLAlchemy model field is named `agent_template_id`.
    template_id: int | None = Field(default=None, alias="agent_template_id")
    name: str
    role_title: str
    description: str
    output_format_hint: str
    approval_required: bool
    is_active: bool

    model_config = {"from_attributes": True, "populate_by_name": True}


class AgentCreateIn(BaseModel):
    name: str
    role_title: str
    description: str
    system_instructions: str
    allowed_tools: dict[str, Any] = Field(default_factory=dict)
    allowed_handoff_targets: list[str] = Field(default_factory=list)
    output_format_hint: str
    approval_required: bool = False
    is_active: bool = True


class AgentUpdateIn(BaseModel):
    is_active: bool


class WorkspaceOut(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceCreateIn(BaseModel):
    name: str


class WorkflowOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    goal: str
    require_human_approval: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowCreateIn(BaseModel):
    name: str
    goal: str
    participant_agent_ids: list[int]
    require_human_approval: bool = True


class WorkflowRunCreateResponse(BaseModel):
    run_id: int


class TaskOut(BaseModel):
    id: int
    kind: TaskKind
    order_index: int
    objective: str
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    model_config = {"from_attributes": True}


class TaskAssignmentOut(BaseModel):
    id: int
    task_id: int
    agent_id: int
    status: AssignmentStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    model_config = {"from_attributes": True}


class ArtifactOut(BaseModel):
    id: int
    task_id: int
    agent_id: int
    kind: ArtifactKind
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalOut(BaseModel):
    id: int
    workflow_run_id: int
    checkpoint_kind: CheckpointKind
    status: ApprovalStatus
    requested_at: datetime
    decided_at: datetime | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class ApprovalDecisionIn(BaseModel):
    approved: bool
    notes: str | None = None


class ActivityLogOut(BaseModel):
    id: int
    workspace_id: int
    workflow_run_id: int | None = None
    user_id: int
    event_type: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowRunOut(BaseModel):
    id: int
    workflow_id: int
    workspace_id: int
    status: WorkflowStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    current_step_index: int
    human_approval_required: bool
    shared_context: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    model_config = {"from_attributes": True}


class WorkflowRunDetailOut(BaseModel):
    run: WorkflowRunOut
    tasks: list[TaskOut]
    assignments: list[TaskAssignmentOut]
    artifacts: list[ArtifactOut]
    approvals: list[ApprovalOut]
    activity_logs: list[ActivityLogOut]

