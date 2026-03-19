import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WorkflowStatus(str, enum.Enum):
    PLANNING = "planning"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskKind(str, enum.Enum):
    PLAN = "plan"
    RESEARCH = "research"
    DRAFT = "draft"
    REVIEW = "review"
    FINALIZE = "finalize"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AssignmentStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactKind(str, enum.Enum):
    PLANNING_NOTES = "planning_notes"
    RESEARCH_NOTES = "research_notes"
    DRAFT_MEMO = "draft_memo"
    REVIEW_REPORT = "review_report"
    FINAL_DELIVERABLE = "final_deliverable"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    GRANTED = "granted"
    REJECTED = "rejected"


class CheckpointKind(str, enum.Enum):
    FINAL_DELIVERABLE = "final_deliverable"


def utcnow() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    api_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="owner")


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    owner: Mapped["User"] = relationship(back_populates="workspaces")
    agents: Mapped[list["Agent"]] = relationship(back_populates="workspace")
    workflows: Mapped[list["Workflow"]] = relationship(back_populates="workspace")
    workflow_runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="workspace")


class AgentTemplate(Base):
    __tablename__ = "agent_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    role_title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    system_instructions: Mapped[str] = mapped_column(Text)
    allowed_tools: Mapped[dict] = mapped_column(JSON, default=dict)
    allowed_handoff_targets: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_format_hint: Mapped[str] = mapped_column(Text)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id"), index=True)
    agent_template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("agent_templates.id"), nullable=True)

    name: Mapped[str] = mapped_column(String(255))
    role_title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    system_instructions: Mapped[str] = mapped_column(Text)
    allowed_tools: Mapped[dict] = mapped_column(JSON, default=dict)
    allowed_handoff_targets: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_format_hint: Mapped[str] = mapped_column(Text)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="agents")


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    goal: Mapped[str] = mapped_column(Text)
    require_human_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="workflows")
    participants: Mapped[list["WorkflowParticipant"]] = relationship(back_populates="workflow")
    workflow_runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="workflow")


class WorkflowParticipant(Base):
    __tablename__ = "workflow_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflows.id"), index=True)
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id"), index=True)

    workflow: Mapped["Workflow"] = relationship(back_populates="participants")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflows.id"), index=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id"), index=True)

    status: Mapped[WorkflowStatus] = mapped_column(SAEnum(WorkflowStatus), default=WorkflowStatus.PLANNING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_step_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    human_approval_required: Mapped[bool] = mapped_column(Boolean, default=True)
    shared_context: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow: Mapped["Workflow"] = relationship(back_populates="workflow_runs")
    workspace: Mapped["Workspace"] = relationship(back_populates="workflow_runs")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_runs.id"), index=True)
    kind: Mapped[TaskKind] = mapped_column(SAEnum(TaskKind), index=True)
    order_index: Mapped[int] = mapped_column(Integer, index=True)
    objective: Mapped[str] = mapped_column(Text)

    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), index=True)
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id"), index=True)

    status: Mapped[AssignmentStatus] = mapped_column(SAEnum(AssignmentStatus), default=AssignmentStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Handoff(Base):
    __tablename__ = "handoffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_runs.id"), index=True)
    from_task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), index=True)
    to_task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), index=True)
    from_agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id"), index=True)
    to_agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id"), index=True)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), index=True)
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id"), index=True)
    kind: Mapped[ArtifactKind] = mapped_column(SAEnum(ArtifactKind), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("workflow_runs.id"), index=True)
    checkpoint_kind: Mapped[CheckpointKind] = mapped_column(SAEnum(CheckpointKind), index=True)
    status: Mapped[ApprovalStatus] = mapped_column(SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id"), index=True)
    workflow_run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("workflow_runs.id"), index=True, nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)

    event_type: Mapped[str] = mapped_column(String(100), index=True)
    message: Mapped[str] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


def model_classes() -> list[type[Base]]:
    return [
        User,
        Workspace,
        AgentTemplate,
        Agent,
        Workflow,
        WorkflowParticipant,
        WorkflowRun,
        Task,
        TaskAssignment,
        Handoff,
        Artifact,
        Approval,
        ActivityLog,
    ]

