from __future__ import annotations

from app.core.config import settings
from app.services.channels.base import ChannelAdapter
from app.services.channels.meta_whatsapp import MetaWhatsAppAdapter
from app.services.channels.twilio_whatsapp import TwilioWhatsAppAdapter


def get_whatsapp_adapter() -> ChannelAdapter:
    """Resolve the configured WhatsApp provider adapter."""
    p = (settings.whatsapp_provider or "twilio").lower()
    if p == "meta":
        return MetaWhatsAppAdapter()
    return TwilioWhatsAppAdapter()
