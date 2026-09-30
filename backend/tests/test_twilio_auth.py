"""The phone bridge only talks to Twilio.

Before: POST /voice/twilio/webhook handed its stream URL to anyone, and
WS /voice/twilio started an Azure VoiceLive session (billed) for any client.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from twilio.request_validator import RequestValidator

from app import twilio_bridge
from app.config import get_settings
from app.main import app

AUTH_TOKEN = "twilio-test-token"
HOOK = "http://testserver/voice/twilio/webhook"
FORM = {"CallSid": "CA123", "From": "+40700000000", "To": "+40711111111"}


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", AUTH_TOKEN)
    monkeypatch.setenv("AZURE_VOICELIVE_API_KEY", "k")
    monkeypatch.setenv("TWILIO_BRIDGE_PUBLIC_URL", "wss://example.test/voice/twilio")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _signed(params: dict[str, str]) -> dict[str, str]:
    return {"X-Twilio-Signature": RequestValidator(AUTH_TOKEN).compute_signature(HOOK, params)}


def test_webhook_refuses_a_forged_request(configured: None) -> None:
    r = TestClient(app).post(HOOK, data=FORM, headers={"X-Twilio-Signature": "forged"})
    assert r.status_code == 403


def test_webhook_answers_twilio_with_a_stream_token(configured: None) -> None:
    r = TestClient(app).post(HOOK, data=FORM, headers=_signed(FORM))
    assert r.status_code == 200
    assert 'url="wss://example.test/voice/twilio"' in r.text
    assert '<Parameter name="token"' in r.text


def test_webhook_without_auth_token_never_reveals_the_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("AZURE_VOICELIVE_API_KEY", "k")
    monkeypatch.setenv("TWILIO_BRIDGE_PUBLIC_URL", "wss://example.test/voice/twilio")
    get_settings.cache_clear()
    try:
        r = TestClient(app).post(HOOK, data=FORM)
    finally:
        get_settings.cache_clear()
    assert r.status_code == 200
    assert "<Stream" not in r.text  # fallback <Say> TwiML


def test_stream_token_is_bound_to_the_call_and_expires() -> None:
    token = twilio_bridge.mint_stream_token("CA123")
    assert twilio_bridge.verify_stream_token(token, "CA123")
    assert not twilio_bridge.verify_stream_token(token, "CA999")
    assert not twilio_bridge.verify_stream_token("nonsense", "CA123")
    stale = twilio_bridge.mint_stream_token("CA123", ttl=-1)
    assert not twilio_bridge.verify_stream_token(stale, "CA123")


def _start(token: str | None, call_sid: str = "CA123") -> dict:
    return {
        "event": "start",
        "streamSid": "MZ1",
        "start": {"callSid": call_sid, "customParameters": {"token": token} if token else {}},
    }


def test_stream_without_token_is_closed_before_voicelive_starts() -> None:
    with patch("app.twilio_bridge._run_phone_voicelive_session") as run:
        with TestClient(app).websocket_connect("/voice/twilio") as ws:
            ws.send_json({"event": "connected"})
            ws.send_json(_start(None))
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_text()
    assert exc.value.code == 4403
    run.assert_not_called()


def test_stream_with_valid_token_starts_voicelive() -> None:
    async def fake_session(*_a, **_k) -> None:  # type: ignore[no-untyped-def]
        return None

    with patch("app.twilio_bridge._run_phone_voicelive_session", side_effect=fake_session) as run:
        with TestClient(app).websocket_connect("/voice/twilio") as ws:
            ws.send_json({"event": "connected"})
            ws.send_json(_start(twilio_bridge.mint_stream_token("CA123")))
            ws.send_json({"event": "stop", "streamSid": "MZ1"})
            time.sleep(0.05)
    run.assert_called_once()
