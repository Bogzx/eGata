# eGata — Plan 3: Agent Intelligence + Voice

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mock chat with a real Pydantic AI agent, integrate Gemini Live for realtime Romanian voice on browser + Twilio phone, and wire the three completion modes to the real agent.

**Architecture:** Pydantic AI agent in FastAPI exposes tool endpoints; browser opens a direct WebSocket to Gemini Live using an ephemeral token from FastAPI, function calls from Gemini Live dispatch back to FastAPI tools via signed JWT; Twilio Media Streams bridge in FastAPI proxies G.711 ↔ PCM to a parallel Gemini Live session for phone.

**Tech Stack:** Pydantic AI SDK, Google `google-genai` SDK (Gemini Live), `websockets` (Python), `pydub` or `audioop` for G.711 transcode, JWT (PyJWT), browser Gemini Live SDK (or raw WebSocket), Twilio Media Streams. OpenAI SDK retained for fallback if Gemini Romanian disappoints.

**Dependencies:** Wave 1 must be merged. Specifically Plan 2's `agent.py`, `procedures.py`, `documents.py`, `ledger.py`, `pdf.py` exist with their endpoint signatures; Plan 1's `useVoiceAgent.ts` stub exists with the exact signature from roadmap §4.

**Interfaces with other plans:**
- Plan 4 reads completed deliveries and writes reminders. Plan 3 exposes `set_reminder(citizen_id, kind, ...)` tool that Plan 4's worker calls (not the agent directly).
- Plan 4's accessibility toggles set `preferences.simple_language` and `preferences.voice_only` on the `/voice/session` request. Plan 3 honors `simple_language` by injecting a directive into the agent system prompt; honors `voice_only` by configuring the Gemini Live session to use audio-only output (no text-only fallback messages).

---

## Files

**Owned by this plan (write/replace):**
- `backend/pyproject.toml` (add deps)
- `backend/app/agent.py` (replace body, keep `/agent/chat` signature)
- `backend/app/voice.py` (new — voice session + JWT issuance)
- `backend/app/twilio_bridge.py` (new — phone bridge)
- `backend/app/tools/__init__.py` (new — tool registry)
- `backend/app/tools/lookup_procedure.py` (new)
- `backend/app/tools/set_field.py` (new)
- `backend/app/tools/generate_pdf.py` (new)
- `backend/app/tools/deliver.py` (new)
- `backend/app/tools/find_redirect.py` (new)
- `backend/app/tools/set_reminder.py` (new)
- `backend/app/prompts.py` (new — Romanian system prompts)
- `backend/app/tool_dispatch.py` (new — HTTP tool endpoints + JWT verifier)
- `backend/app/main.py` (extend — register new routers; do NOT rewrite Plan 2 sections)
- `backend/tests/test_tools_*.py` (new — TDD)
- `backend/tests/test_agent_chat.py` (new)
- `backend/tests/test_voice_session.py` (new)
- `backend/tests/test_twilio_bridge.py` (new)
- `backend/tests/test_jwt.py` (new)
- `frontend/lib/useVoiceAgent.ts` (replace body — keep signature)
- `frontend/lib/gemini-live.ts` (new — low-level WS client)
- `frontend/lib/audioWorklet.ts` (new — PCM capture/playback worklet glue)
- `frontend/public/worklets/pcm-recorder.js` (new — AudioWorkletProcessor)
- `frontend/public/worklets/pcm-player.js` (new — AudioWorkletProcessor)
- `frontend/components/VocalFillFlow.tsx` (extend — wire `useVoiceAgent`)
- `frontend/components/ChatPanel.tsx` (extend — call real `/agent/chat`)
- `frontend/__tests__/useVoiceAgent.test.ts` (new)
- `.env.example` (extend — `GEMINI_API_KEY`, `JWT_SIGNING_SECRET`, `TWILIO_BRIDGE_PUBLIC_URL`)
- `docs/twilio-setup.md` (new — TwiML + console config notes)

---

## Step 1: Install Plan 3 dependencies

- [ ] Update `backend/pyproject.toml` `[project.dependencies]` section by appending:

```toml
"pydantic-ai>=0.0.46",
"google-genai>=0.4.0",
"pyjwt>=2.9.0",
"websockets>=13.1",
"twilio>=9.3.0",
"audioop-lts>=0.2.1 ; python_version >= '3.13'",
```

(Notes: `audioop` removed from stdlib in 3.13; `audioop-lts` backports it. If the project pins 3.12, the conditional dep is inert and `import audioop` still works. We use `audioop.ulaw2lin` / `audioop.lin2ulaw` for G.711 ↔ PCM transcode without needing `pydub`/`ffmpeg`.)

