from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.models.entities import MessageProvider
from app.services.channels.meta_whatsapp import MetaWhatsAppAdapter
from app.services.channels.twilio_whatsapp import TwilioWhatsAppAdapter


def test_twilio_parse_inbound():
    app = FastAPI()

    @app.post("/hook")
    async def hook(request: Request):
        msgs = await TwilioWhatsAppAdapter().parse_inbound_request(request)
        return [
            {
                "text": m.text,
                "mid": m.message_id,
                "from": m.external_user_address,
                "provider": m.provider.value,
            }
            for m in msgs
        ]

    client = TestClient(app)
    r = client.post(
        "/hook",
        data={
            "MessageSid": "SMxyz",
            "From": "whatsapp:+15550001111",
            "To": "whatsapp:+15550002222",
            "Body": "hi",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data[0]["text"] == "hi"
    assert data[0]["mid"] == "SMxyz"
    assert data[0]["from"] == "+15550001111"
    assert data[0]["provider"] == MessageProvider.TWILIO.value


def test_meta_parse_inbound():
    app = FastAPI()

    @app.post("/m")
    async def m(request: Request):
        msgs = await MetaWhatsAppAdapter().parse_inbound_request(request)
        return [{"id": x.message_id, "text": x.text} for x in msgs]

    client = TestClient(app)
    payload = '{"entry":[{"changes":[{"value":{"metadata":{"phone_number_id":"123"},"messages":[{"from":"1555","id":"mid1","timestamp":"1600000000","type":"text","text":{"body":"yo"}}]}}]}]}'
    r = client.post("/m", content=payload, headers={"content-type": "application/json"})
    assert r.status_code == 200
    data = r.json()
    assert data[0]["id"] == "mid1"
    assert data[0]["text"] == "yo"


def test_twilio_verify_signature_disabled(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "whatsapp_verify_signature", False)
    adapter = TwilioWhatsAppAdapter()
    req = MagicMock(spec=Request)
    assert adapter.verify_signature(req, b"x") is True

