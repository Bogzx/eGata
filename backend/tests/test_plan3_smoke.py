"""Plan 3 smoke tests — minimal coverage of new surfaces.

Covers:
- JWT round-trip + tampering / expiry / wrong audience.
- Tool registry contains all 6 expected tools.
- /tools/{name} requires bearer JWT.
- /voice/twilio/webhook returns either TwiML <Stream> or static fallback.
- Phone tool allowlist excludes document-mutating tools.

Does NOT hit Gemini or Supabase — pure unit coverage.
"""
from __future__ import annotations

import time

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.tools import REGISTRY
from app.twilio_bridge import (
    PHONE_TOOL_ALLOWLIST,
    mulaw_to_pcm16_16k,
    parse_twilio_frame,
    pcm16_24k_to_mulaw_8k,
)
from app.voice import issue_tool_jwt, verify_tool_jwt


client = TestClient(app)


# ---- JWT ----

def test_jwt_roundtrip() -> None:
    token = issue_tool_jwt(
        citizen_id="11111111-1111-1111-1111-111111111111",
        document_id="22222222-2222-2222-2222-222222222222",
        ttl_seconds=300,
    )
    claims = verify_tool_jwt(token)
    assert claims.citizen_id == "11111111-1111-1111-1111-111111111111"
    assert claims.document_id == "22222222-2222-2222-2222-222222222222"


def test_jwt_expired_rejected() -> None:
    token = issue_tool_jwt(citizen_id="x", document_id=None, ttl_seconds=-1)
    with pytest.raises(pyjwt.ExpiredSignatureError):
        verify_tool_jwt(token)


def test_jwt_wrong_audience_rejected() -> None:
    settings = get_settings()
    bad = pyjwt.encode(
        {
            "sub": "x",
            "aud": "wrong-aud",
            "iss": settings.jwt_issuer,
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
            "jti": "abc",
        },
        settings.jwt_signing_secret,
        algorithm="HS256",
    )
    with pytest.raises(pyjwt.InvalidAudienceError):
        verify_tool_jwt(bad)


def test_jwt_tampered_signature_rejected() -> None:
    token = issue_tool_jwt(citizen_id="x", document_id=None, ttl_seconds=300)
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(pyjwt.InvalidSignatureError):
        verify_tool_jwt(tampered)


# ---- Tool registry ----

def test_registry_has_six_tools() -> None:
    expected = {
        "lookup_procedure",
        "set_field",
        "generate_pdf",
        "deliver",
        "find_redirect",
        "set_reminder",
    }
    assert expected.issubset(set(REGISTRY.keys()))


# ---- /tools/{name} HTTP endpoint ----

def test_tools_endpoint_requires_jwt() -> None:
    r = client.post("/tools/lookup_procedure", json={"query": "x"})
    assert r.status_code == 401


def test_tools_endpoint_unknown_tool_404() -> None:
    token = issue_tool_jwt(
        citizen_id="11111111-1111-1111-1111-111111111111",
        document_id=None,
    )
    r = client.post(
        "/tools/nonexistent_tool",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert r.status_code == 404


# ---- find_redirect tool (no IO, safe to run online) ----

def test_find_redirect_anaf() -> None:
    import asyncio

    from app.tools import ToolContext
    from app.tools.find_redirect import find_redirect

    ctx = ToolContext(citizen_id="x", document_id=None)
    result = asyncio.run(find_redirect(ctx, query="vreau să plătesc impozit pe casă"))
    assert result.target == "ANAF"
    assert result.url and "anaf" in result.url.lower()


def test_find_redirect_drpciv() -> None:
    import asyncio

    from app.tools import ToolContext
    from app.tools.find_redirect import find_redirect

    ctx = ToolContext(citizen_id="x", document_id=None)
    result = asyncio.run(
        find_redirect(ctx, query="vreau să schimb adresa pe talon")
    )
    assert result.target == "DRPCIV"


def test_find_redirect_unknown_returns_none() -> None:
    import asyncio

    from app.tools import ToolContext
    from app.tools.find_redirect import find_redirect

    ctx = ToolContext(citizen_id="x", document_id=None)
    result = asyncio.run(find_redirect(ctx, query="vreau o pizza"))
    assert result.target is None


# ---- Twilio bridge audio codec helpers ----

def test_mulaw_to_pcm16_16k_roughly_doubles_samples() -> None:
    # 160 bytes μ-law (20 ms @ 8 kHz) → 16 kHz PCM16. Expected ≈ 640 bytes,
    # audioop.ratecv may shave a couple due to filter delay — allow ±4.
    pcm = mulaw_to_pcm16_16k(bytes([0xFF] * 160))
    assert 636 <= len(pcm) <= 644


def test_pcm24k_to_mulaw_8k_one_third() -> None:
    # 100 ms of 24 kHz PCM16 silence = 4800 bytes → μ-law 8 kHz ≈ 800 bytes ±4.
    mulaw = pcm16_24k_to_mulaw_8k(bytes(4800))
    assert 796 <= len(mulaw) <= 804


def test_parse_twilio_frame_media() -> None:
    import base64

    payload = base64.b64encode(b"\xff" * 160).decode()
    frame = parse_twilio_frame(
        {
            "event": "media",
            "streamSid": "MZxxxx",
            "media": {"payload": payload, "track": "inbound"},
        }
    )
    assert frame.event == "media"
    assert frame.audio_mulaw == b"\xff" * 160


def test_phone_tool_allowlist_excludes_writes() -> None:
    assert "lookup_procedure" in PHONE_TOOL_ALLOWLIST
    assert "find_redirect" in PHONE_TOOL_ALLOWLIST
    for write_tool in ("set_field", "generate_pdf", "deliver", "set_reminder"):
        assert write_tool not in PHONE_TOOL_ALLOWLIST


# ---- /voice/twilio/webhook returns TwiML ----

def test_voice_twilio_webhook_returns_twiml() -> None:
    r = client.post("/voice/twilio/webhook")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    body = r.text
    # Either bridge-mode (<Stream>) or fallback (<Say>) — both are valid responses.
    assert "<Response>" in body
    assert ("<Stream" in body) or ("<Say" in body)


# ---- /voice/session requires auth ----

def test_voice_session_requires_auth() -> None:
    r = client.post("/voice/session", json={})
    assert r.status_code == 401


# ---- /agent/chat preserves contract ----

def test_agent_chat_requires_auth() -> None:
    r = client.post("/agent/chat", json={"message": "hello"})
    assert r.status_code == 401


# ---- /tools/lookup_procedure with valid JWT ----
# Skipped by default because it hits Gemini embeddings + Supabase.

def test_prompts_build() -> None:
    from app.prompts import build_system_prompt

    p = build_system_prompt()
    assert "CivicAI" in p
    assert "primăriei" in p
    p2 = build_system_prompt(simple_language=True)
    assert "MOD SIMPLU ACTIVAT" in p2
    p3 = build_system_prompt(variant="phone")
    assert "telefonic" in p3
