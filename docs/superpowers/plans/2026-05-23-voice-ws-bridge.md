# Voice WS Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Gemini Live voice from a browser-direct WebSocket (with leaked API key) to a backend bridge with unified conversation history, in-process tool dispatch, and live-transcribed messages straight from Gemini's `input_audio_transcription` / `output_audio_transcription`.

**Architecture:** New backend WS endpoint `/agent/voice/ws` holds a `client.aio.live.connect()` session and shares the existing `_conversations[conv_id]` with the text agent. Frontend gets a new `voiceWs.ts` client + `useVoiceAgentBridge.ts` hook (drop-in replacement for `useVoiceAgent`). Old direct-WS path stays alive behind `NEXT_PUBLIC_VOICE_BRIDGE` env flag for rollback.

**Tech Stack:** FastAPI WebSocket, `google-genai` ≥1.10 (upgrade required for transcription), Next.js, Zustand, AudioWorklet PCM16/24.

**Spec:** `docs/superpowers/specs/2026-05-23-voice-ws-bridge-design.md`

**Reference:** `backend/app/twilio_bridge.py` (existing working Gemini Live bridge — same pattern).

---

## File Structure

### New files

- `backend/app/agent_voice.py` — bridge module: WS endpoint, `VoiceBridgeSession` class, tool dispatch.
- `frontend/lib/voiceWs.ts` — typed WebSocket client (~150 lines).
- `frontend/lib/useVoiceAgentBridge.ts` — React hook with identical surface to `useVoiceAgent`.

### Modified files

- `backend/pyproject.toml` — bump `google-genai` minimum to a transcription-supporting version.
- `backend/app/main.py` — register the new WS router.
- `backend/app/agent.py` — export `_conversations` and `_remember` (already module-level but used cross-module now).
- `frontend/lib/sessionStore.ts` — add live-message actions + `live?: boolean` on `Message`.
- `frontend/lib/types.ts` — add `live?: boolean` field on `Message` type.
- `frontend/components/chat/ChatStream.tsx` — render live messages with a subtle indicator.
- `frontend/components/chat/ChatSurface.tsx` — env-gated hook switch.
- `frontend/.env.example` (if exists) or `frontend/.env.local` — document the new env var.

### Untouched (deliberately — these are the fallback)

- `backend/app/voice.py` — keep `/voice/session` endpoint + JWT helpers.
- `frontend/lib/gemini-live.ts` — keep direct-WS client.
- `frontend/lib/useVoiceAgent.ts` — keep direct hook.
- `backend/app/twilio_bridge.py` — phone bridge, unaffected.

---

## Task 0: Upgrade google-genai for transcription support

The Python SDK at 1.2.0 doesn't expose `input_audio_transcription` / `output_audio_transcription` on `LiveConnectConfig`. Both fields are required for the live-message UX. Upgrade to 1.10+ (transcription is stable from that range onward) while staying below 2.0 to avoid the major-version bump that breaks `pyproject.toml`'s upper bound.

**Files:**
- Modify: `backend/pyproject.toml` (the `google-genai` line)

- [ ] **Step 1: Bump version constraint**

In `backend/pyproject.toml`, change:
```
  "google-genai>=0.3.0,<2.0",
```
to:
```
  "google-genai>=1.10.0,<2.0",
```

- [ ] **Step 2: Install the new version**

Run from `backend/`:
```bash
pip install -e .
```
Expected: a recent 1.x install (e.g. 1.75.0).

- [ ] **Step 3: Verify transcription fields are now available**

```bash
python -c "from google.genai import types as t; m = t.LiveConnectConfig.model_fields; print('input_audio_transcription' in m, 'output_audio_transcription' in m)"
```
Expected: `True True`. If False on either, bump higher (try `>=1.30.0`) and reinstall.

- [ ] **Step 4: Verify existing twilio bridge still imports**

```bash
python -c "from app.twilio_bridge import _run_phone_gemini_session, router; print('ok')"
```
Expected: `ok`. If the SDK upgrade renamed any type used in `twilio_bridge.py`, patch the import. Most likely candidates: `genai_types.Blob`, `genai_types.LiveConnectConfig`, `genai_types.SpeechConfig`, `genai_types.VoiceConfig`, `genai_types.PrebuiltVoiceConfig`, `genai_types.FunctionResponse` — these have been stable across 1.x.

- [ ] **Step 5: Verify text agent still imports**

```bash
python -c "from app.agent import _conversations, _stream_agent_turn; print('ok')"
```
Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml
git commit -m "deps: bump google-genai to >=1.10 for Live transcription support"
```

---

## Task 1: Backend bridge skeleton — connect to Gemini Live, echo audio

Stand up `agent_voice.py` with a WS endpoint that accepts mic audio and proxies it to Gemini Live, returning agent audio back. No transcripts, no tools yet — just verify the round-trip works.

**Files:**
- Create: `backend/app/agent_voice.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: Create the bridge module**