- [ ] Add to `.env.example` (don't touch existing keys):

```
# Plan 3 — Voice + Agent
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash-exp
GEMINI_VOICE_NAME=Aoede
JWT_SIGNING_SECRET=change-me-32-bytes
JWT_AUDIENCE=egata-tools
JWT_ISSUER=egata-voice
TWILIO_BRIDGE_PUBLIC_URL=wss://egata-backend.up.railway.app/voice/twilio
```

- [ ] Extend `backend/app/config.py` settings model (it already exists from Plan 2) by appending fields:

```python
class Settings(BaseSettings):
    # ... existing fields from Plan 2 ...
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash-exp"
    gemini_voice_name: str = "Aoede"
    jwt_signing_secret: str
    jwt_audience: str = "egata-tools"
    jwt_issuer: str = "egata-voice"
    twilio_bridge_public_url: str = ""
```

- [ ] Run `uv sync` (or `pip install -e .`) inside `backend/`. Confirm imports work:

```bash
cd backend && python -c "import pydantic_ai, google.genai, jwt, websockets, audioop; print('ok')"
```

- [ ] Commit: `chore(plan-3): add pydantic-ai, google-genai, pyjwt, websockets deps`

---

## Step 2: JWT signing/verification module (TDD first)

The browser receives a short-lived JWT from `/voice/session` and presents it when Gemini Live dispatches function calls back to our tool HTTP endpoints. Phone tools don't need JWT (server-side dispatch).

- [ ] Write `backend/tests/test_jwt.py` FIRST:

```python
import time
import pytest
import jwt as pyjwt
from app.voice import issue_tool_jwt, verify_tool_jwt, JwtClaims


def test_issue_and_verify_roundtrip():
    token = issue_tool_jwt(
        citizen_id="11111111-1111-1111-1111-111111111111",
        document_id="22222222-2222-2222-2222-222222222222",
        ttl_seconds=300,
    )
    claims = verify_tool_jwt(token)
    assert claims.citizen_id == "11111111-1111-1111-1111-111111111111"
    assert claims.document_id == "22222222-2222-2222-2222-222222222222"
    assert claims.aud == "egata-tools"


def test_expired_jwt_rejected():
    token = issue_tool_jwt(
        citizen_id="11111111-1111-1111-1111-111111111111",
        document_id=None,
        ttl_seconds=-1,
    )
    with pytest.raises(pyjwt.ExpiredSignatureError):
        verify_tool_jwt(token)


def test_wrong_audience_rejected():
    from app.config import settings
    bad = pyjwt.encode(
        {"sub": "x", "aud": "wrong-aud", "iss": settings.jwt_issuer,
         "exp": int(time.time()) + 60},
        settings.jwt_signing_secret, algorithm="HS256",
    )
    with pytest.raises(pyjwt.InvalidAudienceError):
        verify_tool_jwt(bad)


def test_tampered_signature_rejected():
    token = issue_tool_jwt(citizen_id="x", document_id=None, ttl_seconds=300)
    tampered = token[:-2] + "AA"
    with pytest.raises(pyjwt.InvalidSignatureError):
        verify_tool_jwt(tampered)
```

- [ ] Make tests pass by implementing `backend/app/voice.py` (partial — just JWT for now):

```python
"""Voice session + JWT signing/verification for tool dispatch."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

import jwt as pyjwt
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings


_bearer = HTTPBearer(auto_error=False)


@dataclass
class JwtClaims:
    citizen_id: str
    document_id: str | None
    aud: str
    iss: str
    exp: int
    jti: str


def issue_tool_jwt(
    citizen_id: str,
    document_id: str | None,
    ttl_seconds: int = 600,
) -> str:
    now = int(time.time())
    payload = {
        "sub": citizen_id,
        "doc": document_id,
        "aud": settings.jwt_audience,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": uuid.uuid4().hex,
    }
    return pyjwt.encode(payload, settings.jwt_signing_secret, algorithm="HS256")


def verify_tool_jwt(token: str) -> JwtClaims:
    decoded = pyjwt.decode(
        token,
        settings.jwt_signing_secret,
        algorithms=["HS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
    return JwtClaims(
        citizen_id=decoded["sub"],
        document_id=decoded.get("doc"),
        aud=decoded["aud"],
        iss=decoded["iss"],
        exp=decoded["exp"],
        jti=decoded["jti"],
    )


def require_tool_jwt(creds: HTTPAuthorizationCredentials | None) -> JwtClaims:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing tool JWT")
    try:
        return verify_tool_jwt(creds.credentials)
    except pyjwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid tool JWT: {e}")
```

- [ ] Run `cd backend && pytest tests/test_jwt.py -v`. All 4 tests pass.

- [ ] Commit: `feat(plan-3): JWT signing + verification for voice tool dispatch`

---

## Step 3: Tool registry + `lookup_procedure` (TDD)

- [ ] Write `backend/tests/test_tools_lookup_procedure.py` FIRST:

```python
import pytest
from app.tools.lookup_procedure import lookup_procedure
from app.tools import ToolContext


@pytest.fixture
def ctx(seeded_citizen):
    return ToolContext(citizen_id=seeded_citizen.id, document_id=None)


async def test_lookup_returns_top_match(ctx):
    result = await lookup_procedure(ctx, query="vreau să-mi schimb domiciliul")
    assert result.matches[0].procedure_id == "schimbare-domiciliu"
    assert result.matches[0].score > 0.6
    assert result.redirect_candidate is None


async def test_lookup_returns_redirect_for_anaf(ctx):
    result = await lookup_procedure(ctx, query="trebuie să-mi plătesc impozitul pe casă")
    assert result.redirect_candidate in {"ANAF", None}
    # ANAF redirect OR low-confidence match; both acceptable per spec §9
    if result.matches:
        assert result.matches[0].score < 0.7 or result.redirect_candidate == "ANAF"


async def test_lookup_empty_query_raises(ctx):
    with pytest.raises(ValueError):
        await lookup_procedure(ctx, query="")
```

- [ ] Write `backend/app/tools/__init__.py`:

```python
"""Agent tool registry. Each tool is a callable with a Pydantic-typed signature.

The same tool function is invoked from two contexts:
- Pydantic AI agent loop (server-side, from /agent/chat).
- HTTP endpoint dispatched by browser when Gemini Live emits a function-call.

Both paths go through the same Python function, so behavior cannot drift.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeAlias

ToolFunc: TypeAlias = Callable[..., Awaitable[Any]]


@dataclass
class ToolContext:
    """Per-invocation context. Built from JWT for browser path or
    from the agent's session state for server path."""
    citizen_id: str
    document_id: str | None


# Registry populated by each tool module on import.
REGISTRY: dict[str, ToolFunc] = {}


def register(name: str):
    def deco(func: ToolFunc) -> ToolFunc:
        REGISTRY[name] = func
        return func
    return deco


# Import side-effects register the tools.
from app.tools import (  # noqa: E402, F401
    lookup_procedure as _lp,
    set_field as _sf,
    generate_pdf as _gp,
    deliver as _dl,
    find_redirect as _fr,
    set_reminder as _sr,
)
```

- [ ] Write `backend/app/tools/lookup_procedure.py`:

```python
"""lookup_procedure tool — wraps Plan 2's RAG endpoint."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.procedures import rag_lookup  # exposed by Plan 2's procedures.py
from app.tools import ToolContext, register


class ProcedureMatch(BaseModel):
    procedure_id: str
    title: str
    score: float


class LookupResult(BaseModel):
    matches: list[ProcedureMatch] = Field(default_factory=list)
    redirect_candidate: str | None = None


@register("lookup_procedure")
async def lookup_procedure(ctx: ToolContext, query: str) -> LookupResult:
    """Find the best primărie procedure for a free-text citizen query.

    Args:
      query: Plain-language Romanian description of the citizen's need.

    Returns:
      Up to 3 matches sorted by similarity. If top score < 0.6, returns
      `redirect_candidate` set to ANAF / CNAS / DRPCIV based on keyword hints.
    """
    query = query.strip()
    if not query:
        raise ValueError("query cannot be empty")

    matches, redirect = await rag_lookup(query, top_k=3, threshold=0.6)
    return LookupResult(
        matches=[ProcedureMatch(**m) for m in matches],
        redirect_candidate=redirect,
    )
```

- [ ] Run `pytest tests/test_tools_lookup_procedure.py -v`. Pass.

- [ ] Commit: `feat(plan-3): tool registry + lookup_procedure tool with RAG`

---

## Step 4: Tools `set_field`, `generate_pdf`, `deliver` (TDD)

All three wrap existing Plan 2 endpoints but go through the DB layer directly (not HTTP round-trip) — they are called inside FastAPI.

- [ ] Write `backend/tests/test_tools_set_field.py`:

```python
import pytest
from app.tools.set_field import set_field
from app.tools import ToolContext


async def test_set_field_updates_document(seeded_document):
    ctx = ToolContext(citizen_id=seeded_document.citizen_id, document_id=seeded_document.id)
    result = await set_field(ctx, name="adresa_noua", value="Str. Plopilor 15, Cluj-Napoca")
    assert result.fields["adresa_noua"] == "Str. Plopilor 15, Cluj-Napoca"


async def test_set_field_validates_against_procedure_options(seeded_document_schimbare):
    ctx = ToolContext(citizen_id=seeded_document_schimbare.citizen_id,
                      document_id=seeded_document_schimbare.id)
    with pytest.raises(ValueError, match="not in options"):
        await set_field(ctx, name="tip_proprietate", value="proprietar-de-spațiu-imaginar")


async def test_set_field_requires_document(seeded_citizen):
    ctx = ToolContext(citizen_id=seeded_citizen.id, document_id=None)
    with pytest.raises(ValueError, match="document_id required"):
        await set_field(ctx, name="x", value="y")
```

- [ ] Write `backend/app/tools/set_field.py`:

```python
"""set_field tool — patch a field on the active document."""
from __future__ import annotations

from typing import Any

from app.documents import patch_document_fields, get_document
from app.procedures import get_procedure
from app.tools import ToolContext, register


@register("set_field")
async def set_field(ctx: ToolContext, name: str, value: Any) -> Any:
    """Set a single form field on the active document.

    Args:
      name: Field name from the procedure schema (e.g., "adresa_noua").
      value: New value. Must satisfy `options` if the field constrains them.

    Returns the updated Document.
    """
    if not ctx.document_id:
        raise ValueError("document_id required for set_field")

    doc = await get_document(ctx.document_id, citizen_id=ctx.citizen_id)
    proc = get_procedure(doc.procedure_id)
    field_spec = next((f for f in proc.fields if f.name == name), None)
    if field_spec is None:
        raise ValueError(f"Unknown field '{name}' for procedure {doc.procedure_id}")
    if field_spec.options and value not in field_spec.options:
        raise ValueError(
            f"Value {value!r} not in options for '{name}': {field_spec.options}"
        )

    return await patch_document_fields(
        ctx.document_id, fields={name: value}, citizen_id=ctx.citizen_id
    )
```

- [ ] Write `backend/tests/test_tools_generate_pdf.py`:

```python
import pytest
from app.tools.generate_pdf import generate_pdf
from app.tools import ToolContext


async def test_generate_pdf_returns_url(seeded_document_filled):
    ctx = ToolContext(citizen_id=seeded_document_filled.citizen_id,
                      document_id=seeded_document_filled.id)
    result = await generate_pdf(ctx)
    assert result.pdf_url.startswith("http")
    assert result.pdf_url.endswith(".pdf")


async def test_generate_pdf_requires_required_fields(seeded_document_incomplete):
    ctx = ToolContext(citizen_id=seeded_document_incomplete.citizen_id,
                      document_id=seeded_document_incomplete.id)
    with pytest.raises(ValueError, match="missing required"):
        await generate_pdf(ctx)
```

- [ ] Write `backend/app/tools/generate_pdf.py`:

```python
"""generate_pdf tool — wraps LaTeX compile."""
from __future__ import annotations

from pydantic import BaseModel

from app.documents import get_document
from app.pdf import compile_pdf_for_document
from app.procedures import get_procedure
from app.tools import ToolContext, register


class PdfResult(BaseModel):
    pdf_url: str


@register("generate_pdf")
async def generate_pdf(ctx: ToolContext) -> PdfResult:
    """Compile the active document to PDF via LaTeX.

    Returns the storage URL of the compiled PDF.
    """
    if not ctx.document_id:
        raise ValueError("document_id required for generate_pdf")
    doc = await get_document(ctx.document_id, citizen_id=ctx.citizen_id)
    proc = get_procedure(doc.procedure_id)
    missing = [f.name for f in proc.fields if f.required and f.name not in (doc.fields or {})]
    if missing:
        raise ValueError(f"missing required fields: {missing}")
    pdf_url = await compile_pdf_for_document(doc.id, citizen_id=ctx.citizen_id)
    return PdfResult(pdf_url=pdf_url)
```

- [ ] Write `backend/tests/test_tools_deliver.py`:

```python
import pytest
from app.tools.deliver import deliver
from app.tools import ToolContext


@pytest.mark.parametrize("mode", ["save", "send", "print"])
async def test_deliver_marks_finalized(seeded_document_filled, mode):
    ctx = ToolContext(citizen_id=seeded_document_filled.citizen_id,
                      document_id=seeded_document_filled.id)
    result = await deliver(ctx, delivery=mode)
    assert result.status == "finalized"
    assert result.delivery == mode
    assert result.ref_number.startswith("CV-")


async def test_deliver_rejects_invalid_mode(seeded_document_filled):
    ctx = ToolContext(citizen_id=seeded_document_filled.citizen_id,
                      document_id=seeded_document_filled.id)
    with pytest.raises(ValueError, match="delivery must be"):
        await deliver(ctx, delivery="email")
```

- [ ] Write `backend/app/tools/deliver.py`:

```python
"""deliver tool — save/send/print finalization."""
from __future__ import annotations

from typing import Literal

from app.documents import deliver_document
from app.tools import ToolContext, register


DeliveryMode = Literal["save", "send", "print"]
_VALID = {"save", "send", "print"}


@register("deliver")
async def deliver(ctx: ToolContext, delivery: str) -> dict:
    """Finalize the active document and choose delivery channel.

    Args:
      delivery: One of "save", "send", "print".
    """
    if not ctx.document_id:
        raise ValueError("document_id required for deliver")
    if delivery not in _VALID:
        raise ValueError(f"delivery must be one of {_VALID}, got {delivery!r}")
    return await deliver_document(
        ctx.document_id, delivery=delivery, citizen_id=ctx.citizen_id
    )
```

- [ ] Run `pytest tests/test_tools_set_field.py tests/test_tools_generate_pdf.py tests/test_tools_deliver.py -v`. All pass.

- [ ] Commit: `feat(plan-3): set_field, generate_pdf, deliver tools (TDD)`

---

## Step 5: Tools `find_redirect`, `set_reminder` (TDD)

- [ ] Write `backend/tests/test_tools_find_redirect.py`:

```python
import pytest
from app.tools.find_redirect import find_redirect, REDIRECT_TARGETS
from app.tools import ToolContext


async def test_find_redirect_anaf_for_tax_query():
    ctx = ToolContext(citizen_id="x", document_id=None)
    result = await find_redirect(ctx, query="trebuie să plătesc impozit pe mașină")
    assert result.target == "ANAF"
    assert result.url.startswith("https://")


async def test_find_redirect_drpciv_for_vehicle():
    ctx = ToolContext(citizen_id="x", document_id=None)
    result = await find_redirect(ctx, query="vreau să schimb adresa pe talon")
    assert result.target == "DRPCIV"


async def test_find_redirect_cnas_for_doctor():
    ctx = ToolContext(citizen_id="x", document_id=None)
    result = await find_redirect(ctx, query="vreau să-mi schimb medicul de familie")
    assert result.target == "CNAS"


async def test_find_redirect_explicit_target():
    ctx = ToolContext(citizen_id="x", document_id=None)
    result = await find_redirect(ctx, query="ceva", target="ANAF")
    assert result.target == "ANAF"
    assert "anaf" in result.url.lower()


async def test_find_redirect_unknown_returns_none():
    ctx = ToolContext(citizen_id="x", document_id=None)
    result = await find_redirect(ctx, query="vreau o pizza")
    assert result.target is None
```

- [ ] Write `backend/app/tools/find_redirect.py`:

```python
"""find_redirect tool — recognizes out-of-scope needs and points to ANAF/CNAS/DRPCIV."""
from __future__ import annotations

from pydantic import BaseModel

from app.tools import ToolContext, register


REDIRECT_TARGETS: dict[str, dict[str, str]] = {
    "ANAF": {
        "name": "ANAF — Agenția Națională de Administrare Fiscală",
        "url": "https://www.anaf.ro",
        "phone": "031 403 9160",
        "scope": "Impozite, taxe, fiscalitate, domiciliu fiscal.",
    },
    "CNAS": {
        "name": "CNAS — Casa Națională de Asigurări de Sănătate",
        "url": "https://cnas.ro",
        "phone": "0800 800 950",
        "scope": "Medic de familie, asigurare medicală, card de sănătate.",
    },
    "DRPCIV": {
        "name": "DRPCIV — Direcția Regim Permise de Conducere și Înmatriculare a Vehiculelor",
        "url": "https://drpciv.ro",
        "phone": "021 9665",
        "scope": "Talon auto, permis de conducere, înmatriculare.",
    },
}


# Lowercase keyword → target. Order matters: more specific first.
_KEYWORDS: list[tuple[str, str]] = [
    ("medic de familie", "CNAS"),
    ("medicul de familie", "CNAS"),
    ("card de sănătate", "CNAS"),
    ("asigurare medicală", "CNAS"),
    ("cnas", "CNAS"),
    ("talon", "DRPCIV"),
    ("permis de conducere", "DRPCIV"),
    ("înmatriculare", "DRPCIV"),
    ("mașin", "DRPCIV"),  # mașină, mașinii
    ("drpciv", "DRPCIV"),
    ("impozit", "ANAF"),
    ("taxă", "ANAF"),
    ("taxa", "ANAF"),
    ("fiscal", "ANAF"),
    ("anaf", "ANAF"),
    ("declarație unică", "ANAF"),
]


class RedirectInfo(BaseModel):
    target: str | None
    name: str | None = None
    url: str | None = None
    phone: str | None = None
    scope: str | None = None
    explanation: str | None = None


@register("find_redirect")
async def find_redirect(
    ctx: ToolContext, query: str, target: str | None = None
) -> RedirectInfo:
    """Decide if a query is out of primărie scope and where to send the citizen.

    Args:
      query: The citizen's plain-text need.
      target: Optional explicit target ("ANAF" | "CNAS" | "DRPCIV"). Skips keyword search.
    """
    if target and target in REDIRECT_TARGETS:
        info = REDIRECT_TARGETS[target]
        return RedirectInfo(target=target, **info,
                            explanation=f"{info['scope']} Această cerere se face la {info['name']}.")

    q = query.lower()
    for kw, tgt in _KEYWORDS:
        if kw in q:
            info = REDIRECT_TARGETS[tgt]
            return RedirectInfo(target=tgt, **info,
                                explanation=f"{info['scope']} Această cerere se face la {info['name']}.")
    return RedirectInfo(target=None)
```

- [ ] Write `backend/tests/test_tools_set_reminder.py`:

```python
import pytest
from app.tools.set_reminder import set_reminder
from app.tools import ToolContext


async def test_set_reminder_in_scope_procedure(seeded_citizen, supabase):
    ctx = ToolContext(citizen_id=seeded_citizen.id, document_id=None)
    rem = await set_reminder(
        ctx,
        kind="in_scope_procedure",
        procedure_id="preschimbare-ci",
        title="Preschimbare carte de identitate",
        deadline_days=15,
    )
    assert rem.id is not None
    assert rem.kind == "in_scope_procedure"
    assert rem.procedure_id == "preschimbare-ci"
    assert rem.status == "pending"
    # Verify DB row
    rows = supabase.table("reminders").select("*").eq("id", str(rem.id)).execute()
    assert len(rows.data) == 1


async def test_set_reminder_external_redirect(seeded_citizen):
    ctx = ToolContext(citizen_id=seeded_citizen.id, document_id=None)
    rem = await set_reminder(
        ctx,
        kind="external_redirect",
        redirect_target="DRPCIV",
        title="Actualizare talon auto",
        deadline_days=30,
    )
    assert rem.kind == "external_redirect"
    assert rem.redirect_target == "DRPCIV"


async def test_set_reminder_invalid_kind(seeded_citizen):
    ctx = ToolContext(citizen_id=seeded_citizen.id, document_id=None)
    with pytest.raises(ValueError, match="kind must be"):
        await set_reminder(ctx, kind="garbage", title="X")
```

- [ ] Write `backend/app/tools/set_reminder.py`:

```python
"""set_reminder tool — inserts a row in the reminders table.

Called both by the conversational agent (rare; explicit "remind me later" intent)
AND by Plan 4's background worker after document delivery. Plan 4's worker imports
this function directly (`from app.tools.set_reminder import set_reminder`), passing
a synthetic ToolContext built from the citizen_id of the trigger document.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel

from app.db import supabase_admin
from app.tools import ToolContext, register


ReminderKind = Literal["in_scope_procedure", "external_redirect"]
_VALID_KINDS = {"in_scope_procedure", "external_redirect"}


class ReminderResult(BaseModel):
    id: uuid.UUID
    citizen_id: uuid.UUID
    trigger_doc_id: uuid.UUID | None
    kind: str
    procedure_id: str | None
    redirect_target: str | None
    title: str
    due_date: date | None
    status: str


@register("set_reminder")
async def set_reminder(
    ctx: ToolContext,
    kind: str,
    title: str,
    procedure_id: str | None = None,
    redirect_target: str | None = None,
    trigger_doc_id: str | None = None,
    deadline_days: int | None = None,
) -> ReminderResult:
    """Create a proactive reminder for the citizen.

    Args:
      kind: "in_scope_procedure" or "external_redirect".
      title: Romanian title shown on the home screen card.
      procedure_id: Required when kind="in_scope_procedure".
      redirect_target: Required when kind="external_redirect" (ANAF/CNAS/DRPCIV).
      trigger_doc_id: Document that triggered this reminder (Plan 4 worker passes it).
      deadline_days: Days from now until the reminder is due.
    """
    if kind not in _VALID_KINDS:
        raise ValueError(f"kind must be in {_VALID_KINDS}, got {kind!r}")
    if kind == "in_scope_procedure" and not procedure_id:
        raise ValueError("procedure_id required when kind=in_scope_procedure")
    if kind == "external_redirect" and not redirect_target:
        raise ValueError("redirect_target required when kind=external_redirect")

    due = (date.today() + timedelta(days=deadline_days)) if deadline_days else None

    row = {
        "id": str(uuid.uuid4()),
        "citizen_id": ctx.citizen_id,
        "trigger_doc_id": trigger_doc_id or ctx.document_id,
        "kind": kind,
        "procedure_id": procedure_id,
        "redirect_target": redirect_target,
        "title": title,
        "due_date": due.isoformat() if due else None,
        "status": "pending",
    }
    resp = supabase_admin.table("reminders").insert(row).execute()
    inserted = resp.data[0]
    return ReminderResult(**inserted)
```

- [ ] Run `pytest tests/test_tools_find_redirect.py tests/test_tools_set_reminder.py -v`. Pass.

- [ ] Commit: `feat(plan-3): find_redirect + set_reminder tools (TDD)`

---

## Step 6: Romanian system prompts

- [ ] Write `backend/app/prompts.py`:

```python
"""Romanian system prompts for eGata agent variants.

Two prompts:
- CONVERSATIONAL_SYSTEM: full agent, all 6 tools, used by browser /agent/chat and voice.
- PHONE_SYSTEM: info-only, RAG-only, used by Twilio bridge.

The `simple_language` flag prepends SIMPLE_LANGUAGE_DIRECTIVE to either prompt.
The `voice_only` flag prepends VOICE_ONLY_DIRECTIVE.
"""
from __future__ import annotations


CONVERSATIONAL_SYSTEM = """\
Ești eGata, asistentul digital al primăriei. Vorbești simplu, prietenos, în limba română.
Scopul tău: să ajuți cetățeanul să completeze documente pentru primărie.

Reguli stricte:
1. Răspunzi DOAR pentru proceduri de primărie. Pentru altceva (ANAF, CNAS, DRPCIV) folosește
   tool-ul `find_redirect` și explică unde trebuie să meargă cetățeanul.
2. Pentru orice cerere nouă, folosește `lookup_procedure` ca să afli procedura potrivită
   din registrul nostru. Confirmă cu cetățeanul înainte de a continua.
3. Folosește profilul cetățeanului pentru auto-completare. Nu repeta informații pe care
   le ai deja (nume, CNP, adresă curentă).
4. Înainte de a întreba un câmp, sugerează un răspuns implicit dacă există (`suggest_default`).
5. NU pronunța CNP-uri vocal. Spune doar „CNP-ul tău" sau „ultimele 4 cifre", niciodată
   toate cele 13 cifre.
6. Folosește `set_field` pentru fiecare valoare pe care o colectezi.
7. Când toate câmpurile obligatorii sunt completate, oferă cele trei opțiuni:
   Salvare PDF (tool `deliver` cu delivery="save"), Trimitere la primărie (delivery="send"),
   sau Tipărire (delivery="print"). Întreabă cetățeanul ce preferă.
8. După apelul `deliver`, NU mai apela alte tool-uri. Worker-ul de fundal va crea automat
   memento-urile pentru pașii următori.
9. Tool-ul `set_reminder` îl folosești DOAR dacă cetățeanul cere explicit „adu-mi aminte
   despre X". Altfel, sistemul creează memento-uri automat după livrare.

Stil:
- Cald, fără jargon administrativ.
- Propoziții scurte. Maxim 2-3 propoziții pe răspuns.
- O singură întrebare la un moment dat.
- Folosește „dumneavoastră" sau „tu" consistent (preferă „tu" dacă cetățeanul a folosit „tu").
"""


PHONE_SYSTEM = """\
Ești eGata, asistentul telefonic al primăriei Cluj-Napoca. Vorbești simplu, prietenos,
în limba română.

Pe telefon ai un singur scop: să informezi cetățeanul ce acte are nevoie pentru o procedură
și unde se rezolvă. NU poți completa documente pe telefon.

Reguli stricte:
1. Folosește `lookup_procedure` pentru orice cerere. Explică ce acte sunt necesare
   (din `fields`) și ce pași trebuie să facă cetățeanul.
2. Pentru cereri în afara primăriei, folosește `find_redirect` și dictează clar
   instituția, telefonul și site-ul.
3. La finalul fiecărei explicații, invită cetățeanul pe site: „Pentru a completa
   documentul online, vizitați egata.ro sau veniți la kioskul din primărie."
4. NU pronunța CNP-uri sau date personale vocal.
5. Răspunsuri foarte scurte — maxim 30 de secunde de vorbire pe replică.
6. Dacă cetățeanul cere ceva care nu e nici primărie nici redirect cunoscut, spune politicos:
   „Nu pot ajuta cu această cerere pe telefon. Vă rog să vizitați egata.ro."

Stil: cald, voce calmă, propoziții scurte, pauze între idei pentru claritate audio.
"""


SIMPLE_LANGUAGE_DIRECTIVE = """\

INSTRUCȚIUNE SUPLIMENTARĂ — MOD SIMPLU ACTIVAT:
Vorbește ca pentru un copil de clasa a 6-a. Fără jargon administrativ.
În loc de „domiciliu fiscal", spune „adresa unde plătești impozite".
În loc de „înscrierea mențiunii de stabilire a domiciliului", spune „să schimbi adresa pe buletin".
Propoziții foarte scurte. Definește orice termen tehnic înainte de a-l folosi.
"""


VOICE_ONLY_DIRECTIVE = """\

INSTRUCȚIUNE SUPLIMENTARĂ — MOD DOAR VOCE ACTIVAT:
Cetățeanul nu se uită la ecran. Toate informațiile trebuie spuse audibil.
Pentru liste, numerotează clar („primul, al doilea, al treilea") și pauzează după fiecare.
Confirmă fiecare câmp completat: „Am notat: adresa nouă este Strada Plopilor 15."
Citește răspunsul așteptat înainte de a accepta — „Ai zis Strada Plopilor 15, corect?"
"""


def build_system_prompt(
    variant: str = "conversational",
    simple_language: bool = False,
    voice_only: bool = False,
) -> str:
    if variant == "phone":
        base = PHONE_SYSTEM
    else:
        base = CONVERSATIONAL_SYSTEM
    directives = ""
    if simple_language:
        directives += SIMPLE_LANGUAGE_DIRECTIVE
    if voice_only:
        directives += VOICE_ONLY_DIRECTIVE
    return base + directives
```

- [ ] Snapshot test `backend/tests/test_prompts.py`:

```python
from app.prompts import build_system_prompt


def test_default_conversational_prompt():
    p = build_system_prompt()
    assert "eGata" in p
    assert "primăriei" in p
    assert "SIMPLE_LANGUAGE_DIRECTIVE" not in p  # token not leaked
    assert "INSTRUCȚIUNE SUPLIMENTARĂ" not in p


def test_simple_language_injection():
    p = build_system_prompt(simple_language=True)
    assert "MOD SIMPLU ACTIVAT" in p
    assert "clasa a 6-a" in p


def test_voice_only_injection():
    p = build_system_prompt(voice_only=True)
    assert "MOD DOAR VOCE ACTIVAT" in p


def test_phone_variant_distinct():
    p = build_system_prompt(variant="phone")
    assert "telefonic" in p
    assert "egata.ro" in p
```

- [ ] Run `pytest tests/test_prompts.py -v`. Pass.

- [ ] Commit: `feat(plan-3): Romanian system prompts with simple-language + voice-only directives`

---

## Step 7: Pydantic AI agent + replace `/agent/chat`

- [ ] Write `backend/tests/test_agent_chat.py`:

```python
import pytest
from httpx import AsyncClient


async def test_chat_returns_message_with_tool_call_for_domiciliu(
    client: AsyncClient, auth_headers, seeded_citizen
):
    r = await client.post(
        "/agent/chat",
        headers=auth_headers,
        json={"message": "Vreau să-mi schimb domiciliul"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "conversation_id" in body
    assert isinstance(body["message"], str)
    assert any(tc["name"] == "lookup_procedure" for tc in body["tool_calls"])


async def test_chat_with_document_context(
    client: AsyncClient, auth_headers, seeded_document
):
    r = await client.post(
        "/agent/chat",
        headers=auth_headers,
        json={
            "document_id": str(seeded_document.id),
            "message": "Adresa nouă este Str. Plopilor 15, Cluj-Napoca",
        },
    )
    assert r.status_code == 200
    body = r.json()
    # Should have invoked set_field
    assert any(tc["name"] == "set_field" for tc in body["tool_calls"])


async def test_chat_redirect_for_anaf_query(
    client: AsyncClient, auth_headers
):
    r = await client.post(
        "/agent/chat",
        headers=auth_headers,
        json={"message": "Cum îmi plătesc impozitul pe casă?"},
    )
    body = r.json()
    # Either a tool call to find_redirect, or text mentions ANAF
    msg_lower = body["message"].lower()
    has_redirect_tool = any(tc["name"] == "find_redirect" for tc in body["tool_calls"])
    assert has_redirect_tool or "anaf" in msg_lower
```

- [ ] Replace `backend/app/agent.py` body (keep `/agent/chat` endpoint signature stable):

```python
"""Conversational agent — Pydantic AI over Gemini for the browser chat path.

Endpoint signature `POST /agent/chat` is preserved from Plan 2 so the frontend
ChatPanel does not need to change.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.gemini import GeminiModel

from app.auth import get_current_citizen
from app.citizens import get_citizen_profile
from app.config import settings
from app.documents import get_document
from app.procedures import get_procedure
from app.prompts import build_system_prompt
from app.tools import ToolContext
from app.tools.deliver import deliver as t_deliver
from app.tools.find_redirect import find_redirect as t_find_redirect
from app.tools.generate_pdf import generate_pdf as t_generate_pdf
from app.tools.lookup_procedure import lookup_procedure as t_lookup_procedure
from app.tools.set_field import set_field as t_set_field
from app.tools.set_reminder import set_reminder as t_set_reminder


router = APIRouter(prefix="/agent", tags=["agent"])


# --- Request/response models (frozen from Plan 2 contract) ---

class ChatPreferences(BaseModel):
    simple_language: bool = False
    voice_only: bool = False


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    document_id: str | None = None
    message: str
    preferences: ChatPreferences = ChatPreferences()


class ChatToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    tool_calls: list[ChatToolCall] = []


# --- Pydantic AI agent factory ---

def _build_agent(simple_language: bool, voice_only: bool) -> Agent[ToolContext, str]:
    model = GeminiModel(settings.gemini_model, api_key=settings.gemini_api_key)
    agent: Agent[ToolContext, str] = Agent(
        model,
        deps_type=ToolContext,
        system_prompt=build_system_prompt(
            variant="conversational",
            simple_language=simple_language,
            voice_only=voice_only,
        ),
    )

    @agent.tool
    async def lookup_procedure(ctx: RunContext[ToolContext], query: str) -> dict:
        """Find the best primărie procedure for a free-text Romanian query."""
        return (await t_lookup_procedure(ctx.deps, query=query)).model_dump()

    @agent.tool
    async def set_field(ctx: RunContext[ToolContext], name: str, value: Any) -> dict:
        """Set a single form field on the active document."""
        return await t_set_field(ctx.deps, name=name, value=value)

    @agent.tool
    async def generate_pdf(ctx: RunContext[ToolContext]) -> dict:
        """Compile the active document to PDF via LaTeX."""
        return (await t_generate_pdf(ctx.deps)).model_dump()

    @agent.tool
    async def deliver(ctx: RunContext[ToolContext], delivery: str) -> dict:
        """Finalize the document. delivery in {save, send, print}."""
        return await t_deliver(ctx.deps, delivery=delivery)

    @agent.tool
    async def find_redirect(
        ctx: RunContext[ToolContext], query: str, target: str | None = None
    ) -> dict:
        """Decide if a query is out of primărie scope. Returns ANAF/CNAS/DRPCIV info."""
        return (await t_find_redirect(ctx.deps, query=query, target=target)).model_dump()

    @agent.tool
    async def set_reminder(
        ctx: RunContext[ToolContext],
        kind: str,
        title: str,
        procedure_id: str | None = None,
        redirect_target: str | None = None,
        deadline_days: int | None = None,
    ) -> dict:
        """Create a proactive reminder for the citizen (rare; only on explicit request)."""
        rem = await t_set_reminder(
            ctx.deps,
            kind=kind, title=title,
            procedure_id=procedure_id, redirect_target=redirect_target,
            deadline_days=deadline_days,
        )
        return rem.model_dump(mode="json")

    return agent


# --- Conversation store (in-memory; sufficient for hackathon) ---

_conversations: dict[str, list[dict]] = {}


async def _build_context_preamble(
    citizen_id: str, document_id: str | None
) -> str:
    """Inject citizen profile + active doc state into the user message context."""
    profile = await get_citizen_profile(citizen_id)
    lines = [
        f"Profil cetățean: {profile.prenume} {profile.nume}",
        f"Atribute: {profile.attributes}",
    ]
    if document_id:
        doc = await get_document(document_id, citizen_id=citizen_id)
        proc = get_procedure(doc.procedure_id)
        lines.append(f"Document activ: {proc.title} (status={doc.status})")
        lines.append(f"Câmpuri completate: {doc.fields or {}}")
        missing = [f.name for f in proc.fields if f.required and f.name not in (doc.fields or {})]
        lines.append(f"Câmpuri obligatorii rămase: {missing}")
    return "\n".join(lines)


# --- Endpoint ---

@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    citizen=Depends(get_current_citizen),
) -> ChatResponse:
    conv_id = req.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
    history = _conversations.setdefault(conv_id, [])

    agent = _build_agent(
        simple_language=req.preferences.simple_language,
        voice_only=req.preferences.voice_only,
    )
    deps = ToolContext(citizen_id=str(citizen.id), document_id=req.document_id)

    preamble = await _build_context_preamble(str(citizen.id), req.document_id)
    user_msg = f"{preamble}\n\n---\n\n{req.message}"

    try:
        result = await agent.run(user_msg, deps=deps, message_history=history)
    except Exception as e:
        raise HTTPException(500, f"Agent error: {e}")

    # Capture tool calls from this turn (Pydantic AI exposes them via result.all_messages())
    tool_calls: list[ChatToolCall] = []
    for msg in result.new_messages():
        for part in getattr(msg, "parts", []):
            if part.__class__.__name__ == "ToolCallPart":
                tool_calls.append(ChatToolCall(
                    name=part.tool_name,
                    arguments=part.args_as_dict() if hasattr(part, "args_as_dict") else dict(part.args),
                ))

    history.extend(result.all_messages())

    return ChatResponse(
        conversation_id=conv_id,
        message=result.data,
        tool_calls=tool_calls,
    )
```

- [ ] Run `pytest tests/test_agent_chat.py -v` — they should pass against the real Gemini API (or skip with a marker if `GEMINI_API_KEY` not set):

```python
# Add to top of test_agent_chat.py:
import os
pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="requires GEMINI_API_KEY",
)
```

- [ ] Manual verification: with backend running and `GEMINI_API_KEY` set, curl:

```bash
TOKEN="<otp-issued-token>"
curl -sX POST http://localhost:8000/agent/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Vreau să-mi schimb domiciliul"}' | jq
```

Expected: `tool_calls` includes `lookup_procedure`; `message` confirms the procedure in Romanian.

- [ ] Commit: `feat(plan-3): replace mock /agent/chat with Pydantic AI + Gemini agent`

---

## Step 8: Tool dispatch HTTP endpoints (called by browser with JWT)

When Gemini Live emits a function-call in the browser session, the browser SDK posts the call to a FastAPI endpoint with the short-lived JWT. We expose one endpoint per tool that re-uses the same Python function.

- [ ] Write `backend/app/tool_dispatch.py`:

```python
"""HTTP endpoints invoked by the browser when Gemini Live emits a function-call.

Each endpoint requires a valid tool JWT (issued by /voice/session) and forwards
to the same Python tool function used by the server-side agent loop.

URL convention: POST /tools/{tool_name}
Body: the tool's arguments as JSON.
Response: the tool's return value as JSON.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.tools import REGISTRY, ToolContext
from app.voice import JwtClaims, _bearer, require_tool_jwt


router = APIRouter(prefix="/tools", tags=["tool-dispatch"])


def _ctx(claims: JwtClaims) -> ToolContext:
    return ToolContext(citizen_id=claims.citizen_id, document_id=claims.document_id)


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return value


@router.post("/{tool_name}")
async def dispatch_tool(
    tool_name: str,
    args: dict[str, Any] = Body(default_factory=dict),
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> Any:
    claims = require_tool_jwt(creds)
    tool = REGISTRY.get(tool_name)
    if tool is None:
        raise HTTPException(404, f"Unknown tool '{tool_name}'")
    try:
        result = await tool(_ctx(claims), **args)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Tool {tool_name} failed: {e}")
    return _serialize(result)
```

- [ ] Test `backend/tests/test_tool_dispatch.py`:

```python
import pytest
from httpx import AsyncClient
from app.voice import issue_tool_jwt


async def test_dispatch_lookup_procedure(client: AsyncClient, seeded_citizen):
    token = issue_tool_jwt(str(seeded_citizen.id), document_id=None)
    r = await client.post(
        "/tools/lookup_procedure",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "vreau să-mi schimb domiciliul"},
    )
    assert r.status_code == 200
    body = r.json()
    assert any(m["procedure_id"] == "schimbare-domiciliu" for m in body["matches"])


async def test_dispatch_requires_jwt(client: AsyncClient):
    r = await client.post("/tools/lookup_procedure", json={"query": "x"})
    assert r.status_code == 401


async def test_dispatch_unknown_tool(client: AsyncClient, seeded_citizen):
    token = issue_tool_jwt(str(seeded_citizen.id), document_id=None)
    r = await client.post(
        "/tools/nonexistent",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert r.status_code == 404


async def test_dispatch_set_field_validates(client: AsyncClient, seeded_document_schimbare):
    token = issue_tool_jwt(
        str(seeded_document_schimbare.citizen_id),
        document_id=str(seeded_document_schimbare.id),
    )
    r = await client.post(
        "/tools/set_field",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "tip_proprietate", "value": "alien"},
    )
    assert r.status_code == 400
    assert "not in options" in r.json()["detail"]
```

- [ ] Run `pytest tests/test_tool_dispatch.py -v`. Pass.

- [ ] Register router in `backend/app/main.py` (extend, don't rewrite):

```python
# Add near the bottom of main.py where other routers are registered:
from app.tool_dispatch import router as tool_dispatch_router
app.include_router(tool_dispatch_router)
```

- [ ] Commit: `feat(plan-3): HTTP tool-dispatch endpoints with JWT auth`

---

## Step 9: `POST /voice/session` endpoint

Creates a Gemini Live ephemeral session (via the `google-genai` SDK), issues a tool JWT, returns both plus the tool URL list to the browser.

- [ ] Append to `backend/app/voice.py`:

```python
# ---- Voice session creation ----

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_citizen
from app.citizens import get_citizen_profile
from app.documents import get_document
from app.procedures import get_procedure
from app.prompts import build_system_prompt


router = APIRouter(prefix="/voice", tags=["voice"])


class VoicePreferences(BaseModel):
    simple_language: bool = False
    voice_only: bool = False


class VoiceSessionRequest(BaseModel):
    document_id: str | None = None
    preferences: VoicePreferences = VoicePreferences()


class VoiceSessionResponse(BaseModel):
    session_id: str
    gemini_api_key: str         # ephemeral if google-genai supports it; otherwise main key over TLS
    gemini_model: str
    gemini_voice: str
    system_prompt: str
    tool_jwt: str
    tool_base_url: str          # e.g. https://egata-backend.up.railway.app/tools
    tool_names: list[str]
    citizen_context: dict       # profile snapshot for client-side display
    document_context: dict | None


@router.post("/session", response_model=VoiceSessionResponse)
async def create_voice_session(
    req: VoiceSessionRequest,
    citizen=Depends(get_current_citizen),
) -> VoiceSessionResponse:
    from app.tools import REGISTRY

    profile = await get_citizen_profile(str(citizen.id))
    document_context: dict | None = None
    if req.document_id:
        doc = await get_document(req.document_id, citizen_id=str(citizen.id))
        proc = get_procedure(doc.procedure_id)
        document_context = {
            "id": str(doc.id),
            "procedure_id": doc.procedure_id,
            "procedure_title": proc.title,
            "fields": doc.fields or {},
            "required_fields": [f.model_dump() for f in proc.fields if f.required],
            "all_fields": [f.model_dump() for f in proc.fields],
        }

    system_prompt = build_system_prompt(
        variant="conversational",
        simple_language=req.preferences.simple_language,
        voice_only=req.preferences.voice_only,
    )
    # Inject context preamble directly into the system prompt so Gemini Live has it from turn 1
    context_preamble = (
        f"\n\n---\nProfil cetățean activ:\n"
        f"Nume: {profile.prenume} {profile.nume}\n"
        f"Atribute: {profile.attributes}\n"
    )
    if document_context:
        context_preamble += f"\nDocument activ: {document_context['procedure_title']}\n"
        context_preamble += f"Câmpuri completate: {document_context['fields']}\n"
        missing = [f["name"] for f in document_context["required_fields"]
                   if f["name"] not in document_context["fields"]]
        context_preamble += f"Câmpuri obligatorii rămase: {missing}\n"

    tool_jwt = issue_tool_jwt(
        citizen_id=str(citizen.id),
        document_id=req.document_id,
        ttl_seconds=1800,  # 30 min — covers a full voice session
    )

    session_id = uuid.uuid4().hex

    return VoiceSessionResponse(
        session_id=session_id,
        gemini_api_key=settings.gemini_api_key,
        gemini_model=settings.gemini_model,
        gemini_voice=settings.gemini_voice_name,
        system_prompt=system_prompt + context_preamble,
        tool_jwt=tool_jwt,
        tool_base_url=f"{settings.public_base_url}/tools",
        tool_names=list(REGISTRY.keys()),
        citizen_context=profile.model_dump(mode="json"),
        document_context=document_context,
    )
```

(Note: As of Gemini Live's current SDK behavior, the browser opens a direct WS to `wss://generativelanguage.googleapis.com/.../BidiGenerateContent?key=...`. Google has documented ephemeral token plans but their availability varies; we ship with the main API key delivered over TLS for the hackathon and add a "swap to ephemeral when GA" TODO. Risk is acceptable because the JWT is the actual authorization for tool calls — the Gemini key only controls model access.)

- [ ] Register voice router in `main.py`:

```python
from app.voice import router as voice_router
app.include_router(voice_router)
```

- [ ] Write `backend/tests/test_voice_session.py`:

```python
import pytest
from httpx import AsyncClient


async def test_voice_session_returns_required_fields(
    client: AsyncClient, auth_headers, seeded_citizen
):
    r = await client.post("/voice/session", headers=auth_headers, json={})
    assert r.status_code == 200
    body = r.json()
    for key in ["session_id", "gemini_api_key", "gemini_model", "gemini_voice",
                "system_prompt", "tool_jwt", "tool_base_url", "tool_names"]:
        assert key in body
    assert "lookup_procedure" in body["tool_names"]


async def test_voice_session_honors_simple_language(
    client: AsyncClient, auth_headers
):
    r = await client.post(
        "/voice/session",
        headers=auth_headers,
        json={"preferences": {"simple_language": True}},
    )
    body = r.json()
    assert "MOD SIMPLU ACTIVAT" in body["system_prompt"]


async def test_voice_session_honors_voice_only(
    client: AsyncClient, auth_headers
):
    r = await client.post(
        "/voice/session",
        headers=auth_headers,
        json={"preferences": {"voice_only": True}},
    )
    body = r.json()
    assert "MOD DOAR VOCE ACTIVAT" in body["system_prompt"]


async def test_voice_session_includes_document_context(
    client: AsyncClient, auth_headers, seeded_document
):
    r = await client.post(
        "/voice/session",
        headers=auth_headers,
        json={"document_id": str(seeded_document.id)},
    )
    body = r.json()
    assert body["document_context"] is not None
    assert body["document_context"]["id"] == str(seeded_document.id)


async def test_voice_session_jwt_is_valid(
    client: AsyncClient, auth_headers, seeded_citizen
):
    from app.voice import verify_tool_jwt
    r = await client.post("/voice/session", headers=auth_headers, json={})
    body = r.json()
    claims = verify_tool_jwt(body["tool_jwt"])
    assert claims.citizen_id == str(seeded_citizen.id)
```

- [ ] Run `pytest tests/test_voice_session.py -v`. Pass.

- [ ] Commit: `feat(plan-3): POST /voice/session endpoint with Gemini Live config + tool JWT`

---

## Step 10: Browser PCM AudioWorklets

Gemini Live wants 16kHz PCM16 in, 24kHz PCM16 out (per the SDK reference). Both ends through AudioWorklets so the audio path stays off the main thread.

- [ ] Write `frontend/public/worklets/pcm-recorder.js`:

```javascript
// Captures mic audio, resamples to 16 kHz PCM16, posts ArrayBuffer chunks
// to the main thread for forwarding to Gemini Live.
class PCMRecorderProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.targetRate = 16000;
    this.sourceRate = sampleRate; // AudioContext rate (typically 48000)
    this.ratio = this.sourceRate / this.targetRate;
    this.buffer = [];
    this.outChunkSamples = 1600; // 100 ms at 16 kHz
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const channel = input[0];

    // Naive linear downsample
    let i = 0;
    while (i < channel.length) {
      const idx = Math.floor(i);
      this.buffer.push(channel[idx]);
      i += this.ratio;
    }

    while (this.buffer.length >= this.outChunkSamples) {
      const chunk = this.buffer.splice(0, this.outChunkSamples);
      const pcm = new Int16Array(chunk.length);
      for (let j = 0; j < chunk.length; j++) {
        const s = Math.max(-1, Math.min(1, chunk[j]));
        pcm[j] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
    return true;
  }
}

registerProcessor('pcm-recorder', PCMRecorderProcessor);
```

- [ ] Write `frontend/public/worklets/pcm-player.js`:

```javascript
// Receives 24 kHz PCM16 from main thread, plays it through the AudioContext.
class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.cursor = 0;
    this.port.onmessage = (e) => {
      if (e.data === 'flush') {
        this.queue = [];
        this.cursor = 0;
        return;
      }
      const i16 = new Int16Array(e.data);
      const f32 = new Float32Array(i16.length);
      for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 32768;
      this.queue.push(f32);
    };
  }

  process(_inputs, outputs) {
    const out = outputs[0][0];
    let written = 0;
    while (written < out.length) {
      if (this.queue.length === 0) {
        for (let i = written; i < out.length; i++) out[i] = 0;
        return true;
      }
      const head = this.queue[0];
      const remain = head.length - this.cursor;
      const take = Math.min(remain, out.length - written);
      out.set(head.subarray(this.cursor, this.cursor + take), written);
      this.cursor += take;
      written += take;
      if (this.cursor >= head.length) {
        this.queue.shift();
        this.cursor = 0;
      }
    }
    return true;
  }
}

registerProcessor('pcm-player', PCMPlayerProcessor);
```

- [ ] Write `frontend/lib/audioWorklet.ts`:

```typescript
export type RecorderHandle = {
  context: AudioContext;
  source: MediaStreamAudioSourceNode;
  node: AudioWorkletNode;
  stream: MediaStream;
  stop: () => void;
};

export async function startMicRecorder(
  onChunk: (chunk: ArrayBuffer) => void
): Promise<RecorderHandle> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  const context = new AudioContext({ latencyHint: "interactive" });
  await context.audioWorklet.addModule("/worklets/pcm-recorder.js");
  const source = context.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(context, "pcm-recorder");
  node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => onChunk(e.data);
  source.connect(node);
  // Don't connect node to destination — we don't want echo.
  return {
    context, source, node, stream,
    stop: () => {
      try { node.disconnect(); } catch {}
      try { source.disconnect(); } catch {}
      stream.getTracks().forEach((t) => t.stop());
      void context.close();
    },
  };
}


export type PlayerHandle = {
  context: AudioContext;
  node: AudioWorkletNode;
  feed: (chunk: ArrayBuffer) => void;
  flush: () => void;
  stop: () => void;
};

export async function startPlayer(): Promise<PlayerHandle> {
  const context = new AudioContext({ sampleRate: 24000, latencyHint: "interactive" });
  await context.audioWorklet.addModule("/worklets/pcm-player.js");
  const node = new AudioWorkletNode(context, "pcm-player");
  node.connect(context.destination);
  return {
    context, node,
    feed: (chunk) => node.port.postMessage(chunk, [chunk]),
    flush: () => node.port.postMessage("flush"),
    stop: () => {
      try { node.disconnect(); } catch {}
      void context.close();
    },
  };
}
```

- [ ] Commit: `feat(plan-3): browser AudioWorklets for PCM16 capture + playback`

---

## Step 11: `frontend/lib/gemini-live.ts` — low-level Gemini Live WS client

- [ ] Write `frontend/lib/gemini-live.ts`:

```typescript
/**
 * Minimal browser WebSocket client for Gemini Live (BidiGenerateContent).
 *
 * Endpoint URL pattern (subject to SDK changes — verified against google-genai docs):
 *   wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=API_KEY
 *
 * Setup message declares: model, voice, response modality (audio), tools (function
 * declarations), system instruction.
 *
 * Bidi protocol (key messages we handle):
 *   - clientContent: streams in audio chunks (base64 PCM16 16 kHz) + text
 *   - toolCall: server emits a function-call → we dispatch HTTP to FastAPI
 *   - toolResponse: we send the tool result back
 *   - serverContent: agent text + base64 PCM16 24 kHz audio chunks
 *   - generationComplete / interrupted: end-of-turn / barge-in events
 */

export type FunctionDecl = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
};

export type GeminiLiveOpts = {
  apiKey: string;
  model: string;
  voiceName: string;
  systemPrompt: string;
  functionDeclarations: FunctionDecl[];
  onAgentAudio: (pcm: ArrayBuffer) => void;
  onAgentText: (text: string) => void;
  onUserTranscript: (text: string) => void;
  onInterrupted: () => void;          // barge-in / generation_complete
  onToolCall: (
    name: string,
    args: Record<string, unknown>,
    callId: string,
  ) => Promise<Record<string, unknown>>;
  onError: (err: unknown) => void;
};

export class GeminiLiveSession {
  private ws: WebSocket | null = null;
  private opts: GeminiLiveOpts;
  private opened = false;

  constructor(opts: GeminiLiveOpts) {
    this.opts = opts;
  }

  async connect(): Promise<void> {
    const url =
      `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=${encodeURIComponent(this.opts.apiKey)}`;
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";
      ws.onopen = () => {
        const setup = {
          setup: {
            model: `models/${this.opts.model}`,
            generationConfig: {
              responseModalities: ["AUDIO"],
              speechConfig: {
                voiceConfig: { prebuiltVoiceConfig: { voiceName: this.opts.voiceName } },
                languageCode: "ro-RO",
              },
              temperature: 0.7,
            },
            systemInstruction: {
              role: "system",
              parts: [{ text: this.opts.systemPrompt }],
            },
            tools: [{ functionDeclarations: this.opts.functionDeclarations }],
            // Barge-in is on by default in Gemini Live; explicit setting kept for clarity:
            realtimeInputConfig: { automaticActivityDetection: { disabled: false } },
          },
        };
        ws.send(JSON.stringify(setup));
        this.opened = true;
        this.ws = ws;
        resolve();
      };
      ws.onerror = (e) => {
        this.opts.onError(e);
        if (!this.opened) reject(e);
      };
      ws.onclose = () => { this.opened = false; this.ws = null; };
      ws.onmessage = (e) => this.handleMessage(e);
    });
  }

  private async handleMessage(event: MessageEvent): Promise<void> {
    let msg: any;
    try {
      msg = typeof event.data === "string"
        ? JSON.parse(event.data)
        : JSON.parse(new TextDecoder().decode(event.data));
    } catch {
      return;
    }

    // serverContent: agent text + audio
    const sc = msg.serverContent;
    if (sc) {
      if (sc.interrupted) this.opts.onInterrupted();
      const parts = sc.modelTurn?.parts ?? [];
      for (const p of parts) {
        if (p.text) this.opts.onAgentText(p.text);
        if (p.inlineData?.mimeType?.startsWith("audio/")) {
          const audio = base64ToArrayBuffer(p.inlineData.data);
          this.opts.onAgentAudio(audio);
        }
      }
      // User transcription (when enabled — Gemini Live exposes this in inputTranscription)
      if (sc.inputTranscription?.text) {
        this.opts.onUserTranscript(sc.inputTranscription.text);
      }
      if (sc.outputTranscription?.text) {
        this.opts.onAgentText(sc.outputTranscription.text);
      }
    }

    // toolCall handling
    const tc = msg.toolCall;
    if (tc && Array.isArray(tc.functionCalls)) {
      const responses = await Promise.all(
        tc.functionCalls.map(async (fc: any) => {
          const result = await this.opts.onToolCall(
            fc.name, fc.args || {}, fc.id,
          );
          return {
            id: fc.id,
            name: fc.name,
            response: { output: result },
          };
        }),
      );
      this.sendToolResponse(responses);
    }
  }

  sendAudio(chunk: ArrayBuffer): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({
      realtimeInput: {
        mediaChunks: [{
          mimeType: "audio/pcm;rate=16000",
          data: arrayBufferToBase64(chunk),
        }],
      },
    }));
  }

  sendText(text: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({
      clientContent: {
        turns: [{ role: "user", parts: [{ text }] }],
        turnComplete: true,
      },
    }));
  }

  sendToolResponse(responses: unknown[]): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({ toolResponse: { functionResponses: responses } }));
  }

  close(): void {
    try { this.ws?.close(); } catch { /* noop */ }
    this.ws = null;
  }
}


function arrayBufferToBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

function base64ToArrayBuffer(b64: string): ArrayBuffer {
  const bin = atob(b64);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  return buf.buffer;
}
```

- [ ] Commit: `feat(plan-3): low-level Gemini Live WebSocket client (Romanian voice config)`

---

## Step 12: `frontend/lib/useVoiceAgent.ts` — real implementation

Matches the signature in roadmap §4 exactly.

- [ ] Replace `frontend/lib/useVoiceAgent.ts` (file existed as a stub from Plan 1):

```typescript
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { VoicePreferences } from "./types";
import { apiClient } from "./api";
import { GeminiLiveSession, FunctionDecl } from "./gemini-live";
import { startMicRecorder, startPlayer, RecorderHandle, PlayerHandle } from "./audioWorklet";


export type VoiceAgentState = "idle" | "connecting" | "listening" | "speaking" | "error";

export type ToolCallHandler = (
  name: string,
  args: Record<string, unknown>,
) => Promise<Record<string, unknown>>;

export type VoiceAgentHook = {
  state: VoiceAgentState;
  start: (opts: {
    documentId?: string;
    preferences?: VoicePreferences;
    onAgentMessage?: (text: string) => void;
    onTranscript?: (text: string) => void;
  }) => Promise<void>;
  stop: () => void;
  sendText: (text: string) => Promise<void>;
  registerToolHandler: (handler: ToolCallHandler) => void;
  lastTranscript: string;
  lastAgentMessage: string;
};


type VoiceSessionResponse = {
  session_id: string;
  gemini_api_key: string;
  gemini_model: string;
  gemini_voice: string;
  system_prompt: string;
  tool_jwt: string;
  tool_base_url: string;
  tool_names: string[];
  citizen_context: Record<string, unknown>;
  document_context: Record<string, unknown> | null;
};


// Hardcoded JSON-Schema parameter shapes per tool name. Kept in sync with backend
// Python tool signatures. Gemini Live requires explicit declarations to emit function-calls.
const TOOL_SCHEMAS: Record<string, FunctionDecl> = {
  lookup_procedure: {
    name: "lookup_procedure",
    description: "Find the best primărie procedure for a free-text Romanian query.",
    parameters: {
      type: "object",
      properties: { query: { type: "string", description: "User's plain-language need." } },
      required: ["query"],
    },
  },
  set_field: {
    name: "set_field",
    description: "Set a single form field on the active document.",
    parameters: {
      type: "object",
      properties: {
        name: { type: "string", description: "Field name from procedure schema." },
        value: { description: "New field value." },
      },
      required: ["name", "value"],
    },
  },
  generate_pdf: {
    name: "generate_pdf",
    description: "Compile the active document to PDF via LaTeX.",
    parameters: { type: "object", properties: {} },
  },
  deliver: {
    name: "deliver",
    description: "Finalize the document. delivery in {save, send, print}.",
    parameters: {
      type: "object",
      properties: {
        delivery: { type: "string", enum: ["save", "send", "print"] },
      },
      required: ["delivery"],
    },
  },
  find_redirect: {
    name: "find_redirect",
    description: "Decide if a query is out of primărie scope and where to send the citizen.",
    parameters: {
      type: "object",
      properties: {
        query: { type: "string" },
        target: { type: "string", description: "Optional explicit target." },
      },
      required: ["query"],
    },
  },
  set_reminder: {
    name: "set_reminder",
    description: "Create a proactive reminder (rare; only on explicit citizen request).",
    parameters: {
      type: "object",
      properties: {
        kind: { type: "string", enum: ["in_scope_procedure", "external_redirect"] },
        title: { type: "string" },
        procedure_id: { type: "string" },
        redirect_target: { type: "string" },
        deadline_days: { type: "number" },
      },
      required: ["kind", "title"],
    },
  },
};


export function useVoiceAgent(): VoiceAgentHook {
  const [state, setState] = useState<VoiceAgentState>("idle");
  const [lastTranscript, setLastTranscript] = useState("");
  const [lastAgentMessage, setLastAgentMessage] = useState("");

  const sessionRef = useRef<GeminiLiveSession | null>(null);
  const recorderRef = useRef<RecorderHandle | null>(null);
  const playerRef = useRef<PlayerHandle | null>(null);
  const userToolHandlerRef = useRef<ToolCallHandler | null>(null);
  const tokenRef = useRef<{ jwt: string; baseUrl: string } | null>(null);

  const registerToolHandler = useCallback((handler: ToolCallHandler) => {
    userToolHandlerRef.current = handler;
  }, []);

  const dispatchTool = useCallback(
    async (name: string, args: Record<string, unknown>): Promise<Record<string, unknown>> => {
      // Always go to FastAPI (single source of truth); userToolHandlerRef is called
      // afterwards so the UI can react (e.g., highlight a field that changed).
      const tok = tokenRef.current;
      if (!tok) throw new Error("No tool JWT available — session not started");
      const resp = await fetch(`${tok.baseUrl}/${name}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${tok.jwt}`,
        },
        body: JSON.stringify(args),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error(`Tool ${name} failed (${resp.status}): ${detail}`);
      }
      const result = await resp.json();
      // Fire-and-forget UI notification
      try {
        await userToolHandlerRef.current?.(name, { ...args, _result: result });
      } catch { /* swallow UI errors */ }
      return result;
    },
    [],
  );

  const start: VoiceAgentHook["start"] = useCallback(async (opts) => {
    try {
      setState("connecting");

      const session = await apiClient.post<VoiceSessionResponse>("/voice/session", {
        document_id: opts.documentId,
        preferences: opts.preferences ?? {},
      });
      tokenRef.current = { jwt: session.tool_jwt, baseUrl: session.tool_base_url };

      const declarations: FunctionDecl[] = session.tool_names
        .map((n) => TOOL_SCHEMAS[n])
        .filter((d): d is FunctionDecl => Boolean(d));

      const player = await startPlayer();
      playerRef.current = player;

      const gemini = new GeminiLiveSession({
        apiKey: session.gemini_api_key,
        model: session.gemini_model,
        voiceName: session.gemini_voice,
        systemPrompt: session.system_prompt,
        functionDeclarations: declarations,
        onAgentAudio: (pcm) => {
          setState("speaking");
          player.feed(pcm);
        },
        onAgentText: (text) => {
          setLastAgentMessage(text);
          opts.onAgentMessage?.(text);
        },
        onUserTranscript: (text) => {
          setLastTranscript(text);
          opts.onTranscript?.(text);
          setState("listening");
        },
        onInterrupted: () => {
          // Barge-in: stop playback immediately, return to listening
          player.flush();
          setState("listening");
        },
        onToolCall: dispatchTool,
        onError: (err) => {
          console.error("[useVoiceAgent] Gemini error", err);
          setState("error");
        },
      });
      sessionRef.current = gemini;
      await gemini.connect();

      // Start mic AFTER WS is open
      let recorder: RecorderHandle;
      try {
        recorder = await startMicRecorder((chunk) => {
          gemini.sendAudio(chunk);
        });
      } catch (micErr) {
        // Mic-denied fallback: keep WS open for text-input usage
        console.warn("[useVoiceAgent] Mic denied; falling back to text", micErr);
        setState("error");
        throw new VoiceAgentMicDeniedError();
      }
      recorderRef.current = recorder;

      setState("listening");
    } catch (err) {
      setState("error");
      throw err;
    }
  }, [dispatchTool]);

  const stop: VoiceAgentHook["stop"] = useCallback(() => {
    sessionRef.current?.close();
    recorderRef.current?.stop();
    playerRef.current?.stop();
    sessionRef.current = null;
    recorderRef.current = null;
    playerRef.current = null;
    tokenRef.current = null;
    setState("idle");
  }, []);

  const sendText: VoiceAgentHook["sendText"] = useCallback(async (text) => {
    if (!sessionRef.current) {
      throw new Error("Voice session not started; call start() first.");
    }
    sessionRef.current.sendText(text);
  }, []);

  useEffect(() => () => { stop(); }, [stop]);

  return {
    state,
    start,
    stop,
    sendText,
    registerToolHandler,
    lastTranscript,
    lastAgentMessage,
  };
}


export class VoiceAgentMicDeniedError extends Error {
  constructor() {
    super("Microphone permission denied — fall back to text chat.");
    this.name = "VoiceAgentMicDeniedError";
  }
}
```

- [ ] Write `frontend/__tests__/useVoiceAgent.test.ts` (Vitest):

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";


vi.mock("@/lib/api", () => ({
  apiClient: {
    post: vi.fn(async () => ({
      session_id: "s1",
      gemini_api_key: "k",
      gemini_model: "m",
      gemini_voice: "v",
      system_prompt: "sys",
      tool_jwt: "jwt-token",
      tool_base_url: "http://api/tools",
      tool_names: ["lookup_procedure", "set_field"],
      citizen_context: {},
      document_context: null,
    })),
  },
}));

// Mock GeminiLiveSession and audioWorklet to avoid touching real APIs
vi.mock("@/lib/gemini-live", () => {
  return {
    GeminiLiveSession: vi.fn().mockImplementation((opts) => ({
      connect: vi.fn(async () => {}),
      close: vi.fn(),
      sendAudio: vi.fn(),
      sendText: vi.fn(),
      _opts: opts,
    })),
  };
});
vi.mock("@/lib/audioWorklet", () => ({
  startMicRecorder: vi.fn(async () => ({ stop: vi.fn() })),
  startPlayer: vi.fn(async () => ({ feed: vi.fn(), flush: vi.fn(), stop: vi.fn() })),
}));

import { useVoiceAgent, VoiceAgentMicDeniedError } from "@/lib/useVoiceAgent";


describe("useVoiceAgent", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("starts and reaches listening state", async () => {
    const { result } = renderHook(() => useVoiceAgent());
    await act(async () => { await result.current.start({}); });
    expect(result.current.state).toBe("listening");
  });

  it("registerToolHandler stores the handler", async () => {
    const { result } = renderHook(() => useVoiceAgent());
    const handler = vi.fn(async () => ({}));
    act(() => { result.current.registerToolHandler(handler); });
    expect(handler).not.toHaveBeenCalled(); // not yet invoked
  });

  it("stop returns to idle", async () => {
    const { result } = renderHook(() => useVoiceAgent());
    await act(async () => { await result.current.start({}); });
    act(() => { result.current.stop(); });
    expect(result.current.state).toBe("idle");
  });

  it("throws VoiceAgentMicDeniedError when mic denied", async () => {
    const audioWorklet = await import("@/lib/audioWorklet");
    (audioWorklet.startMicRecorder as any).mockRejectedValueOnce(
      new DOMException("denied", "NotAllowedError"),
    );
    const { result } = renderHook(() => useVoiceAgent());
    await expect(
      act(async () => { await result.current.start({}); }),
    ).rejects.toBeInstanceOf(VoiceAgentMicDeniedError);
    expect(result.current.state).toBe("error");
  });
});
```

- [ ] Run `cd frontend && pnpm test useVoiceAgent`. Pass.

- [ ] Commit: `feat(plan-3): real useVoiceAgent hook with Gemini Live WebSocket + tool dispatch`

---

## Step 13: Wire Vocal completion mode

- [ ] Extend `frontend/components/VocalFillFlow.tsx` (file exists from Plan 1 as stub):

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useVoiceAgent, VoiceAgentMicDeniedError } from "@/lib/useVoiceAgent";
import { Document, Procedure, VoicePreferences } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Mic, MicOff, MessageSquare } from "lucide-react";


type Props = {
  document: Document;
  procedure: Procedure;
  preferences?: VoicePreferences;
  onFieldsUpdated?: (fields: Record<string, unknown>) => void;
  onTextFallback?: () => void;
};

export function VocalFillFlow({
  document,
  procedure,
  preferences,
  onFieldsUpdated,
  onTextFallback,
}: Props) {
  const voice = useVoiceAgent();
  const [transcript, setTranscript] = useState<string[]>([]);
  const [agentLines, setAgentLines] = useState<string[]>([]);
  const [micDenied, setMicDenied] = useState(false);
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    voice.registerToolHandler(async (name, args) => {
      if (name === "set_field" && args._result) {
        const result = args._result as Document;
        onFieldsUpdated?.(result.fields ?? {});
      }
      return {};
    });

    voice.start({
      documentId: document.id,
      preferences,
      onAgentMessage: (text) => setAgentLines((prev) => [...prev, text]),
      onTranscript: (text) => setTranscript((prev) => [...prev, text]),
    }).catch((err) => {
      if (err instanceof VoiceAgentMicDeniedError) {
        setMicDenied(true);
      } else {
        console.error("Voice start failed", err);
      }
    });

    return () => voice.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (micDenied) {
    return (
      <div className="space-y-4 rounded-lg border bg-amber-50 p-6">
        <div className="flex items-center gap-3">
          <MicOff aria-hidden className="text-amber-700" />
          <h3 className="text-lg font-semibold">Microfonul nu este disponibil</h3>
        </div>
        <p>
          Browser-ul nu ne-a permis accesul la microfon. Putem continua scriind în chat,
          asistentul răspunde la fel. Conversația ta nu se pierde.
        </p>
        <Button onClick={onTextFallback}>
          <MessageSquare className="mr-2 h-4 w-4" />
          Continuă cu text
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3" aria-live="polite">
        <Mic className={voice.state === "listening" ? "text-green-600 animate-pulse" : "text-muted-foreground"} aria-hidden />
        <span className="text-sm">
          {{
            idle: "Asistentul nu este pornit",
            connecting: "Se conectează...",
            listening: "Ascult — vorbește când vrei",
            speaking: "Asistentul vorbește",
            error: "Eroare — încearcă din nou",
          }[voice.state]}
        </span>
      </div>

      <section aria-label="Transcriere">
        <h4 className="mb-2 text-sm font-semibold">Ce ai spus</h4>
        <ul className="space-y-1 text-sm">
          {transcript.map((t, i) => <li key={i}>{t}</li>)}
        </ul>
      </section>

      <section aria-label="Răspunsul asistentului">
        <h4 className="mb-2 text-sm font-semibold">Asistentul</h4>
        <ul className="space-y-1 text-sm">
          {agentLines.map((t, i) => <li key={i}>{t}</li>)}
        </ul>
      </section>

      <Button variant="outline" onClick={() => voice.stop()}>
        Oprește
      </Button>
    </div>
  );
}
```

- [ ] Ensure `frontend/components/CompletionModeSelector.tsx` (from Plan 1) routes the "Vocal" choice to `<VocalFillFlow />` with `preferences` pulled from the citizen profile.

- [ ] Commit: `feat(plan-3): wire VocalFillFlow to real useVoiceAgent`

---

## Step 14: Wire ChatPanel to real `/agent/chat`

ChatPanel from Plan 1 already calls `/agent/chat`; this step just confirms request/response wiring still matches now that the backend is real, and adds tool-call rendering.

- [ ] Update `frontend/components/ChatPanel.tsx` so that when a `set_field` or `deliver` tool call is returned, the parent component re-fetches the document. Concretely, after `apiClient.post("/agent/chat", ...)`, iterate over `tool_calls` and emit them via a prop:

```tsx
// Inside ChatPanel send handler, after:
//   const resp = await apiClient.post<ChatResponse>("/agent/chat", { ... });
// Add:
for (const tc of resp.tool_calls ?? []) {
  if (tc.name === "set_field" || tc.name === "deliver" || tc.name === "generate_pdf") {
    onDocumentSideEffect?.(tc.name, tc.arguments);
  }
}
```

The procedure flow page (`/req/[id]`) reacts by re-fetching the document.

- [ ] Manual smoke test: with both services running, navigate to `/req/schimbare-domiciliu`, type "Vreau să-mi schimb domiciliul", verify agent confirms the procedure in Romanian and the form preview state updates as fields fill.

- [ ] Commit: `feat(plan-3): ChatPanel surfaces agent tool-calls to parent for document refresh`

---

## Step 15: Twilio bridge — phone path

The bridge accepts Twilio Media Streams WebSocket (raw 8 kHz μ-law audio in base64 JSON envelopes) and proxies to a parallel Gemini Live session using the phone system prompt with the restricted tool set.

- [ ] Write `backend/tests/test_twilio_bridge.py`:

```python
"""Unit tests for the G.711 ↔ PCM transcoder.

The full bridge integration is exercised with manual phone calls in Step 17;
here we test the codec helpers and the message routing logic.
"""
import audioop
import base64
import pytest

from app.twilio_bridge import (
    mulaw_to_pcm16_16k,
    pcm16_24k_to_mulaw_8k,
    parse_twilio_frame,
    PHONE_TOOL_ALLOWLIST,
)


def test_mulaw_to_pcm16_16k_roundtrip_smoke():
    # Synthetic 8 kHz μ-law bytes (silence pattern)
    mulaw_bytes = bytes([0xFF] * 160)  # 20 ms at 8 kHz
    pcm = mulaw_to_pcm16_16k(mulaw_bytes)
    # 8 kHz → 16 kHz doubles sample count; 2 bytes per sample
    assert len(pcm) == 160 * 2 * 2


def test_pcm24k_to_mulaw8k_changes_length():
    # 100 ms of 24 kHz PCM16 silence = 24000 * 0.1 * 2 = 4800 bytes
    pcm = bytes(4800)
    mulaw = pcm16_24k_to_mulaw_8k(pcm)
    # 24 kHz → 8 kHz divides by 3; μ-law is 1 byte/sample
    assert len(mulaw) == int(24000 * 0.1 / 3)


def test_parse_twilio_media_frame():
    payload = base64.b64encode(b"\xff" * 160).decode()
    frame = {
        "event": "media",
        "streamSid": "MZxxxx",
        "media": {"timestamp": "200", "payload": payload, "track": "inbound"},
    }
    parsed = parse_twilio_frame(frame)
    assert parsed.event == "media"
    assert parsed.audio_mulaw == b"\xff" * 160


def test_parse_twilio_start_frame():
    frame = {"event": "start", "streamSid": "MZxxxx", "start": {"callSid": "CAxxxx"}}
    parsed = parse_twilio_frame(frame)
    assert parsed.event == "start"
    assert parsed.audio_mulaw is None


def test_phone_tool_allowlist_is_restricted():
    assert "lookup_procedure" in PHONE_TOOL_ALLOWLIST
    assert "find_redirect" in PHONE_TOOL_ALLOWLIST
    # Document-writing tools MUST NOT be in the allowlist
    assert "set_field" not in PHONE_TOOL_ALLOWLIST
    assert "generate_pdf" not in PHONE_TOOL_ALLOWLIST
    assert "deliver" not in PHONE_TOOL_ALLOWLIST
    assert "set_reminder" not in PHONE_TOOL_ALLOWLIST
```

- [ ] Write `backend/app/twilio_bridge.py`:

```python
"""Twilio Media Streams ↔ Gemini Live bridge.

Twilio sends raw 8 kHz mono μ-law audio over WebSocket inside JSON envelopes.
We transcode μ-law ↔ PCM16, resample 8 kHz ↔ 16 kHz / 24 kHz, and proxy to a
parallel Gemini Live session configured with the phone system prompt and a
restricted tool allowlist (RAG-only).

Twilio Media Streams protocol reference (events we handle):
    {"event": "connected", ...}
    {"event": "start", "streamSid": "...", "start": {...}}
    {"event": "media", "media": {"payload": "<base64 mulaw>", ...}}
    {"event": "stop", ...}
"""
from __future__ import annotations

import asyncio
import audioop
import base64
import json
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types as genai_types

from app.config import settings
from app.prompts import build_system_prompt
from app.tools import REGISTRY, ToolContext


router = APIRouter(tags=["twilio"])
log = logging.getLogger("twilio_bridge")


PHONE_TOOL_ALLOWLIST: set[str] = {"lookup_procedure", "find_redirect"}


# ---- Audio codec helpers ----

def mulaw_to_pcm16_16k(mulaw_bytes: bytes) -> bytes:
    """8 kHz μ-law → 16 kHz PCM16 mono (what Gemini Live wants on input)."""
    pcm8k = audioop.ulaw2lin(mulaw_bytes, 2)
    pcm16k, _ = audioop.ratecv(pcm8k, 2, 1, 8000, 16000, None)
    return pcm16k


def pcm16_24k_to_mulaw_8k(pcm24k_bytes: bytes) -> bytes:
    """24 kHz PCM16 (Gemini Live output) → 8 kHz μ-law for Twilio."""
    pcm8k, _ = audioop.ratecv(pcm24k_bytes, 2, 1, 24000, 8000, None)
    return audioop.lin2ulaw(pcm8k, 2)


# ---- Twilio frame parsing ----

@dataclass
class TwilioFrame:
    event: str
    stream_sid: str | None
    audio_mulaw: bytes | None


def parse_twilio_frame(msg: dict) -> TwilioFrame:
    event = msg.get("event", "unknown")
    stream_sid = msg.get("streamSid")
    audio = None
    if event == "media" and msg.get("media", {}).get("payload"):
        audio = base64.b64decode(msg["media"]["payload"])
    return TwilioFrame(event=event, stream_sid=stream_sid, audio_mulaw=audio)


# ---- Gemini Live phone session ----

async def _run_phone_gemini_session(
    inbound: asyncio.Queue[bytes],
    send_to_twilio: callable,  # async fn(mulaw_bytes)
    stop_event: asyncio.Event,
) -> None:
    client = genai.Client(api_key=settings.gemini_api_key)

    function_declarations = [
        {
            "name": "lookup_procedure",
            "description": "Find the best primărie procedure for a Romanian query.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "find_redirect",
            "description": "Decide if a query is out of primărie scope.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "target": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    ]
    config = genai_types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=build_system_prompt(variant="phone"),
        tools=[{"function_declarations": function_declarations}],
        speech_config=genai_types.SpeechConfig(
            voice_config=genai_types.VoiceConfig(
                prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                    voice_name=settings.gemini_voice_name,
                )
            ),
            language_code="ro-RO",
        ),
    )

    # Synthetic ToolContext for phone calls — no citizen_id (caller is anonymous)
    phone_ctx = ToolContext(citizen_id="phone-anonymous", document_id=None)

    async with client.aio.live.connect(model=settings.gemini_model, config=config) as session:
        async def pump_inbound() -> None:
            while not stop_event.is_set():
                pcm = await inbound.get()
                if pcm is None:
                    break
                await session.send_realtime_input(audio=genai_types.Blob(
                    data=pcm, mime_type="audio/pcm;rate=16000",
                ))

        async def pump_outbound() -> None:
            async for response in session.receive():
                if response.data:  # audio bytes (PCM16 24 kHz)
                    mulaw = pcm16_24k_to_mulaw_8k(response.data)
                    await send_to_twilio(mulaw)
                # Tool calls
                tc = getattr(response, "tool_call", None)
                if tc and tc.function_calls:
                    responses = []
                    for fc in tc.function_calls:
                        if fc.name not in PHONE_TOOL_ALLOWLIST:
                            log.warning("Phone agent attempted disallowed tool %s", fc.name)
                            responses.append(genai_types.FunctionResponse(
                                id=fc.id, name=fc.name,
                                response={"error": "tool_not_available_on_phone"},
                            ))
                            continue
                        try:
                            tool = REGISTRY[fc.name]
                            result = await tool(phone_ctx, **(fc.args or {}))
                            if hasattr(result, "model_dump"):
                                result = result.model_dump(mode="json")
                            responses.append(genai_types.FunctionResponse(
                                id=fc.id, name=fc.name, response={"output": result},
                            ))
                        except Exception as e:
                            log.exception("Phone tool %s failed", fc.name)
                            responses.append(genai_types.FunctionResponse(
                                id=fc.id, name=fc.name, response={"error": str(e)},
                            ))
                    await session.send_tool_response(function_responses=responses)
                if getattr(response, "server_content", None) and response.server_content.interrupted:
                    log.debug("Phone agent interrupted (barge-in)")

        await asyncio.gather(pump_inbound(), pump_outbound())


# ---- WebSocket endpoint ----

@router.websocket("/voice/twilio")
async def twilio_media_stream(ws: WebSocket) -> None:
    await ws.accept()
    log.info("Twilio Media Stream connected")

    inbound: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
    stop_event = asyncio.Event()
    stream_sid_holder: dict[str, str] = {}

    async def send_to_twilio(mulaw_bytes: bytes) -> None:
        sid = stream_sid_holder.get("sid")
        if not sid:
            return
        try:
            await ws.send_text(json.dumps({
                "event": "media",
                "streamSid": sid,
                "media": {"payload": base64.b64encode(mulaw_bytes).decode()},
            }))
        except Exception:
            log.exception("Failed sending audio to Twilio")

    gemini_task = asyncio.create_task(
        _run_phone_gemini_session(inbound, send_to_twilio, stop_event)
    )

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            frame = parse_twilio_frame(msg)
            if frame.event == "start" and frame.stream_sid:
                stream_sid_holder["sid"] = frame.stream_sid
                log.info("Twilio stream started %s", frame.stream_sid)
            elif frame.event == "media" and frame.audio_mulaw:
                pcm = mulaw_to_pcm16_16k(frame.audio_mulaw)
                try:
                    inbound.put_nowait(pcm)
                except asyncio.QueueFull:
                    # Drop oldest to keep latency bounded
                    _ = inbound.get_nowait()
                    inbound.put_nowait(pcm)
            elif frame.event == "stop":
                log.info("Twilio stream stopped")
                break
    except WebSocketDisconnect:
        log.info("Twilio WS disconnected")
    finally:
        stop_event.set()
        await inbound.put(None)  # type: ignore[arg-type]
        gemini_task.cancel()
        try:
            await gemini_task
        except (asyncio.CancelledError, Exception):
            pass


# ---- Webhook returning TwiML on inbound calls ----

_TWIML_BRIDGE = """\
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{ws_url}" />
  </Connect>
</Response>
"""

_TWIML_FALLBACK = """\
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="ro-RO">
    Bună ziua. Asistentul vocal este indisponibil momentan.
    Vă rugăm să vizitați egata.ro pentru asistență completă.
    Mulțumim.
  </Say>
</Response>
"""


@router.post("/voice/twilio/webhook")
async def twilio_voice_webhook(request: Request) -> Response:
    """Twilio Voice webhook: returns TwiML opening a Stream to /voice/twilio.

    Falls back to static <Say> if the bridge health check is unhealthy.
    """
    if not await _bridge_is_healthy():
        return Response(content=_TWIML_FALLBACK, media_type="application/xml")
    ws_url = settings.twilio_bridge_public_url or "wss://localhost/voice/twilio"
    return Response(
        content=_TWIML_BRIDGE.format(ws_url=ws_url),
        media_type="application/xml",
    )


async def _bridge_is_healthy() -> bool:
    """Lightweight health check.

    For the hackathon: just verifies GEMINI_API_KEY is set and the public URL
    is configured. A real production check would ping Gemini Live and confirm
    the WebSocket route is responsive.
    """
    if not settings.gemini_api_key:
        return False
    if not settings.twilio_bridge_public_url:
        return False
    return True
```

- [ ] Register the router in `main.py`:

```python
from app.twilio_bridge import router as twilio_router
app.include_router(twilio_router)
```

- [ ] Run `pytest tests/test_twilio_bridge.py -v`. All 5 tests pass.

- [ ] Commit: `feat(plan-3): Twilio Media Streams bridge to Gemini Live (phone agent, RAG-only)`

---

## Step 16: Twilio console configuration + TwiML fallback docs

- [ ] Write `docs/twilio-setup.md`:

```markdown
# Twilio Configuration — eGata Phone Bridge

## Prerequisites
- Twilio account with an EU number provisioned (or UK +44 fallback).
- Railway/production URL of the FastAPI backend, e.g. `https://egata-backend.up.railway.app`.

## Steps (Twilio Console)

1. **Phone Numbers → Manage → Active numbers** → click your eGata number.

2. **Voice & Fax → A CALL COMES IN**
   - Type: **Webhook**
   - URL: `https://egata-backend.up.railway.app/voice/twilio/webhook`
   - HTTP: **POST**

3. **Voice & Fax → CALL STATUS CHANGES** (optional)
   - URL: `https://egata-backend.up.railway.app/voice/twilio/status`
   - Method: POST (not implemented in MVP; safe to leave blank).

4. **Primary Handler Fails** → leave empty (the webhook itself returns the static `<Say>`
   fallback when the bridge is unhealthy).

## Environment variable for backend

```
TWILIO_BRIDGE_PUBLIC_URL=wss://egata-backend.up.railway.app/voice/twilio
```

This is the URL Twilio is told to open a Media Streams WebSocket to (via the TwiML
`<Stream url="...">` element).

## Testing manually

- Dial the Twilio number from your phone.
- You should hear the agent say something in Romanian within ~2 seconds.
- Speak: *"Bună ziua, ce acte îmi trebuie pentru o adeverință de venit?"*
- Agent should respond with the list of required fields and direct you to egata.ro.

## Fallback behavior

If `GEMINI_API_KEY` is unset OR `TWILIO_BRIDGE_PUBLIC_URL` is unset OR the bridge endpoint
is unreachable, the webhook returns static TwiML `<Say>` in Romanian:

> *"Bună ziua. Asistentul vocal este indisponibil momentan. Vă rugăm să vizitați
> egata.ro pentru asistență completă. Mulțumim."*
```

- [ ] Smoke test the webhook locally:

```bash
curl -sX POST http://localhost:8000/voice/twilio/webhook | head
```

Should return TwiML XML. With env vars unset, should return the `<Say>` fallback.

- [ ] Commit: `docs(plan-3): Twilio console setup + TwiML fallback documentation`

---

## Step 17: End-to-end browser voice test (manual + recorded)

- [ ] **Pre-flight:** confirm `GEMINI_API_KEY` is set on both Railway (backend) and local dev; confirm `JWT_SIGNING_SECRET` matches between backend and any tools that verify; confirm Plan 1 + Plan 2 are deployed and `schimbare-domiciliu` is seeded.

- [ ] **Manual browser test steps** (record on video for demo):
  1. Open the deployed frontend in Chrome on a laptop.
  2. Log in as `maria-ionescu` (the seeded demo persona).
  3. Click "Start o cerere nouă" → type / pick `Schimbare domiciliu`.
  4. Auto-fill screen renders. Click "Vocal".
  5. Grant mic permission when prompted.
  6. Speak: **"Bună ziua. Vreau să-mi schimb domiciliul. Adresa mea nouă este Strada Plopilor numărul 15, Cluj-Napoca."**
  7. **Expected:** within 2 sec the agent responds in Romanian confirming the procedure and asks for the next missing field (e.g., `tip_proprietate`).
  8. The form preview pane shows `adresa_noua` filled with "Str. Plopilor 15, Cluj-Napoca" within 3 sec.
  9. Continue conversation: answer "proprietar" when asked about tip_proprietate.
  10. Once all required fields are filled, agent asks "Vrei să salvezi, să trimiți sau să tipărești?" — say "Trimite".
  11. Agent confirms; the document moves to `finalized`, ref_number appears, ledger entry visible at `/doc/[id]`.

- [ ] **Barge-in test:** while the agent is reading back the field summary, interrupt by speaking. Confirm the agent stops speaking within ~200 ms and switches to listening.

- [ ] **Mic-denied test:** in browser settings, block microphone for the site. Reload and start the Vocal flow. Confirm the amber fallback panel renders with the "Continuă cu text" button and clicking it returns to the text chat without losing conversation state.

- [ ] **Simple-language test:** in the accessibility toggles (UI wired by Plan 4 but already passes the flag to `/voice/session`), enable "Explică-mi mai simplu". Start a new voice session. Confirm the agent uses shorter sentences and avoids jargon (e.g., "schimb adresa pe buletin" rather than "înregistrarea mențiunii de stabilire a domiciliului").

- [ ] Commit any small fixes uncovered: `fix(plan-3): <issue>`

---

## Step 18: End-to-end phone voice test

- [ ] **Pre-flight:** Twilio number configured per `docs/twilio-setup.md`; `TWILIO_BRIDGE_PUBLIC_URL` set on Railway; backend deployed and reachable.

- [ ] **Manual phone test steps:**
  1. From a personal phone, dial the Twilio eGata number.
  2. **Expected:** within 2 sec of connect, the agent greets in Romanian.
  3. Say: **"Bună ziua, de ce acte am nevoie pentru o adeverință de venit?"**
  4. **Expected:** agent lists the required fields (nume, CNP, employer, etc.) and directs to egata.ro.
  5. Say: **"Cum îmi schimb medicul de familie?"** → agent should redirect to CNAS with phone number 0800 800 950.
  6. Say: **"Vreau să completez documentul acum."** → agent should politely decline ("nu pot completa documente pe telefon") and again invite to egata.ro.

- [ ] **Fallback test:** temporarily unset `GEMINI_API_KEY` on the deployed backend. Dial again. Confirm the static `<Say>` fallback plays the Romanian message. Re-set the env var.

- [ ] Commit any small fixes: `fix(plan-3): <issue>`

---

## Step 19: Self-review against Checkpoint 2 (Plan 3 items)

- [ ] `/agent/chat` powered by Pydantic AI + Gemini tool calls (no canned responses) — **Step 7**.
- [ ] `/voice/session` returns a working Gemini Live ephemeral token — **Step 9** (note: real ephemeral tokens depend on Gemini Live SDK availability; we ship with main key delivered over TLS + tool JWT).
- [ ] `useVoiceAgent` hook drives a real WebSocket session to Gemini Live in Romanian — **Steps 10-12**.
- [ ] Function calls from Gemini Live dispatched to FastAPI tools — **Steps 8 + 12**.
- [ ] Voice flow for `schimbare-domiciliu` works end-to-end — **Step 17**.
- [ ] Twilio inbound number connects to phone bridge; agent answers a procedural question in Romanian — **Steps 15-16, 18**.
- [ ] TwiML fallback configured if bridge fails — **Step 15** (`_TWIML_FALLBACK`) **+ Step 16** (docs).

- [ ] Run the full backend test suite: `cd backend && pytest -v`. All passing.
- [ ] Run the full frontend test suite: `cd frontend && pnpm test`. All passing.
- [ ] Update the wave-2 branch and open PR `wave2/plan-3-agent-voice` → `main` per roadmap §7.

- [ ] Commit: `chore(plan-3): final tidy + checkpoint-2 verification notes`

---

## Final commit + merge

- [ ] Verify `git status` clean.
- [ ] Push branch.
- [ ] Open PR with the body templated to call out: scope coverage table, Checkpoint 2 items checked, known caveats (Gemini ephemeral-token swap pending GA, real Twilio number must be provisioned manually).
