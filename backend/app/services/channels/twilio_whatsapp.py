from __future__ import annotations

import hashlib
import hmac
import urllib.parse
from datetime import datetime
from typing import Any

import httpx
from fastapi import Request

from app.core.config import settings
from app.models.entities import MessageChannel, MessageProvider
from app.services.channels.base import ChannelAdapter
from app.services.channels.types import (
    DeliveryUpdate,
    NormalizedInboundMessage,
    ProviderSendResult,
    ReplyContext,
    SendContext,
)


async def _parse_form(request: Request) -> dict[str, str]:
    """Parse Twilio application/x-www-form-urlencoded without requiring python-multipart."""
    body = await request.body()
    parsed = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {k: v[0] if v else "" for k, v in parsed.items()}


def _verify_twilio_signature(url: str, params: dict[str, str], signature: str, auth_token: str) -> bool:
    # https://www.twilio.com/docs/usage/security#validating-requests
    if not auth_token:
        return False
    s = url
    for key in sorted(params.keys()):
        s += key + params[key]
    expected = hmac.new(auth_token.encode("utf-8"), s.encode("utf-8"), hashlib.sha1).digest()
    import base64

    expected_b64 = base64.b64encode(expected).decode("utf-8")
    return hmac.compare_digest(expected_b64, signature)


class TwilioWhatsAppAdapter(ChannelAdapter):
    async def parse_inbound_request(self, request: Request) -> list[NormalizedInboundMessage]:
        params = await _parse_form(request)
        from_addr = params.get("From", "")
        to_addr = params.get("To", "")
        body = params.get("Body", "") or ""
        sid = params.get("MessageSid") or params.get("SmsMessageSid") or ""
        if not sid:
            # TODO: real Twilio always sends MessageSid; keep synthetic for tests
            sid = f"twilio-synthetic-{hash(from_addr + body) & 0xFFFFFFFF}"

        ts = datetime.utcnow()
        return [
            NormalizedInboundMessage(
                channel=MessageChannel.WHATSAPP,
                provider=MessageProvider.TWILIO,
                external_user_address=from_addr.replace("whatsapp:", ""),
                external_business_address=to_addr.replace("whatsapp:", "") or None,
                message_id=sid,
                text=body,
                raw_payload=dict(params),
                timestamp=ts,
                attachments=[],
                reply_context=None,
            )
        ]

    async def send_text(self, to: str, body: str, context: SendContext) -> ProviderSendResult:
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            # TODO: configure TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM for live sends
            return ProviderSendResult(ok=False, error="Twilio credentials not configured (TODO)")

        from_num = settings.twilio_whatsapp_from
        if not from_num:
            return ProviderSendResult(ok=False, error="TWILIO_WHATSAPP_FROM not set (TODO)")

        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"

        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
        )
        data = {"From": from_num, "To": to, "Body": body}
        auth = (settings.twilio_account_sid, settings.twilio_auth_token)

        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.post(url, data=data, auth=auth)
                r.raise_for_status()
                payload = r.json()
                return ProviderSendResult(
                    ok=True,
                    provider_message_id=payload.get("sid"),
                    raw=payload,
                )
        except Exception as e:
            return ProviderSendResult(ok=False, error=str(e)[:2000])

    async def parse_status_callback(self, request: Request) -> list[DeliveryUpdate]:
        params = await _parse_form(request)
        sid = params.get("MessageSid") or ""
        status = (params.get("MessageStatus") or params.get("SmsStatus") or "").lower()
        if not sid:
            return []
        return [DeliveryUpdate(provider_message_id=sid, status=status, raw=dict(params))]

    def verify_signature(self, request: Request, raw_body: bytes) -> bool:
        if not settings.whatsapp_verify_signature:
            return True
        sig = request.headers.get("X-Twilio-Signature") or ""
        if not sig:
            return False
        # Reconstruct URL Twilio used (public URL must match configured webhook URL)
        url = str(request.url)
        # Twilio sends application/x-www-form-urlencoded
        params = urllib.parse.parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
        flat = {k: v[0] if v else "" for k, v in params.items()}
        return _verify_twilio_signature(url, flat, sig, settings.twilio_auth_token)