`backend/app/agent_voice.py`:
```python
"""Browser ↔ Gemini Live WebSocket bridge.

Patterned after backend/app/twilio_bridge.py. The browser sends PCM16
mono 16 kHz audio over a WebSocket; the backend forwards to Gemini Live
via the Python SDK, relays agent audio back, surfaces live transcripts
as JSON control frames, and dispatches tool-calls in-process against
app.tools.REGISTRY.

JSON control frames (see docs/superpowers/specs/2026-05-23-voice-ws-bridge-design.md §5).
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from google import genai
from google.genai import types as genai_types

from app.config import get_settings
from app.prompts import build_system_prompt
from app.security import current_citizen_id_from_cookies
from app.tools import REGISTRY, ToolContext

router = APIRouter(prefix="/agent", tags=["voice"])
log = logging.getLogger("agent_voice")


@dataclass
class VoiceStartPayload:
    document_id: str | None = None
    conversation_id: str | None = None
    simple_language: bool = False
    voice_only: bool = False


@dataclass
class VoiceBridgeSession:
    ws: WebSocket
    citizen_id: str
    inbound_audio: asyncio.Queue[bytes | None] = field(
        default_factory=lambda: asyncio.Queue(maxsize=200)
    )
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    conv_id: str = ""
    start_payload: VoiceStartPayload | None = None

    async def send_json(self, obj: dict[str, Any]) -> None:
        try:
            await self.ws.send_text(json.dumps(obj, ensure_ascii=False))
        except Exception:
            log.exception("ws.send_text failed")

    async def send_bytes(self, data: bytes) -> None:
        try:
            await self.ws.send_bytes(data)
        except Exception:
            log.exception("ws.send_bytes failed")

    async def wait_for_start(self) -> VoiceStartPayload:
        # First frame from client must be JSON `start`.
        msg = await self.ws.receive()
        if msg.get("type") != "websocket.receive":
            raise RuntimeError(f"Expected receive, got {msg}")
        text = msg.get("text")
        if not text:
            raise RuntimeError("Expected JSON start frame, got binary")
        payload = json.loads(text)
        if payload.get("type") != "start":
            raise RuntimeError(f"Expected start frame, got {payload.get('type')}")
        prefs = payload.get("preferences") or {}
        return VoiceStartPayload(
            document_id=payload.get("document_id"),
            conversation_id=payload.get("conversation_id"),
            simple_language=bool(prefs.get("simple_language")),
            voice_only=bool(prefs.get("voice_only")),
        )

    async def run(self) -> None:
        self.start_payload = await self.wait_for_start()
        self.conv_id = (
            self.start_payload.conversation_id
            or f"conv_{secrets.token_urlsafe(8)}"
        )

        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)

        system_prompt = build_system_prompt(
            variant="conversational",
            simple_language=self.start_payload.simple_language,
            voice_only=self.start_payload.voice_only,
        )

        config = genai_types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=genai_types.Content(
                role="system",
                parts=[genai_types.Part.from_text(text=system_prompt)],
            ),
            speech_config=genai_types.SpeechConfig(
                voice_config=genai_types.VoiceConfig(
                    prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                        voice_name=settings.gemini_voice_name,
                    )
                ),
                language_code="ro-RO",
            ),
            # Transcription fields added in google-genai >=1.10
            input_audio_transcription=genai_types.AudioTranscriptionConfig(),
            output_audio_transcription=genai_types.AudioTranscriptionConfig(),
        )

        async with client.aio.live.connect(
            model=settings.gemini_voice_model, config=config
        ) as gemini:
            await self.send_json({"type": "ready", "conversation_id": self.conv_id})
            await asyncio.gather(
                self._pump_mic_to_gemini(gemini),
                self._pump_gemini_to_client(gemini),
                self._pump_client_to_bridge(),
            )

    async def _pump_client_to_bridge(self) -> None:
        try:
            while not self.stop_event.is_set():
                msg = await self.ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    self.stop_event.set()
                    break
                if "bytes" in msg and msg["bytes"] is not None:
                    try:
                        self.inbound_audio.put_nowait(msg["bytes"])
                    except asyncio.QueueFull:
                        try:
                            _ = self.inbound_audio.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        try:
                            self.inbound_audio.put_nowait(msg["bytes"])
                        except asyncio.QueueFull:
                            pass
                    continue
                if "text" in msg and msg["text"]:
                    # control frames (text, interrupt, etc.) — Task 4
                    pass
        except WebSocketDisconnect:
            self.stop_event.set()
        finally:
            try:
                self.inbound_audio.put_nowait(None)
            except asyncio.QueueFull:
                pass

    async def _pump_mic_to_gemini(self, session) -> None:
        while not self.stop_event.is_set():
            pcm = await self.inbound_audio.get()
            if pcm is None:
                break
            try:
                await session.send_realtime_input(
                    audio=genai_types.Blob(
                        data=pcm, mime_type="audio/pcm;rate=16000"
                    )
                )
            except Exception:
                log.exception("send_realtime_input failed")
                self.stop_event.set()
                break

    async def _pump_gemini_to_client(self, session) -> None:
        try:
            async for response in session.receive():
                if self.stop_event.is_set():
                    break
                # Audio out
                data = getattr(response, "data", None)
                if data:
                    await self.send_bytes(data)
                # More handling in Task 2 (transcripts) + Task 3 (tools)
        except Exception:
            log.exception("gemini receive failed")
            await self.send_json({"type": "error", "detail": "Gemini stream failed"})
            self.stop_event.set()


@router.websocket("/voice/ws")
async def voice_ws(ws: WebSocket) -> None:
    citizen_id_opt: UUID | None = current_citizen_id_from_cookies(ws.cookies)
    if citizen_id_opt is None:
        await ws.close(code=4401)
        return
    await ws.accept()
    session = VoiceBridgeSession(ws=ws, citizen_id=str(citizen_id_opt))
    try:
        await session.run()
    except WebSocketDisconnect:
        log.info("client disconnected mid-session")
    except Exception:
        log.exception("voice bridge crashed")
        await session.send_json({"type": "error", "detail": "Bridge error"})
    finally:
        try:
            await ws.close()
        except Exception:
            pass
```

- [ ] **Step 2: Add the cookie auth helper**

The existing `app.security` likely exposes `current_citizen_id` as a FastAPI dependency that reads from `Request.cookies`. For a WebSocket we read cookies eagerly, so add a non-Depends variant.

Inspect first:
```bash
grep -n "current_citizen_id\|def " backend/app/security.py | head -40
```

Then add (or extract) at the bottom of `backend/app/security.py`:
```python
def current_citizen_id_from_cookies(cookies: dict) -> UUID | None:
    """Resolve citizen ID from a raw cookies dict (e.g., from a WebSocket upgrade)."""
    token = cookies.get("civicai_session") or cookies.get("session")
    if not token:
        return None
    try:
        return _decode_session_token(token)  # reuse existing decoder
    except Exception:
        return None
```

