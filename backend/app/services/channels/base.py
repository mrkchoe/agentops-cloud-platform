from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from fastapi import Request

from app.services.channels.types import DeliveryUpdate, NormalizedInboundMessage, ProviderSendResult, SendContext


class ChannelAdapter(ABC):
    """Provider-specific WhatsApp (or other channel) adapter."""

    @abstractmethod
    async def parse_inbound_request(self, request: Request) -> list[NormalizedInboundMessage]:
        """Return zero or more normalized messages (Meta may batch)."""

    @abstractmethod
    async def send_text(self, to: str, body: str, context: SendContext) -> ProviderSendResult:
        """Send a plain-text outbound message."""

    async def send_typing(self, to: str, context: SendContext) -> None:
        """Optional typing indicator; default no-op."""

    @abstractmethod
    async def parse_status_callback(self, request: Request) -> list[DeliveryUpdate]:
        """Parse delivery status webhook body."""

    @abstractmethod
    def verify_signature(self, request: Request, raw_body: bytes) -> bool:
        """Validate provider signature when enabled in settings."""
