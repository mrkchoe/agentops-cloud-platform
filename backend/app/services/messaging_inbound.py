from __future__ import annotations

import asyncio
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import (
    ChannelBinding,
    Conversation,
    ConversationType,
    DeliveryStatus,
    Message,
    MessageDirection,
    MessageProvider,
    Workflow,
    Workspace,
)
from app.services.activity_log import log_event
from app.services.channels import SendContext
from app.services.llm import get_provider
from app.services.messaging_service import (
    build_conversational_messages,
    deliver_outbound_whatsapp,
    find_prior_inbound_transcript,
    parse_conversational_json,
    record_outbound_message,
    select_target_agent,
)
from app.services.workflow_orchestrator import WorkflowOrchestrator


def _duplicate_outbound_exists(db: Session, inbound_message_id: int) -> bool:
    q = (
        db.query(Message)
        .filter(
            Message.reply_to_message_id == inbound_message_id,
            Message.direction == MessageDirection.OUTBOUND,
        )
        .first()
    )
    return q is not None


def process_inbound_whatsapp_message(db: Session, inbound_message_id: int) -> None:
    """
    Load inbound message, run conversational agent, optionally start workflow, send WhatsApp reply.
    Idempotent: if an outbound reply already exists for this inbound id, no-op.
    """
    inbound = db.query(Message).filter(Message.id == inbound_message_id).one()
    if inbound.direction != MessageDirection.INBOUND:
        return

    if _duplicate_outbound_exists(db, inbound.id):
        return

    conv = db.query(Conversation).filter(Conversation.id == inbound.conversation_id).one()
    ws = db.query(Workspace).filter(Workspace.id == conv.workspace_id).one()
    binding = (
        db.query(ChannelBinding)
        .filter(
            ChannelBinding.conversation_id == conv.id,
            ChannelBinding.provider == inbound.provider,
        )
        .first()
    )
    if not binding:
        binding = (
            db.query(ChannelBinding)
            .filter(
                ChannelBinding.workspace_id == conv.workspace_id,
                ChannelBinding.external_user_address == (inbound.external_sender_address or ""),
            )
            .first()
        )

    agent = select_target_agent(db, workspace_id=conv.workspace_id, binding_agent_id=binding.agent_id if binding else None)
    if not agent:
        # No agent configured — record failure outbound
        record_outbound_message(
            db,
            conversation_id=conv.id,
            agent_id=None,
            body_text="[No active agent configured for this workspace. TODO: configure DEFAULT_WHATSAPP_AGENT_ID.]",
            body_structured={"error": "no_agent"},
            provider=inbound.provider,
            reply_to_message_id=inbound.id,
            provider_message_id=None,
            delivery_status=DeliveryStatus.FAILED,
        )
        db.commit()
        return

    prior = find_prior_inbound_transcript(db, conv.id)
    messages = build_conversational_messages(agent=agent, user_text=inbound.body_text, prior_snippets=prior)
    provider = get_provider()
    result = provider.generate_conversational(agent=agent, messages=messages, response_hint="json")
    parsed = parse_conversational_json(result.text)
    reply_text = str(parsed.get("reply") or "").strip() or " "
    start_wf = bool(parsed.get("start_workflow"))
    workflow_id = parsed.get("workflow_id")

    ctx = SendContext(
        workspace_id=conv.workspace_id,
        conversation_id=conv.id,
        reply_to_provider_message_id=inbound.provider_message_id,
        metadata={"inbound_message_id": inbound.id},
    )
    to_addr = inbound.external_sender_address or (binding.external_user_address if binding else None)
    if not to_addr:
        record_outbound_message(
            db,
            conversation_id=conv.id,
            agent_id=agent.id,
            body_text=reply_text,
            body_structured=parsed,
            provider=inbound.provider,
            reply_to_message_id=inbound.id,
            provider_message_id=None,
            delivery_status=DeliveryStatus.FAILED,
        )
        db.commit()
        return

    wf_run_id: int | None = None
    if start_wf:
        wf: Workflow | None = None
        if workflow_id is not None:
            wf = db.query(Workflow).filter(Workflow.id == int(workflow_id), Workflow.workspace_id == conv.workspace_id).one_or_none()
        if wf is None:
            wf = db.query(Workflow).filter(Workflow.workspace_id == conv.workspace_id).order_by(Workflow.id.asc()).first()
        if wf is not None:
            orch = WorkflowOrchestrator()
            extra = {
                "messaging_conversation_id": conv.id,
                "messaging_channel_binding_id": binding.id if binding else None,
                "messaging_external_address": to_addr,
                "goal": wf.goal,
            }
            wf_run_id = orch.start_workflow_run(
                db=db,
                workflow_id=wf.id,
                user_id=ws.user_id,
                shared_context_extra=extra,
            )
            db.refresh(conv)
            conv.type = ConversationType.WORKFLOW_LINKED
            conv.linked_workflow_run_id = wf_run_id
            db.add(conv)
            reply_text = f"{reply_text}\n\n(I've started workflow “{wf.name}” — run #{wf_run_id}.)"

    ok, prov_id, err = asyncio.run(deliver_outbound_whatsapp(to_address=to_addr, body=reply_text, context=ctx))
    record_outbound_message(
        db,
        conversation_id=conv.id,
        agent_id=agent.id,
        body_text=reply_text,
        body_structured=parsed,
        provider=inbound.provider,
        reply_to_message_id=inbound.id,
        provider_message_id=prov_id,
        delivery_status=DeliveryStatus.SENT if ok else DeliveryStatus.FAILED,
    )
    if binding:
        binding.last_outbound_at = datetime.utcnow()
        db.add(binding)

    log_event(
        db,
        workspace_id=conv.workspace_id,
        workflow_run_id=wf_run_id,
        user_id=ws.user_id,
        event_type="whatsapp_outbound" if ok else "whatsapp_outbound_failed",
        message=reply_text[:500],
        metadata={
            "inbound_message_id": inbound.id,
            "provider_message_id": prov_id,
            "error": err,
        },
    )
    db.commit()


__all__ = ["process_inbound_whatsapp_message"]