Replace `civicai_session` / `session` / `_decode_session_token` with the actual cookie name and decode function found in `security.py`. If the existing dep already accepts cookies, just import and adapt.

- [ ] **Step 3: Register the router**

In `backend/app/main.py`, find where `voice.router` is included (probably `app.include_router(voice.router)`) and add right after:
```python
from app import agent_voice
app.include_router(agent_voice.router)
```

- [ ] **Step 4: Run the backend**

```bash
cd backend && uvicorn app.main:app --reload --port 8000
```
Expected: clean startup, no import errors.

- [ ] **Step 5: Verify the endpoint exists**

```bash
curl -sI http://localhost:8000/openapi.json | head -1
```
Expected: `HTTP/1.1 200 OK`. Then check the OpenAPI for `/agent/voice/ws` (WS endpoints show up under the `paths` key if FastAPI auto-documented them):
```bash
curl -s http://localhost:8000/openapi.json | python -c "import sys,json; d=json.load(sys.stdin); print([p for p in d.get('paths',{}) if 'voice' in p])"
```
Expected output includes `/agent/voice/ws`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent_voice.py backend/app/main.py backend/app/security.py
git commit -m "feat(voice): backend WS bridge skeleton — audio round-trip to Gemini Live"
```

---

## Task 2: Wire live transcripts from Gemini → JSON control frames

Extend `_pump_gemini_to_client` to parse `server_content.input_transcription` and `server_content.output_transcription` partials and emit `user_delta` / `agent_delta` frames. On `turn_complete` emit `user_done` / `agent_done`.

**Files:**
- Modify: `backend/app/agent_voice.py`

- [ ] **Step 1: Add transcript buffers + finalization to the session**

Add to `VoiceBridgeSession`:
```python
@dataclass
class VoiceBridgeSession:
    # ... existing fields ...
    user_buf: str = ""
    agent_buf: str = ""
    last_role: str | None = None  # 'user' | 'agent' | None
```

- [ ] **Step 2: Add a flush helper**

```python
    async def _flush_role(self, role: str) -> None:
        if role == "user" and self.user_buf:
            text = self.user_buf
            self.user_buf = ""
            await self.send_json({"type": "user_done", "text": text})
            await self._persist_turn(role="user", text=text)
        elif role == "agent" and self.agent_buf:
            text = self.agent_buf
            self.agent_buf = ""
            await self.send_json({"type": "agent_done", "text": text, "tool_calls": []})
            await self._persist_turn(role="model", text=text)

    async def _persist_turn(self, role: str, text: str) -> None:
        # Stub; filled in Task 5.
        return
```

- [ ] **Step 3: Update `_pump_gemini_to_client` to parse transcripts**

Replace the body with:
```python
    async def _pump_gemini_to_client(self, session) -> None:
        try:
            async for response in session.receive():
                if self.stop_event.is_set():
                    break

                # Agent audio out
                data = getattr(response, "data", None)
                if data:
                    await self.send_bytes(data)

                sc = getattr(response, "server_content", None)
                if sc is not None:
                    # User-side transcription (mic STT)
                    in_tx = getattr(sc, "input_transcription", None)
                    if in_tx is not None and getattr(in_tx, "text", None):
                        if self.last_role == "agent":
                            await self._flush_role("agent")
                        self.last_role = "user"
                        self.user_buf += in_tx.text
                        await self.send_json(
                            {"type": "user_delta", "text": self.user_buf}
                        )

                    # Agent-side transcription (parallel to TTS audio)
                    out_tx = getattr(sc, "output_transcription", None)
                    if out_tx is not None and getattr(out_tx, "text", None):
                        if self.last_role == "user":
                            await self._flush_role("user")
                        self.last_role = "agent"
                        self.agent_buf += out_tx.text
                        await self.send_json(
                            {"type": "agent_delta", "text": self.agent_buf}
                        )

                    if getattr(sc, "interrupted", False):
                        await self.send_json({"type": "interrupted"})

                    if getattr(sc, "turn_complete", False):
                        # finalize whichever role spoke last
                        if self.last_role == "user":
                            await self._flush_role("user")
                        elif self.last_role == "agent":
                            await self._flush_role("agent")
                        self.last_role = None

                # tool_call handled in Task 3
        except Exception:
            log.exception("gemini receive failed")
            await self.send_json({"type": "error", "detail": "Gemini stream failed"})
            self.stop_event.set()
```

Note on field names: `server_content.input_transcription` / `output_transcription` come from the v1beta protocol; the Python SDK names match underscored. If the upgraded SDK uses `inputTranscription` (camel), adjust to `getattr(sc, "inputTranscription", None)`. The smoke test below verifies.

- [ ] **Step 4: Smoke test with a quick connect**

Start backend, then from `frontend/` open `http://localhost:3000`, switch to voice mode, say one sentence. In the backend logs:
- expect to see `user_delta` / `user_done` and `agent_delta` / `agent_done` JSON sent
- in the browser DevTools Network panel, the WS frames should show the same

If `input_transcription` is `None` even though audio is flowing, log the raw `response` object once and check actual field names:
```python
log.info("raw response: %r", response)
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent_voice.py
git commit -m "feat(voice): forward Gemini transcripts as live JSON frames"
```

---

## Task 3: Tool dispatch in-process

When Gemini emits a `tool_call`, look up the function in `REGISTRY`, call it with `ToolContext`, send result back to Gemini via `send_tool_response`, and emit `tool_call` + `tool_result` JSON frames to the browser so the right pane updates.

**Files:**
- Modify: `backend/app/agent_voice.py`

- [ ] **Step 1: Build a ToolContext on session start**

In `VoiceBridgeSession.run()`, right after resolving `self.conv_id`:
```python
        tool_ctx = ToolContext(
            citizen_id=self.citizen_id,
            document_id=self.start_payload.document_id,
        )
        self.tool_ctx = tool_ctx
```

Add to the dataclass:
```python
    tool_ctx: ToolContext | None = None
```

- [ ] **Step 2: Add tool dispatch helper**

