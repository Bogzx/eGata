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
from app.tools import REGISTRY, ToolContext
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


def test_prompts_include_widget_directive() -> None:
    from app.prompts import build_system_prompt

    p = build_system_prompt()
    assert "propose_widget" in p
    assert "thinking" in p.lower() or "gândire" in p.lower()


# ---- text_hygiene.strip_thinking ----


def test_strip_thinking_removes_tags() -> None:
    from app.text_hygiene import strip_thinking

    assert strip_thinking("<thinking>foo</thinking>bar") == "bar"
    assert strip_thinking("a<scratchpad>x</scratchpad>b") == "ab"
    assert strip_thinking("<reasoning>r</reasoning>") == ""
    assert strip_thinking("hi<thinking>\nlong\nstuff\n</thinking>there") == "hithere"
    assert strip_thinking("  hello  ") == "hello"
    assert strip_thinking("a<Thinking>1</Thinking>b<thinking>2</thinking>c") == "abc"


def test_strip_thinking_passthrough() -> None:
    from app.text_hygiene import strip_thinking

    assert strip_thinking("") == ""
    assert strip_thinking(None) is None
    assert strip_thinking("plain text no tags") == "plain text no tags"


# ---- propose_widget tool ----


def test_propose_widget_registered() -> None:
    assert "propose_widget" in REGISTRY


def test_propose_widget_choice_happy() -> None:
    import asyncio

    from app.tools.propose_widget import propose_widget

    ctx = ToolContext(citizen_id="c1", document_id="d1")
    result = asyncio.run(
        propose_widget(
            ctx,
            type="choice",
            question="Cum locuiești?",
            options=["Proprietar", "Chiriaș", "Găzduit"],
            target_field="tip_locuinta",
        )
    )
    assert result.acknowledged is True
    assert isinstance(result.widget_id, str) and len(result.widget_id) >= 16
    assert result.type == "choice"
    assert result.target_field == "tip_locuinta"


def test_propose_widget_choice_needs_two_options() -> None:
    import asyncio

    from app.tools.propose_widget import propose_widget

    ctx = ToolContext(citizen_id="c1", document_id="d1")
    with pytest.raises(ValueError, match=">= 2 options"):
        asyncio.run(
            propose_widget(
                ctx,
                type="choice",
                question="x?",
                options=["only-one"],
                target_field="f",
            )
        )


def test_propose_widget_choice_needs_target_field() -> None:
    import asyncio

    from app.tools.propose_widget import propose_widget

    ctx = ToolContext(citizen_id="c1", document_id="d1")
    with pytest.raises(ValueError, match="target_field"):
        asyncio.run(
            propose_widget(
                ctx,
                type="choice",
                question="x?",
                options=["a", "b"],
                target_field=None,
            )
        )


def test_propose_widget_confirm_ok() -> None:
    import asyncio

    from app.tools.propose_widget import propose_widget

    ctx = ToolContext(citizen_id="c1", document_id="d1")
    result = asyncio.run(
        propose_widget(ctx, type="confirm", question="Continui?")
    )
    assert result.acknowledged is True
    assert result.type == "confirm"


def test_propose_widget_rejects_unknown_type() -> None:
    import asyncio

    from app.tools.propose_widget import propose_widget

    ctx = ToolContext(citizen_id="c1", document_id="d1")
    with pytest.raises(ValueError, match="unknown widget type"):
        asyncio.run(propose_widget(ctx, type="banana", question="x"))


def test_phone_tool_allowlist_excludes_propose_widget() -> None:
    assert "propose_widget" not in PHONE_TOOL_ALLOWLIST


# ---- lookup_procedure scenario_plan extension (Multi-procedure RAG) ----


def test_lookup_returns_scenario_plan_when_top_is_scenario(monkeypatch):
    """When the top-1 RAG hit is a scenario above threshold, scenario_plan is populated."""
    import asyncio

    from app.tools import lookup_procedure as lp_module
    from app.tools.lookup_procedure import LookupResult, lookup_procedure

    fake_rows = [
        {"id": "sc-cumparare-apartament", "kind": "scenario", "score": 0.78},
        {"id": "declarare-cladire", "kind": "procedure", "score": 0.62},
    ]
    monkeypatch.setattr(lp_module, "embed_text", lambda _t: [0.0] * 768)
    monkeypatch.setattr(lp_module, "search_top_k_rag", lambda _e, k=5: fake_rows)

    result: LookupResult = asyncio.run(
        lookup_procedure(ctx=None, query="am cumpărat un apartament")
    )

    assert result.scenario_plan is not None
    assert result.scenario_plan.scenario_id == "sc-cumparare-apartament"
    assert len(result.scenario_plan.in_scope_steps) == 3


def test_lookup_returns_no_scenario_when_top_is_procedure(monkeypatch):
    """Procedure wins even if a scenario is in the top-K but lower-ranked."""
    import asyncio

    from app.tools import lookup_procedure as lp_module
    from app.tools.lookup_procedure import lookup_procedure

    fake_rows = [
        {"id": "schimbare-domiciliu", "kind": "procedure", "score": 0.81},
        {"id": "sc-cumparare-apartament", "kind": "scenario", "score": 0.66},
    ]
    monkeypatch.setattr(lp_module, "embed_text", lambda _t: [0.0] * 768)
    monkeypatch.setattr(lp_module, "search_top_k_rag", lambda _e, k=5: fake_rows)

    result = asyncio.run(lookup_procedure(ctx=None, query="vreau să-mi schimb domiciliul"))

    assert result.scenario_plan is None
    assert len(result.matches) >= 1
    assert result.matches[0].procedure_id == "schimbare-domiciliu"


def test_lookup_below_threshold_no_scenario_plan(monkeypatch):
    """Sub-threshold hits return no scenario_plan."""
    import asyncio

    from app.tools import lookup_procedure as lp_module
    from app.tools.lookup_procedure import lookup_procedure

    fake_rows = [
        {"id": "schimbare-domiciliu", "kind": "procedure", "score": 0.30},
    ]
    monkeypatch.setattr(lp_module, "embed_text", lambda _t: [0.0] * 768)
    monkeypatch.setattr(lp_module, "search_top_k_rag", lambda _e, k=5: fake_rows)

    result = asyncio.run(lookup_procedure(ctx=None, query="ceva ciudat"))

    assert result.scenario_plan is None
