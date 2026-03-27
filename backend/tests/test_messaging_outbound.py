import asyncio

from app.services.channels.types import SendContext
from app.services.messaging_service import deliver_outbound_whatsapp


def test_outbound_without_credentials_returns_failure(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "twilio_account_sid", "")
    monkeypatch.setattr(config.settings, "meta_whatsapp_access_token", "")
    monkeypatch.setattr(config.settings, "whatsapp_provider", "twilio")

    ctx = SendContext(workspace_id=1, conversation_id=1)
    ok, mid, err = asyncio.run(deliver_outbound_whatsapp(to_address="+1", body="x", context=ctx))
    assert ok is False
    assert err