Append to `VoiceBridgeSession`:
```python
    async def _dispatch_tool(
        self, name: str, args: dict[str, Any], call_id: str | None
    ) -> genai_types.FunctionResponse:
        await self.send_json(
            {"type": "tool_call", "name": name, "arguments": args}
        )
        tool = REGISTRY.get(name)
        if tool is None:
            output: dict[str, Any] = {"error": f"unknown_tool:{name}"}
        else:
            try:
                result = await tool(self.tool_ctx, **args)
                if hasattr(result, "model_dump"):
                    result = result.model_dump(mode="json")
                output = {"output": result} if not isinstance(result, dict) or "error" not in result else result
            except Exception as e:  # noqa: BLE001
                log.exception("voice tool %s failed", name)
                output = {"error": str(e)}
        await self.send_json(
            {"type": "tool_result", "name": name, "output": output}
        )
        return genai_types.FunctionResponse(
            id=call_id, name=name, response=output
        )
```

- [ ] **Step 3: Wire tool_call branch in receive loop**

In `_pump_gemini_to_client`, add inside the `async for` after the `server_content` block:
```python
                tc = getattr(response, "tool_call", None)
                if tc is not None and getattr(tc, "function_calls", None):
                    responses: list[genai_types.FunctionResponse] = []
                    for fc in tc.function_calls:
                        responses.append(
                            await self._dispatch_tool(
                                name=fc.name,
                                args=dict(fc.args) if fc.args else {},
                                call_id=getattr(fc, "id", None),
                            )
                        )
                    try:
                        await session.send_tool_response(function_responses=responses)
                    except Exception:
                        log.exception("send_tool_response failed")
```

- [ ] **Step 4: Tell Gemini about the tools at setup**

In `VoiceBridgeSession.run()`, replace the `config = genai_types.LiveConnectConfig(...)` block with one that includes the tools. Add a module-level constant:
```python
_BROWSER_FUNCTION_DECLS: list[dict[str, Any]] = [
    {
        "name": "lookup_procedure",
        "description": "Caută procedura primăriei pentru o cerere în limba română.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"query": {"type": "STRING"}},
            "required": ["query"],
        },
    },
    {
        "name": "set_field",
        "description": "Setează un câmp în documentul activ.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING"},
                "value": {"type": "STRING"},
            },
            "required": ["name", "value"],
        },
    },
    {
        "name": "generate_pdf",
        "description": "Generează PDF-ul documentului activ.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "deliver",
        "description": "Finalizează documentul: save / send / print.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "delivery": {"type": "STRING", "enum": ["save", "send", "print"]},
            },
            "required": ["delivery"],
        },
    },
    {
        "name": "find_redirect",
        "description": "Decide dacă o cerere este în afara primăriei.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING"},
                "target": {"type": "STRING"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "set_reminder",
        "description": "Creează un memento proactiv (rar; numai la cerere explicită).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "kind": {
                    "type": "STRING",
                    "enum": ["in_scope_procedure", "external_redirect"],
                },
                "title": {"type": "STRING"},
                "procedure_id": {"type": "STRING"},
                "redirect_target": {"type": "STRING"},
                "deadline_days": {"type": "NUMBER"},
            },
            "required": ["kind", "title"],
        },
    },
    {
        "name": "propose_widget",
        "description": "Propune o întrebare structurată ca widget UI (choice/confirm/date).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "type": {"type": "STRING", "enum": ["choice", "confirm", "date"]},
                "question": {"type": "STRING"},
                "options": {"type": "ARRAY", "items": {"type": "STRING"}},
                "target_field": {"type": "STRING"},
            },
            "required": ["type", "question"],
        },
    },
]
```

Then update the config:
```python
        config = genai_types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=genai_types.Content(
                role="system",
                parts=[genai_types.Part.from_text(text=system_prompt)],
            ),
            tools=[{"function_declarations": _BROWSER_FUNCTION_DECLS}],
            speech_config=genai_types.SpeechConfig(
                voice_config=genai_types.VoiceConfig(
                    prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                        voice_name=settings.gemini_voice_name,
                    )
                ),
                language_code="ro-RO",
            ),
            input_audio_transcription=genai_types.AudioTranscriptionConfig(),
            output_audio_transcription=genai_types.AudioTranscriptionConfig(),
        )
```

- [ ] **Step 5: Smoke test a tool**

With backend running, voice-call the agent and say "Caut procedura pentru schimbare domiciliu." Watch backend logs:
- expect `tool_call` JSON sent
- expect `lookup_procedure` invoked with `query="schimbare domiciliu"`
- expect `tool_result` JSON sent

If the tool throws because `tool_ctx.document_id is None` and that's invalid, that's expected for tools that require a doc. Pick a tool that doesn't (e.g. `lookup_procedure`) for this smoke test.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent_voice.py
git commit -m "feat(voice): in-process tool dispatch in WS bridge"
```

---

## Task 4: Handle text-input-during-voice frames

When the user types into Composer while voice is live, the frontend sends `{"type": "text", "text": "..."}`. Bridge forwards as `client_content` to Gemini.

**Files:**
- Modify: `backend/app/agent_voice.py`

- [ ] **Step 1: Pass the gemini session into the client pump**

The current `_pump_client_to_bridge` doesn't have a handle on `session`. Refactor so it does. Change `run()` to construct it differently:
```python
        async with client.aio.live.connect(
            model=settings.gemini_voice_model, config=config
        ) as gemini:
            self.gemini = gemini
            await self.send_json({"type": "ready", "conversation_id": self.conv_id})
            await asyncio.gather(
                self._pump_mic_to_gemini(gemini),
                self._pump_gemini_to_client(gemini),
                self._pump_client_to_bridge(),
            )
