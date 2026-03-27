from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.entities import MessageChannel, MessageProvider


@dataclass(frozen=True)
class Attachment:
    url: str | None = None
    mime_type: str | None = None
    content_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReplyContext:
    """Provider-specific reply threading (e.g. quoted message id)."""

    provider_message_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedInboundMessage:
    channel: MessageChannel
    provider: MessageProvider
    external_user_address: str
    external_business_address: str | None
    message_id: str
    text: str
    raw_payload: dict[str, Any]
    timestamp: datetime | None
    attachments: list[Attachment] = field(default_factory=list)
    reply_context: ReplyContext | None = None


@dataclass(frozen=True)
class ProviderSendResult:
    ok: bool
    provider_message_id: str | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryUpdate:
    provider_message_id: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SendContext:
    """Context passed to outbound send (binding, conversation, reply threading)."""

    workspace_id: int
    conversation_id: int
    reply_to_provider_message_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
