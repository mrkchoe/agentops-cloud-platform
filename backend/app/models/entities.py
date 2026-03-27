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
    UniqueConstraint,
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


class ConversationType(str, enum.Enum):
    DIRECT = "direct"
    GROUP = "group"
    WORKFLOW_LINKED = "workflow_linked"


class ConversationStatus(str, enum.Enum):
    OPEN = "open"
    ARCHIVED = "archived"
    CLOSED = "closed"


class ParticipantType(str, enum.Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    EXTERNAL = "external"


class MessageSenderType(str, enum.Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    EXTERNAL = "external"


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


class MessageChannel(str, enum.Enum):
    WEB = "web"
    WHATSAPP = "whatsapp"
    SYSTEM = "system"


class MessageProvider(str, enum.Enum):
    TWILIO = "twilio"
    META = "meta"
    NONE = "none"


class DeliveryStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ChannelKind(str, enum.Enum):
    WHATSAPP = "whatsapp"


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
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="workspace")
    channel_bindings: Mapped[list["ChannelBinding"]] = relationship(back_populates="workspace")


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
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
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
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id"), index=True)
    workspace: Mapped["Workspace"] = relationship(back_populates="conversations")
    type: Mapped[ConversationType] = mapped_column(SAEnum(ConversationType), default=ConversationType.DIRECT, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(SAEnum(ConversationStatus), default=ConversationStatus.OPEN, index=True)
    linked_workflow_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workflow_runs.id"), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="conversations")
    participants: Mapped[list["ConversationParticipant"]] = relationship(back_populates="conversation")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")
    channel_bindings: Mapped[list["ChannelBinding"]] = relationship(back_populates="conversation")


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), index=True)
    participant_type: Mapped[ParticipantType] = mapped_column(SAEnum(ParticipantType), index=True)
    participant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    external_address: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    role: Mapped[str | None] = mapped_column(String(128), nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="participants")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), index=True)
    sender_type: Mapped[MessageSenderType] = mapped_column(SAEnum(MessageSenderType), index=True)
    sender_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    external_sender_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body_text: Mapped[str] = mapped_column(Text)
    body_structured: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    direction: Mapped[MessageDirection] = mapped_column(SAEnum(MessageDirection), index=True)
    channel: Mapped[MessageChannel] = mapped_column(SAEnum(MessageChannel), index=True)
    provider: Mapped[MessageProvider] = mapped_column(SAEnum(MessageProvider), index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    reply_to_message_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("messages.id"), nullable=True)
    delivery_status: Mapped[DeliveryStatus | None] = mapped_column(SAEnum(DeliveryStatus), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (UniqueConstraint("provider", "provider_message_id", name="uq_message_provider_msg_id"),)


class ChannelBinding(Base):
    __tablename__ = "channel_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id"), index=True)
    channel: Mapped[ChannelKind] = mapped_column(SAEnum(ChannelKind), index=True)
    provider: Mapped[MessageProvider] = mapped_column(SAEnum(MessageProvider), index=True)
    external_user_address: Mapped[str] = mapped_column(String(512), index=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), index=True)
    agent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("agents.id"), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="channel_bindings")
    conversation: Mapped["Conversation"] = relationship(back_populates="channel_bindings")

    __table_args__ = (
        UniqueConstraint("workspace_id", "provider", "external_user_address", name="uq_channel_binding_workspace_provider_address"),
    )


class StatusCallbackDedupe(Base):
    """Idempotency for provider status webhooks (Twilio/Meta)."""

    __tablename__ = "status_callback_dedupe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[MessageProvider] = mapped_column(SAEnum(MessageProvider), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
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
        Conversation,
        ConversationParticipant,
        Message,
        ChannelBinding,
        StatusCallbackDedupe,
    ]

