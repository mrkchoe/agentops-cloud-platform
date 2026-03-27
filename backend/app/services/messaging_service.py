from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
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
    Workspace,
)
from app.services.channels import SendContext, get_whatsapp_adapter
from app.services.llm import get_provider


def resolve_default_workspace_id(db: Session) -> int | None:
    if settings.default_whatsapp_workspace_id is not None:
        return int(settings.default_whatsapp_workspace_id)
    ws = db.query(Workspace).order_by(Workspace.id.asc()).first()
    return ws.id if ws else None


def select_target_agent(
    db: Session,
    *,
    workspace_id: int,
    binding_agent_id: int | None,
) -> Agent | None:
    if binding_agent_id:
        a = db.query(Agent).filter(Agent.id == binding_agent_id, Agent.workspace_id == workspace_id).one_or_none()
        if a and a.is_active:
            return a
    if settings.default_whatsapp_agent_id is not None:
        a = db.query(Agent).filter(
            Agent.id == settings.default_whatsapp_agent_id,
            Agent.workspace_id == workspace_id,
        ).one_or_none()
        if a and a.is_active:
            return a
    agents = (
        db.query(Agent)
        .filter(Agent.workspace_id == workspace_id, Agent.is_active == True)  # noqa: E712
        .order_by(Agent.id.asc())
        .all()
    )
    for a in agents:
        if "coordinator" in (a.role_title or "").lower():
            return a
    return agents[0] if agents else None


def get_or_create_channel_binding(
    db: Session,
    *,
    workspace_id: int,
    provider: MessageProvider,
    external_user_address: str,
    agent_id: int | None = None,
) -> tuple[ChannelBinding, Conversation, bool]:
    """Return binding, conversation, created_new_binding."""
    existing = (
        db.query(ChannelBinding)
        .filter(
            ChannelBinding.workspace_id == workspace_id,
            ChannelBinding.provider == provider,
            ChannelBinding.external_user_address == external_user_address,
        )
        .one_or_none()
    )
    if existing:
        conv = db.query(Conversation).filter(Conversation.id == existing.conversation_id).one()
        return existing, conv, False

    conv = Conversation(
        workspace_id=workspace_id,
        type=ConversationType.DIRECT,
        title=f"WhatsApp {external_user_address}",
        status=ConversationStatus.OPEN,
    )
    db.add(conv)
    db.flush()

    db.add(
        ConversationParticipant(
            conversation_id=conv.id,
            participant_type=ParticipantType.EXTERNAL,
            external_address=external_user_address,
            role="whatsapp_user",
        )
    )

    binding = ChannelBinding(
        workspace_id=workspace_id,
        channel=ChannelKind.WHATSAPP,
        provider=provider,
        external_user_address=external_user_address,
        conversation_id=conv.id,
        agent_id=agent_id,
    )
    db.add(binding)
    db.flush()
    return binding, conv, True


def append_inbound_message(
    db: Session,
    *,
    conversation_id: int,
    text: str,
    provider: MessageProvider,
    provider_message_id: str,
    external_address: str,
    raw_payload: dict[str, Any],
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        sender_type=MessageSenderType.EXTERNAL,
        external_sender_address=external_address,
        body_text=text,
        body_structured={"raw": raw_payload},
        direction=MessageDirection.INBOUND,
        channel=MessageChannel.WHATSAPP,
        provider=provider,
        provider_message_id=provider_message_id,
        delivery_status=DeliveryStatus.DELIVERED,
    )
    db.add(msg)
    return msg


def build_conversational_messages(*, agent: Agent, user_text: str, prior_snippets: list[str]) -> list[dict[str, str]]:
    system = (
        f"You are {agent.name} ({agent.role_title}) assisting over WhatsApp.\n"
        f"{agent.description}\n{agent.system_instructions}\n"
        "Respond with a JSON object only, keys: reply (string), start_workflow (boolean), "
        "workflow_id (integer or null), reason (string, optional). "
        "Set start_workflow true only when the user clearly needs a multi-step automated workflow run."
    )
    history = "\n".join(prior_snippets[-12:]) if prior_snippets else ""
    user = f"User message:\n{user_text}\n\nRecent transcript (may be empty):\n{history}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_conversational_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"reply": text[:4000], "start_workflow": False, "workflow_id": None}


@retry(wait=wait_exponential(multiplier=0.5, min=0.5, max=8), stop=stop_after_attempt(3))
async def send_whatsapp_text_with_retry(
    *,
    to_address: str,
    body: str,
    context: SendContext,
) -> Any:
    adapter = get_whatsapp_adapter()
    return await adapter.send_text(to_address, body, context)


async def deliver_outbound_whatsapp(
    *,
    to_address: str,
    body: str,
    context: SendContext,
) -> tuple[bool, str | None, str | None]:
    """Returns ok, provider_message_id, error."""
    try:
        result = await send_whatsapp_text_with_retry(to_address=to_address, body=body, context=context)
        return result.ok, result.provider_message_id, result.error
    except Exception as e:
        return False, None, str(e)[:2000]


def record_outbound_message(
    db: Session,
    *,
    conversation_id: int,
    agent_id: int | None,
    body_text: str,
    body_structured: dict[str, Any] | None,
    provider: MessageProvider,
    reply_to_message_id: int | None,
    provider_message_id: str | None,
    delivery_status: DeliveryStatus,
    sender_type: MessageSenderType = MessageSenderType.AGENT,
    sender_id: int | None = None,
) -> Message:
    resolved_sender_id = sender_id if sender_id is not None else agent_id
    msg = Message(
        conversation_id=conversation_id,
        sender_type=sender_type,
        sender_id=resolved_sender_id,
        body_text=body_text,
        body_structured=body_structured,
        direction=MessageDirection.OUTBOUND,
        channel=MessageChannel.WHATSAPP,
        provider=provider,
        provider_message_id=provider_message_id,
        reply_to_message_id=reply_to_message_id,
        delivery_status=delivery_status,
    )
    db.add(msg)
    db.flush()
    return msg


def find_prior_inbound_transcript(db: Session, conversation_id: int, limit: int = 20) -> list[str]:
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    lines: list[str] = []
    for m in reversed(rows):
        prefix = "user" if m.direction == MessageDirection.INBOUND else "assistant"
        lines.append(f"{prefix}: {m.body_text[:2000]}")
    return lines


__all__ = [
    "append_inbound_message",
    "build_conversational_messages",
    "deliver_outbound_whatsapp",
    "find_prior_inbound_transcript",
    "get_or_create_channel_binding",
    "parse_conversational_json",
    "record_outbound_message",
    "resolve_default_workspace_id",
    "select_target_agent",
]
