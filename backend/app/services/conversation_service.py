from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.entities import (
    Agent,
    ChannelBinding,
    ChannelKind,
    Conversation,
    ConversationParticipant,
    ConversationStatus,
    ConversationType,
    DeliveryStatus,
    Message,
    MessageChannel,
    MessageDirection,
    MessageProvider,
    MessageSenderType,
    ParticipantType,
    WorkflowRun,
    Workspace,
)


def list_conversations_for_workspace(db: Session, *, workspace_id: int, limit: int = 50) -> list[Conversation]:
    return (
        db.query(Conversation)
        .filter(Conversation.workspace_id == workspace_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .all()
    )


def create_conversation(
    db: Session,
    *,
    workspace_id: int,
    title: str | None,
    conv_type: ConversationType,
) -> Conversation:
    c = Conversation(
        workspace_id=workspace_id,
        type=conv_type,
        title=title,
        status=ConversationStatus.OPEN,
    )
    db.add(c)
    db.flush()
    db.add(
        ConversationParticipant(
            conversation_id=c.id,
            participant_type=ParticipantType.SYSTEM,
            role="creator",
        )
    )
    return c


def list_messages(db: Session, *, conversation_id: int, limit: int = 100) -> list[Message]:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .all()
    )


def append_web_message(
    db: Session,
    *,
    conversation_id: int,
    user_id: int,
    body_text: str,
    body_structured: dict | None,
) -> Message:
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).one()
    conv.updated_at = datetime.utcnow()
    db.add(conv)

    m = Message(
        conversation_id=conversation_id,
        sender_type=MessageSenderType.USER,
        sender_id=user_id,
        body_text=body_text,
        body_structured=body_structured,
        direction=MessageDirection.INBOUND,
        channel=MessageChannel.WEB,
        provider=MessageProvider.NONE,
        delivery_status=DeliveryStatus.DELIVERED,
    )
    db.add(m)
    return m


def build_conversation_detail(
    db: Session,
    *,
    conversation_id: int,
) -> tuple[Conversation, str, int | None, str | None, WorkflowRun | None]:
    """
    Returns conversation, primary_channel, binding_agent_id, binding_agent_name, linked_workflow_run.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).one()
    binding = db.query(ChannelBinding).filter(ChannelBinding.conversation_id == conversation_id).first()

    primary_channel = "web"
    agent_id: int | None = None
    agent_name: str | None = None
    if binding and binding.channel == ChannelKind.WHATSAPP:
        primary_channel = "whatsapp"
        agent_id = binding.agent_id
        if binding.agent_id:
            ag = db.query(Agent).filter(Agent.id == binding.agent_id).one_or_none()
            if ag:
                agent_name = ag.name

    run: WorkflowRun | None = None
    if conv.linked_workflow_run_id:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == conv.linked_workflow_run_id).one_or_none()

    return conv, primary_channel, agent_id, agent_name, run


def assert_workspace_access(db: Session, *, workspace_id: int, user_id: int) -> Workspace:
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).one()
    if ws.user_id != user_id:
        raise HTTPException(status_code=403, detail="Workspace does not belong to user")
    return ws
