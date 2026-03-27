from __future__ import annotations

import hashlib
import hmac
from datetime import datetime

import httpx
from fastapi import Request

from app.core.config import settings
from app.models.entities import MessageChannel, MessageProvider
from app.services.channels.base import ChannelAdapter
from app.services.channels.types import (
    Attachment,
    DeliveryUpdate,
    NormalizedInboundMessage,
    ProviderSendResult,
    ReplyContext,
    SendContext,
)


class MetaWhatsAppAdapter(ChannelAdapter):
    async def parse_inbound_request(self, request: Request) -> list[NormalizedInboundMessage]:
        payload = await request.json()
        out: list[NormalizedInboundMessage] = []
        entries = payload.get("entry") or []
        for entry in entries:
            changes = entry.get("changes") or []
            for change in changes:
                value = change.get("value") or {}
                messages = value.get("messages") or []
                metadata = value.get("metadata") or {}
                phone_number_id = metadata.get("phone_number_id")
                for msg in messages:
                    from_addr = msg.get("from") or ""
                    mid = msg.get("id") or ""
                    ts = msg.get("timestamp")
                    dt = datetime.utcfromtimestamp(int(ts)) if ts else datetime.utcnow()
                    text = ""
                    if "text" in msg:
                        text = (msg.get("text") or {}).get("body") or ""
                    context = msg.get("context") or {}
                    reply_ctx = (
                        ReplyContext(provider_message_id=context.get("id"), raw=context) if context else None
                    )
                    attachments: list[Attachment] = []
                    if msg.get("type") == "image":
                        attachments.append(Attachment(raw={"type": "image", "image": msg.get("image")}))
                    out.append(
                        NormalizedInboundMessage(
                            channel=MessageChannel.WHATSAPP,
                            provider=MessageProvider.META,
                            external_user_address=from_addr,
                            external_business_address=str(phone_number_id) if phone_number_id else None,
                            message_id=mid,
                            text=text,
                            raw_payload={"entry": entry, "message": msg},
                            timestamp=dt,
                            attachments=attachments,
                            reply_context=reply_ctx,
                        )
                    )
        return out

    async def send_text(self, to: str, body: str, context: SendContext) -> ProviderSendResult:
        if not settings.meta_whatsapp_access_token or not settings.meta_whatsapp_phone_number_id:
            # TODO: configure META_WHATSAPP_ACCESS_TOKEN / META_WHATSAPP_PHONE_NUMBER_ID
            return ProviderSendResult(ok=False, error="Meta WhatsApp credentials not configured (TODO)")

        url = f"https://graph.facebook.com/v20.0/{settings.meta_whatsapp_phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {settings.meta_whatsapp_access_token}",
            "Content-Type": "application/json",
        }
        data = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.post(url, headers=headers, json=data)
                r.raise_for_status()
                payload = r.json()
                messages = payload.get("messages") or []
                mid = messages[0].get("id") if messages else None
                return ProviderSendResult(ok=True, provider_message_id=mid, raw=payload)
        except Exception as e:
            return ProviderSendResult(ok=False, error=str(e)[:2000])

    async def send_typing(self, to: str, context: SendContext) -> None:
        # Meta Cloud API typing indicators use a separate endpoint; optional TODO
        return None

    async def parse_status_callback(self, request: Request) -> list[DeliveryUpdate]:
        payload = await request.json()
        out: list[DeliveryUpdate] = []
        entries = payload.get("entry") or []
        for entry in entries:
            changes = entry.get("changes") or []
            for change in changes:
                value = change.get("value") or {}
                statuses = value.get("statuses") or []
                for st in statuses:
                    mid = st.get("id") or ""
                    status = (st.get("status") or "").lower()
                    if mid:
                        out.append(DeliveryUpdate(provider_message_id=mid, status=status, raw=st))
        return out

    def verify_signature(self, request: Request, raw_body: bytes) -> bool:
        if not settings.whatsapp_verify_signature:
            return True
        if not settings.meta_app_secret:
            return False
        sig_header = request.headers.get("X-Hub-Signature-256") or ""
        if not sig_header.startswith("sha256="):
            return False
        expected = hmac.new(
            settings.meta_app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        received = sig_header.split("=", 1)[1]
        return hmac.compare_digest(expected, received)