```

Add `gemini: Any = None` to the dataclass.

- [ ] **Step 2: Handle the text frame**

In `_pump_client_to_bridge`, replace the `if "text" in msg and msg["text"]:` branch:
```python
                if "text" in msg and msg["text"]:
                    try:
                        payload = json.loads(msg["text"])
                    except Exception:
                        continue
                    if payload.get("type") == "text" and self.gemini is not None:
                        text = payload.get("text") or ""
                        if text.strip():
                            try:
                                await self.gemini.send_client_content(
                                    turns=[
                                        genai_types.Content(
                                            role="user",
                                            parts=[genai_types.Part.from_text(text=text)],
                                        )
                                    ],
                                    turn_complete=True,
                                )
                            except Exception:
                                log.exception("send_client_content failed")
                    elif payload.get("type") == "interrupt" and self.gemini is not None:
                        # Optional v1 — no-op for now, the audit B-NEW-H follow-up.
                        pass
```

- [ ] **Step 3: Smoke test**

With voice live, switch to typing in the textarea and send a message. Backend should call `send_client_content`. Gemini should reply with audio + transcript.

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent_voice.py
git commit -m "feat(voice): handle text-during-voice frames in WS bridge"
```

---

## Task 5: Shared conversation history (seed on start + persist on done)

When the bridge starts, prepend the existing `_conversations[conv_id]` history to the Gemini session as `client_content` (with `turn_complete=False` so the model doesn't respond yet). On each `*_done`, append the new turn to `_conversations`.

**Files:**
- Modify: `backend/app/agent.py` (verify `_conversations` + `_remember` are importable)
- Modify: `backend/app/agent_voice.py`

- [ ] **Step 1: Verify the exports**

```bash
python -c "from app.agent import _conversations, _remember; print(type(_conversations), callable(_remember))"
```
Expected: `<class 'collections.OrderedDict'> True` (or similar). If `_remember` isn't there, look for `_persist` / `_save_history` or whatever the existing name is and use it.

- [ ] **Step 2: Import in the bridge**

At the top of `agent_voice.py`:
```python
from app.agent import _conversations, _remember
```

- [ ] **Step 3: Seed history on start**

In `run()`, after `tool_ctx` setup and before the `async with client.aio.live.connect`:
```python
        history: list[genai_types.Content] = list(_conversations.get(self.conv_id, []))
```

After `await self.send_json({"type": "ready", ...})`, but before `asyncio.gather(...)`:
```python
            if history:
                try:
                    await gemini.send_client_content(
                        turns=history,
                        turn_complete=False,
                    )
                    log.info("seeded %d prior turns from text history", len(history))
                except Exception:
                    log.exception("history seed failed — continuing without")
```

- [ ] **Step 4: Implement `_persist_turn` (was stubbed in Task 2)**

Replace the stub with:
```python
    async def _persist_turn(self, role: str, text: str) -> None:
        try:
            content = genai_types.Content(
                role=role,
                parts=[genai_types.Part.from_text(text=text)],
            )
            current = list(_conversations.get(self.conv_id, []))
            current.append(content)
            _remember(self.conv_id, current)
        except Exception:
            log.exception("persist_turn failed for role=%s", role)
```

- [ ] **Step 5: Smoke test mode-switch context**

1. Open the app, type a few text messages.
2. Switch to voice, say "Despre ce vorbeam mai devreme?" Expect the agent to know.
3. Switch back to text. Type "Repetă ultimul lucru pe care l-ai spus." Expect the agent to recall what it said in voice.

If the second step doesn't work, log `len(history)` and verify it includes the model turns.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent_voice.py
git commit -m "feat(voice): unify conversation history between text + voice paths"
```

---

## Task 6: Frontend voiceWs.ts — typed WebSocket client

Stand up the raw client. No React, no store wiring yet.

**Files:**
- Create: `frontend/lib/voiceWs.ts`

- [ ] **Step 1: Write the module**

```typescript
/**
 * Raw WebSocket client for the backend /agent/voice/ws bridge.
 * See docs/superpowers/specs/2026-05-23-voice-ws-bridge-design.md §5
 * for the frame protocol.
 */

const LOG = (...args: unknown[]) =>
  console.log("[civicai:voiceWs]", ...args);
const ERR = (...args: unknown[]) =>
  console.error("[civicai:voiceWs]", ...args);

export type VoiceWsToolCall = {
  name: string;
  arguments: Record<string, unknown>;
};

export type VoiceWsHandlers = {
  onReady: (conversationId: string) => void;
  onUserDelta: (text: string) => void;
  onUserDone: (text: string) => void;
  onAgentDelta: (text: string) => void;
  onAgentDone: (text: string, toolCalls: VoiceWsToolCall[]) => void;
  onToolCall: (name: string, args: Record<string, unknown>) => void;
  onToolResult: (name: string, output: Record<string, unknown>) => void;
  onAudio: (pcm: ArrayBuffer) => void;
  onInterrupted: () => void;
  onError: (detail: string) => void;
  onClose: () => void;
};

export type VoiceWsStartPayload = {
  documentId?: string;
  conversationId?: string;
  preferences?: {
    simpleLanguage?: boolean;
    voiceOnly?: boolean;
  };
};

export class VoiceWs {
  private ws: WebSocket | null = null;
  private opened = false;
  private toolCallsThisTurn: VoiceWsToolCall[] = [];

  constructor(private handlers: VoiceWsHandlers) {}

  connect(url: string): Promise<void> {
    LOG("connect", url);
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        LOG("onopen");
        this.opened = true;
        this.ws = ws;
        resolve();
      };

      ws.onerror = (e) => {
        ERR("onerror", e);
        if (!this.opened) reject(new Error("WebSocket open failed"));
      };

      ws.onclose = (e) => {
        LOG("onclose", { code: e.code, reason: e.reason });
        this.opened = false;
        this.ws = null;
        this.handlers.onClose();
      };

      ws.onmessage = (e) => this.handleMessage(e);
    });
  }

  sendStart(payload: VoiceWsStartPayload): void {
    this.send({
      type: "start",
      document_id: payload.documentId,
      conversation_id: payload.conversationId,
      preferences: {
        simple_language: payload.preferences?.simpleLanguage ?? false,
        voice_only: payload.preferences?.voiceOnly ?? false,
      },
    });
  }

  sendText(text: string): void {
    this.send({ type: "text", text });
  }

  sendInterrupt(): void {
    this.send({ type: "interrupt" });
  }

  sendAudio(chunk: ArrayBuffer): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(chunk);
  }

  close(): void {
    LOG("close");
    try {
      this.ws?.close();
    } catch {
      /* noop */
    }
    this.ws = null;
  }

  private send(obj: Record<string, unknown>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      ERR("send before open — dropping", obj);
      return;
    }
    this.ws.send(JSON.stringify(obj));
  }

  private handleMessage(event: MessageEvent): void {
    if (event.data instanceof ArrayBuffer) {
      this.handlers.onAudio(event.data);
      return;
    }
    let msg: Record<string, unknown>;
    try {
      msg = JSON.parse(event.data as string);
    } catch (e) {
      ERR("bad JSON frame:", event.data, e);
      return;
    }
    const type = msg.type as string;
    switch (type) {
      case "ready":
        this.handlers.onReady(msg.conversation_id as string);
        break;
      case "user_delta":
        this.handlers.onUserDelta((msg.text as string) ?? "");
        break;
      case "user_done":
        this.handlers.onUserDone((msg.text as string) ?? "");
        break;
      case "agent_delta":
        this.handlers.onAgentDelta((msg.text as string) ?? "");
        break;
      case "agent_done": {
        const text = (msg.text as string) ?? "";
        const calls = this.toolCallsThisTurn;
        this.toolCallsThisTurn = [];
        this.handlers.onAgentDone(text, calls);
        break;
      }
      case "tool_call": {
        const name = msg.name as string;
        const args = (msg.arguments as Record<string, unknown>) ?? {};
        this.toolCallsThisTurn.push({ name, arguments: args });
        this.handlers.onToolCall(name, args);
        break;
      }
      case "tool_result":
        this.handlers.onToolResult(
          msg.name as string,
          (msg.output as Record<string, unknown>) ?? {},
        );
        break;
      case "interrupted":
        this.handlers.onInterrupted();
        break;
      case "error":
        this.handlers.onError((msg.detail as string) ?? "Eroare necunoscută");
        break;
      default:
        ERR("unknown frame type:", type, msg);
    }
  }
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors in `voiceWs.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/voiceWs.ts
git commit -m "feat(voice): frontend WS client for backend voice bridge"
```

