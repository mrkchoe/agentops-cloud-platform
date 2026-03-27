from __future__ import annotations

import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.entities import (
    Conversation,
    DeliveryStatus,
    Message,
    MessageProvider,
    StatusCallbackDedupe,
    Workspace,
)
from app.schemas.schemas import (
    ConversationCreateIn,
    ConversationDetailOut,
    ConversationOut,
    MessageCreateIn,
    MessageOut,
    WorkflowRunOut,
)
from app.services.activity_log import log_event
from app.services.channels import get_whatsapp_adapter
from app.services.conversation_service import (
    append_web_message,
    assert_workspace_access,
    build_conversation_detail,
    create_conversation,
    list_conversations_for_workspace,
    list_messages,
)
from app.services.messaging_service import (
    append_inbound_message,
    get_or_create_channel_binding,
    resolve_default_workspace_id,
)
from app.tasks.celery_tasks import deliver_web_reply_to_whatsapp_task, process_whatsapp_inbound_message_task

router = APIRouter(tags=["messaging"])


@router.get("/conversations", response_model=list[ConversationOut])
def get_conversations(
    workspace_id: int = Query(..., description="Workspace scope"),
    limit: int = 50,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[ConversationOut]:
    assert_workspace_access(db, workspace_id=workspace_id, user_id=user_id)
    limit = max(1, min(limit, 200))
    return list_conversations_for_workspace(db, workspace_id=workspace_id, limit=limit)


@router.post("/conversations", response_model=ConversationOut)
def post_conversation(
    payload: ConversationCreateIn,
    workspace_id: int = Query(...),
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ConversationOut:
    assert_workspace_access(db, workspace_id=workspace_id, user_id=user_id)
    c = create_conversation(
        db,
        workspace_id=workspace_id,
        title=payload.title,
        conv_type=payload.type,
    )
    log_event(
        db,
        workspace_id=workspace_id,
        workflow_run_id=None,
        user_id=user_id,
        event_type="conversation_created",
        message=f"Conversation created ({payload.type.value}).",
        metadata={"conversation_id": c.id},
    )
    db.commit()
    db.refresh(c)
    return c


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation_detail(
    conversation_id: int,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ConversationDetailOut:
    conv, primary_channel, agent_id, agent_name, run = build_conversation_detail(db, conversation_id=conversation_id)
    assert_workspace_access(db, workspace_id=conv.workspace_id, user_id=user_id)
    return ConversationDetailOut(
        id=conv.id,
        workspace_id=conv.workspace_id,
        type=conv.type,
        title=conv.title,
        status=conv.status,
        linked_workflow_run_id=conv.linked_workflow_run_id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        primary_channel=primary_channel,
        binding_agent_id=agent_id,
        binding_agent_name=agent_name,
        workflow_run=WorkflowRunOut.model_validate(run) if run else None,
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_conversation_messages(
    conversation_id: int,
    limit: int = 100,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).one()
    assert_workspace_access(db, workspace_id=conv.workspace_id, user_id=user_id)
    limit = max(1, min(limit, 500))
    return list_messages(db, conversation_id=conversation_id, limit=limit)


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
def post_conversation_message(
    conversation_id: int,
    payload: MessageCreateIn,
    *,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MessageOut:
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).one()
    assert_workspace_access(db, workspace_id=conv.workspace_id, user_id=user_id)
    m = append_web_message(
        db,
        conversation_id=conversation_id,
        user_id=user_id,
        body_text=payload.body_text,
        body_structured=payload.body_structured,
    )
    log_event(
        db,
        workspace_id=conv.workspace_id,
        workflow_run_id=None,
        user_id=user_id,
        event_type="conversation_message_created",
        message="Web message posted.",
        metadata={"conversation_id": conversation_id, "message_id": m.id},
    )
    db.commit()
    db.refresh(m)
    deliver_web_reply_to_whatsapp_task.delay(conversation_id, m.id)
    return m


@router.post("/channels/whatsapp/inbound")
async def whatsapp_inbound_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    raw = await request.body()
    adapter = get_whatsapp_adapter()
    if not adapter.verify_signature(request, raw):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    messages = await adapter.parse_inbound_request(request)
    workspace_id = resolve_default_workspace_id(db)
    if workspace_id is None:
        raise HTTPException(status_code=500, detail="No workspace configured (set DEFAULT_WHATSAPP_WORKSPACE_ID)")

    ws = db.query(Workspace).filter(Workspace.id == workspace_id).one()
    results: list[dict] = []

    for norm in messages:
        try:
            binding, conv, _new = get_or_create_channel_binding(
                db,
                workspace_id=workspace_id,
                provider=norm.provider,
                external_user_address=norm.external_user_address,
            )
            binding.last_inbound_at = datetime.utcnow()
            db.add(binding)

            inbound = append_inbound_message(
                db,
                conversation_id=conv.id,
                text=norm.text,
                provider=norm.provider,
                provider_message_id=norm.message_id,
                external_address=norm.external_user_address,
                raw_payload=norm.raw_payload,
            )

            log_event(
                db,
                workspace_id=workspace_id,
                workflow_run_id=None,
                user_id=ws.user_id,
                event_type="whatsapp_inbound",
                message=f"Inbound WhatsApp message from {norm.external_user_address}",
                metadata={"message_id": inbound.id, "provider_message_id": norm.message_id},
            )
            db.commit()
            db.refresh(inbound)

            process_whatsapp_inbound_message_task.delay(inbound.id)
            results.append({"ok": True, "message_id": inbound.id})
        except IntegrityError:
            db.rollback()
            results.append({"ok": True, "deduped": True, "provider_message_id": norm.message_id})

    return {"received": len(messages), "results": results}


@router.get("/channels/whatsapp/webhook/verify")
async def whatsapp_meta_verify(request: Request) -> Response:
    """Meta Cloud API subscription verification (challenge)."""
    hub_mode = request.query_params.get("hub.mode")
    hub_verify_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")
    if hub_mode != "subscribe":
        raise HTTPException(status_code=403, detail="Invalid mode")
    expected = app_settings.whatsapp_webhook_verify_token or app_settings.meta_verify_token
    if not expected or hub_verify_token != expected:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return Response(content=hub_challenge or "", media_type="text/plain")


@router.post("/channels/whatsapp/status")
async def whatsapp_status_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    raw = await request.body()
    adapter = get_whatsapp_adapter()
    if not adapter.verify_signature(request, raw):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    updates = await adapter.parse_status_callback(request)
    updated = 0
    skipped = 0
    prov = MessageProvider.META if app_settings.whatsapp_provider.lower() == "meta" else MessageProvider.TWILIO

    status_map = {
        "delivered": DeliveryStatus.DELIVERED,
        "read": DeliveryStatus.READ,
        "sent": DeliveryStatus.SENT,
        "failed": DeliveryStatus.FAILED,
        "undelivered": DeliveryStatus.FAILED,
    }

    for u in updates:
        digest = hashlib.sha256(f"{u.provider_message_id}:{u.status}".encode()).hexdigest()
        if db.query(StatusCallbackDedupe).filter(StatusCallbackDedupe.dedupe_key == digest).first():
            skipped += 1
            continue

        db.add(StatusCallbackDedupe(provider=prov, dedupe_key=digest))

        row = db.query(Message).filter(Message.provider_message_id == u.provider_message_id).one_or_none()
        if row:
            row.delivery_status = status_map.get(u.status.lower(), row.delivery_status)
            db.add(row)
            updated += 1
        db.commit()

    return {"updates": len(updates), "messages_updated": updated, "deduped_skipped": skipped}