---

## Task 7: sessionStore live-message actions + Message.live flag

Add the live-message lifecycle actions. Update `Message` type. ChatStream render comes next.

**Files:**
- Modify: `frontend/lib/types.ts` (or wherever `Message` is defined)
- Modify: `frontend/lib/sessionStore.ts`

- [ ] **Step 1: Add `live` to Message type**

Find the `Message` type definition (likely `frontend/lib/types.ts`):
```bash
grep -n "type Message\|interface Message" frontend/lib/types.ts frontend/lib/sessionStore.ts
```

Add a field:
```typescript
export type Message = {
  id: string;
  role: "user" | "agent" | "system";
  text: string;
  // ... existing fields ...
  live?: boolean;  // true while transcript is still arriving
  widgets?: WidgetSpec[];
};
```

- [ ] **Step 2: Add live-message actions to the Zustand slice**

In `frontend/lib/sessionStore.ts`, find the actions block (where `sendText`, `applyToolResult`, etc. live) and add:
```typescript
  beginLiveMessage: (role: "user" | "agent") => {
    const id = `live_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    set((s) => {
      const messages = [...s.messages, { id, role, text: "", live: true }];
      saveMessages(s.activeDocId, messages);
      return { messages };
    });
    return id;
  },
  updateLiveMessage: (id: string, text: string) => {
    set((s) => {
      const messages = s.messages.map((m) =>
        m.id === id ? { ...m, text } : m,
      );
      saveMessages(s.activeDocId, messages);
      return { messages };
    });
  },
  finalizeLiveMessage: (id: string, text: string) => {
    set((s) => {
      const messages = s.messages.map((m) =>
        m.id === id ? { ...m, text, live: false } : m,
      );
      saveMessages(s.activeDocId, messages);
      return { messages };
    });
  },
```

Add them to the store type/interface too:
```typescript
type SessionStore = {
  // ... existing ...
  beginLiveMessage: (role: "user" | "agent") => string;
  updateLiveMessage: (id: string, text: string) => void;
  finalizeLiveMessage: (id: string, text: string) => void;
};
```

- [ ] **Step 3: Type-check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/sessionStore.ts
git commit -m "feat(voice): live-message lifecycle actions in session store"
```

---

## Task 8: ChatStream renders live messages

Live messages render as normal messages but with a subtle pulsing-border affordance so the user knows it's still being transcribed.

**Files:**
- Modify: `frontend/components/chat/ChatStream.tsx`

- [ ] **Step 1: Find the message render**

```bash
grep -n "messages.map\|role ===" frontend/components/chat/ChatStream.tsx | head -20
```

- [ ] **Step 2: Branch on `live`**

Find the JSX where each message renders. Add a className conditional:
```tsx
<div
  className={[
    "message",
    `message-${m.role}`,
    m.live ? "message-live" : "",
  ]
    .filter(Boolean)
    .join(" ")}
>
  {m.text}
  {m.live ? <span className="message-live-caret">▍</span> : null}
</div>
```

- [ ] **Step 3: Add the CSS**

Find the chat CSS (likely `frontend/styles/chat.css` or similar). Add:
```css
.message-live {
  border-left: 2px solid currentColor;
  animation: civicai-live-pulse 1.2s ease-in-out infinite;
}
.message-live-caret {
  display: inline-block;
  margin-left: 2px;
  animation: civicai-live-caret-blink 0.9s steps(2) infinite;
}
@keyframes civicai-live-pulse {
  0%, 100% { border-left-color: currentColor; }
  50%      { border-left-color: transparent; }
}
@keyframes civicai-live-caret-blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0; }
}
```

If the project uses Tailwind utility classes instead of a CSS file, do the equivalent via `data-live` attribute + Tailwind variants. Inspect the existing styling approach before deciding.

- [ ] **Step 4: Type-check + visual sanity**

```bash
cd frontend && npx tsc --noEmit && npm run dev
```
Open `http://localhost:3000`, force a `live: true` message via DevTools (or wait until Task 10) and confirm the pulsing border + caret render.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/chat/ChatStream.tsx frontend/styles/*
git commit -m "feat(voice): live-message render with pulsing-border affordance"
```

---

## Task 9: useVoiceAgentBridge hook

Drop-in replacement for `useVoiceAgent`. Same `VoiceAgentHook` interface. Internally wires `VoiceWs` ↔ `sessionStore` live-message actions ↔ existing `startMicRecorder` / `startPlayer`.

**Files:**
- Create: `frontend/lib/useVoiceAgentBridge.ts`

- [ ] **Step 1: Write the hook**

```typescript
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSessionStore } from "./sessionStore";
import type { VoicePreferences } from "./types";
import {
  startMicRecorder,
  startPlayer,
  type PlayerHandle,
  type RecorderHandle,
} from "./audioWorklet";
import { VoiceWs, type VoiceWsToolCall } from "./voiceWs";
import {
  VoiceAgentMicDeniedError,
  type ToolCallHandler,
  type VoiceAgentHook,
  type VoiceAgentStartOpts,
  type VoiceAgentState,
} from "./useVoiceAgent";

const LOG = (...args: unknown[]) =>
  console.log("[civicai:voice-bridge]", ...args);
const ERR = (...args: unknown[]) =>
  console.error("[civicai:voice-bridge]", ...args);

function wsUrlFor(path: string): string {
  if (typeof window === "undefined") return path;
  const base = process.env.NEXT_PUBLIC_API_BASE ?? window.location.origin;
  const url = new URL(path, base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

export function useVoiceAgentBridge(): VoiceAgentHook {
  const [state, setState] = useState<VoiceAgentState>("idle");

  const wsRef = useRef<VoiceWs | null>(null);
  const recorderRef = useRef<RecorderHandle | null>(null);
  const playerRef = useRef<PlayerHandle | null>(null);
  const userToolHandlerRef = useRef<ToolCallHandler | null>(null);

  const liveUserIdRef = useRef<string | null>(null);
  const liveAgentIdRef = useRef<string | null>(null);

  const store = useSessionStore.getState; // imperative access; we don't subscribe

  const registerToolHandler = useCallback((handler: ToolCallHandler) => {
    userToolHandlerRef.current = handler;
  }, []);

  const stop = useCallback(() => {
    LOG("stop()");
    wsRef.current?.close();
    recorderRef.current?.stop();
    playerRef.current?.stop();
    wsRef.current = null;
    recorderRef.current = null;
    playerRef.current = null;
    liveUserIdRef.current = null;
    liveAgentIdRef.current = null;
    setState("idle");
  }, []);

  const start: VoiceAgentHook["start"] = useCallback(
    async (opts: VoiceAgentStartOpts) => {
      try {
        LOG("start", opts);
        setState("connecting");

        const player = await startPlayer();
        playerRef.current = player;

        const ws = new VoiceWs({
          onReady: (convId) => {
            LOG("ready", convId);
            setState("listening");
          },
          onUserDelta: (text) => {
            if (!liveUserIdRef.current) {
              if (liveAgentIdRef.current) {
                // finalize whatever the agent was saying (defensive)
                store().finalizeLiveMessage(liveAgentIdRef.current, text);
                liveAgentIdRef.current = null;
              }
              liveUserIdRef.current = store().beginLiveMessage("user");
            }
            store().updateLiveMessage(liveUserIdRef.current!, text);
            opts.onUserDelta?.(text);
          },
          onUserDone: (text) => {
            const id = liveUserIdRef.current;
            if (id) store().finalizeLiveMessage(id, text);
            liveUserIdRef.current = null;
            opts.onUserMessage?.(text);
          },
          onAgentDelta: (text) => {
            if (!liveAgentIdRef.current) {
              if (liveUserIdRef.current) {
                store().finalizeLiveMessage(liveUserIdRef.current, "");
                liveUserIdRef.current = null;
              }
              liveAgentIdRef.current = store().beginLiveMessage("agent");
              setState("speaking");
            }
            store().updateLiveMessage(liveAgentIdRef.current!, text);
            opts.onAgentDelta?.(text);
          },
          onAgentDone: (text, toolCalls) => {
            const id = liveAgentIdRef.current;
            if (id) store().finalizeLiveMessage(id, text);
            liveAgentIdRef.current = null;
            setState("listening");
            opts.onAgentMessage?.(
              text,
              toolCalls.map((c) => ({ name: c.name, args: c.arguments })),
            );
          },
          onToolCall: (name, args) => {
            LOG("tool_call", name, args);
            // No browser-side dispatch — backend handles it.
            // Pass through to UI handler so right pane can react if needed.
            void userToolHandlerRef.current?.(name, args).catch(() => undefined);
          },
          onToolResult: (name, output) => {
            LOG("tool_result", name, output);
            void userToolHandlerRef.current?.(name, {
              _result: output,
            }).catch(() => undefined);
          },
          onAudio: (pcm) => {
            playerRef.current?.feed(pcm);
          },
          onInterrupted: () => {
            LOG("interrupted");
            playerRef.current?.flush();
            setState("listening");
          },
          onError: (detail) => {
            ERR("bridge error:", detail);
            setState("error");
          },
          onClose: () => {
            LOG("ws closed");
            if (state !== "error") setState("idle");
          },
        });
        wsRef.current = ws;

        await ws.connect(wsUrlFor("/agent/voice/ws"));
        ws.sendStart({
          documentId: opts.documentId,
          preferences: {
            simpleLanguage: opts.preferences?.simple_language,
            voiceOnly: opts.preferences?.voice_only,
          },
        });

        let recorder: RecorderHandle;
        try {
          recorder = await startMicRecorder((chunk) => ws.sendAudio(chunk));
        } catch (micErr) {
          ERR("mic denied", micErr);
          stop();
          throw new VoiceAgentMicDeniedError();
        }
        recorderRef.current = recorder;

        LOG("listening — fully wired");
      } catch (err) {
        ERR("start failed", err);
        if (!(err instanceof VoiceAgentMicDeniedError)) stop();
        setState("error");
        throw err;
      }
    },
    [state, store, stop],
  );

  const sendText: VoiceAgentHook["sendText"] = useCallback(async (text) => {
    if (!wsRef.current) {
      throw new Error("Voice bridge not started; call start() first.");
    }
    wsRef.current.sendText(text);
  }, []);

  useEffect(() => {
    return () => stop();
  }, [stop]);

  return { state, start, stop, sendText, registerToolHandler };
}
```

Note: I re-export `VoiceAgentMicDeniedError` from `useVoiceAgent.ts` (it already exists). If TypeScript complains about the import shape, switch to a local re-export.

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/useVoiceAgentBridge.ts
git commit -m "feat(voice): React hook for backend WS bridge — drop-in replacement"
```

---

## Task 10: ChatSurface env switch + end-to-end smoke

Add the feature-flag gate so QA can A/B by toggling `NEXT_PUBLIC_VOICE_BRIDGE`. Then run a full demo path end-to-end.

**Files:**
- Modify: `frontend/components/chat/ChatSurface.tsx`
- Optional: `frontend/.env.local` (for dev default)

- [ ] **Step 1: Add the switch**

Find where `useVoiceAgent()` is invoked in `ChatSurface.tsx` (audit references it around lines 90-100):
```bash
grep -n "useVoiceAgent" frontend/components/chat/ChatSurface.tsx
```

Replace the import + call:
```typescript
import { useVoiceAgent } from "@/lib/useVoiceAgent";
import { useVoiceAgentBridge } from "@/lib/useVoiceAgentBridge";

// ...inside the component, replacing the existing `const voice = useVoiceAgent();`:
const useVoiceHook =
  process.env.NEXT_PUBLIC_VOICE_BRIDGE === "1"
    ? useVoiceAgentBridge
    : useVoiceAgent;
const voice = useVoiceHook();
```

⚠️ Don't use `useVoiceHook()` directly inside a conditional — React enforces stable hook order. The pattern above is fine because the assignment happens BEFORE the call, and `process.env.NEXT_PUBLIC_VOICE_BRIDGE` is inlined at build time so it doesn't change at runtime.

- [ ] **Step 2: Document the env var**

If `frontend/.env.example` exists, append:
```
# Set to "1" to use the backend voice WS bridge (default: 0 → direct browser WS).
NEXT_PUBLIC_VOICE_BRIDGE=0
```
Otherwise add the line to `frontend/.env.local` for dev.

- [ ] **Step 3: Run the stack**

Two terminals:
```bash
# terminal 1
cd backend && uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend && NEXT_PUBLIC_VOICE_BRIDGE=1 npm run dev
```

- [ ] **Step 4: Demo smoke path**

In the browser at `http://localhost:3000`:

1. Log in (existing auth).
2. Pick a procedure (e.g. "schimbare domiciliu").
3. Switch to voice mode.
4. Say "Vreau să schimb domiciliul." Expect:
   - your transcript appears as a live message and finalizes
   - agent responds in audio + a live message that finalizes
   - if the agent calls `set_field`, the right pane updates
5. Type "Da" into the composer while voice is live. Expect Gemini to receive it as a turn.
6. Switch back to text mode. Type "Continuă." Expect the agent to remember the voice context.
7. Refresh the page. Expect prior voice messages to remain visible (localStorage).

- [ ] **Step 5: Toggle the flag back to verify the fallback**

```bash
NEXT_PUBLIC_VOICE_BRIDGE=0 npm run dev
```
Voice should still work via the old direct-WS path.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/chat/ChatSurface.tsx frontend/.env.example frontend/.env.local
git commit -m "feat(voice): env-flag switch for backend bridge vs direct WS"
```

---

## Self-review notes

**Spec coverage check:**
- §1 goals (1) key server-side ✓ Task 1 ; (2) unified history ✓ Task 5 ; (3) in-process tools ✓ Task 3 ; (4) live transcripts ✓ Tasks 2+7+8+9
- §4 architecture ✓ Tasks 1-5 (backend) + 6-9 (frontend)
- §5 frame protocol — every frame type covered: `start` ✓ Task 1+6 ; `text` ✓ Task 4+6 ; `interrupt` ✓ Task 4+6 (no-op v1) ; audio binary in/out ✓ Tasks 1+6 ; `ready` ✓ Task 1+6 ; `user_delta`/`user_done`/`agent_delta`/`agent_done` ✓ Tasks 2+6+9 ; `tool_call`/`tool_result` ✓ Tasks 3+6+9 ; `interrupted` ✓ Tasks 2+6+9 ; `error` ✓ Tasks 1+6+9
- §7.3 sessionStore live actions ✓ Task 7
- §7.4 ChatSurface env gate ✓ Task 10
- §8 migration (feature flag, kept files) ✓ Task 10

**Placeholder scan:** All steps have concrete code. The "if SDK uses camelCase" branch in Task 2 step 3 is a contingency, not a placeholder — it tells the engineer exactly what to do in either case.

**Type consistency:** `Message.live`, `beginLiveMessage`, `updateLiveMessage`, `finalizeLiveMessage` are spelled the same everywhere they appear.

**Open risk:** Task 0's SDK upgrade is the highest-variance item. If `>=1.10` doesn't expose `AudioTranscriptionConfig` or the field names differ, Step 3 catches it before downstream tasks. Fallback: try `>=1.30` and re-run.
