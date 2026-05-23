"""Browser ↔ Gemini Live WebSocket bridge.

Patterned after backend/app/twilio_bridge.py. The browser sends PCM16
mono 16 kHz audio over a WebSocket; the backend forwards to Gemini Live
via the Python SDK, relays agent audio back, surfaces live transcripts
as JSON control frames, and dispatches tool-calls in-process against
app.tools.REGISTRY.

JSON control frames — see docs/superpowers/specs/2026-05-23-voice-ws-bridge-design.md
§5 for the full table. The one deviation from the spec: the `start` frame
carries a `token` field (same Bearer JWT used for HTTP) because browsers
cannot set Authorization headers on a WebSocket upgrade.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types as genai_types

from app.agent_tools import REGISTRY as TOOLS_REGISTRY, ToolContext, dispatch, permitted_tools
from app.citizens import fetch_citizen_by_id
from app.config import get_settings
from app.prompts import build_system_prompt
from app.security import decode_token
from app.sessions import (
    Session as DbSession,
    SessionState,
    fetch_or_create_session,
    update_session,
)

router = APIRouter(prefix="/agent", tags=["voice"])
log = logging.getLogger("agent_voice")


def _browser_function_declarations() -> list[dict[str, Any]]:
    """Single source of truth: the agent_tools REGISTRY.

    Gemini Live locks tools at connect time, so we send all 6 declarations.
    The dispatcher then refuses out-of-state calls — the model gets an
    error result it can apologize about, rather than a permitted-tools
    list that changes mid-session.
    """
    return [t.function_declaration() for t in TOOLS_REGISTRY.values()]


@dataclass
class VoiceStartPayload:
    token: str
    document_id: str | None = None
    conversation_id: str | None = None
    simple_language: bool = False
    voice_only: bool = False


@dataclass
class VoiceBridgeSession:
    ws: WebSocket
    citizen_id: str = ""
    inbound_audio: asyncio.Queue[bytes | None] = field(
        default_factory=lambda: asyncio.Queue(maxsize=200)
    )
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    conv_id: str = ""
    start_payload: VoiceStartPayload | None = None
    tool_ctx: ToolContext | None = None
    db_session: DbSession | None = None
    gemini: Any = None
    user_buf: str = ""
    agent_buf: str = ""
    last_role: str | None = None

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
        # First frame from client must be JSON `start` with a token.
        msg = await self.ws.receive()
        if msg.get("type") != "websocket.receive":
            raise RuntimeError(f"Expected receive, got {msg.get('type')}")
        text = msg.get("text")
        if not text:
            raise RuntimeError("Expected JSON start frame, got binary")
        payload = json.loads(text)
        if payload.get("type") != "start":
            raise RuntimeError(f"Expected start frame, got {payload.get('type')}")
        token = payload.get("token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Missing token in start frame")
        prefs = payload.get("preferences") or {}
        return VoiceStartPayload(
            token=token,
            document_id=payload.get("document_id"),
            conversation_id=payload.get("conversation_id"),
            simple_language=bool(prefs.get("simple_language")),
            voice_only=bool(prefs.get("voice_only")),
        )

    def _resolve_citizen(self, token: str) -> str:
        decoded = decode_token(token)
        sub = decoded.get("sub")
        if not isinstance(sub, str):
            raise RuntimeError("Token subject missing")
        # Validate UUID shape; raises if malformed.
        UUID(sub)
        return sub

    async def run(self) -> None:
        try:
            self.start_payload = await self.wait_for_start()
            self.citizen_id = self._resolve_citizen(self.start_payload.token)
        except Exception as e:  # noqa: BLE001
            log.warning("start frame rejected: %s", e)
            await self.send_json({"type": "error", "detail": f"auth: {e}"})
            await self.ws.close(code=4401)
            return

        self.conv_id = (
            self.start_payload.conversation_id
            or f"conv_{secrets.token_urlsafe(8)}"
        )

        # Resolve or create the Session and pull citizen attributes.
        self.db_session = fetch_or_create_session(
            self.citizen_id, session_id=self.conv_id
        )
        if (
            self.start_payload.document_id
            and not self.db_session.active_document_id
        ):
            self.db_session.active_document_id = self.start_payload.document_id
            if self.db_session.state == SessionState.EXPLORING:
                self.db_session.state = SessionState.FILLING

        try:
            citizen = fetch_citizen_by_id(UUID(self.citizen_id))
            citizen_attrs = citizen.get("attributes") or {}
        except Exception:
            citizen_attrs = {}
        self.tool_ctx = ToolContext(
            citizen_id=self.citizen_id,
            citizen_attributes=citizen_attrs,
        )

        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)

        # Build the system instruction with full state-aware context.
        # We compose a static system prompt + per-session preamble; Gemini
        # Live locks system_instruction at connect time, so we cannot
        # rebuild it per-turn the way the text path does. Subsequent state
        # context lives in the conversation history via tool results +
        # session_snapshot frames.
        from app.session_engine import build_system_instruction

        full_prompt = build_system_instruction(
            self.db_session,
            citizen_attrs,
            simple_language=self.start_payload.simple_language,
            voice_only=self.start_payload.voice_only,
        )

        config = genai_types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=genai_types.Content(
                role="system",
                parts=[genai_types.Part.from_text(text=full_prompt)],
            ),
            tools=[{"function_declarations": _browser_function_declarations()}],
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

        # Rehydrate prior conversation history (text-chat lineage) so
        # voice has full context. session.history is JSON; convert to
        # Content objects for the Live API.
        history: list[genai_types.Content] = []
        for entry in self.db_session.history:
            try:
                history.append(genai_types.Content.model_validate(entry))
            except Exception:
                pass

        async with client.aio.live.connect(
            model=settings.gemini_voice_model, config=config
        ) as gemini:
            self.gemini = gemini
            await self.send_json({"type": "ready", "conversation_id": self.conv_id})
            # Initial state snapshot for the client.
            await self.send_json(
                {"type": "session_snapshot", "snapshot": self.db_session.snapshot()}
            )
            log.info(
                "voice bridge ready conv=%s citizen=%s doc=%s state=%s history_turns=%d",
                self.conv_id,
                self.citizen_id,
                self.db_session.active_document_id,
                self.db_session.state.value,
                len(history),
            )

            # Seed Gemini Live with any prior text-chat history so the voice
            # session has context. turn_complete=False so the model does not
            # respond yet — it just absorbs the prior turns.
            if history:
                try:
                    await gemini.send_client_content(
                        turns=history,
                        turn_complete=False,
                    )
                except Exception:
                    log.exception("history seed failed — continuing without")

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
                if msg.get("bytes") is not None:
                    chunk = msg["bytes"]
                    try:
                        self.inbound_audio.put_nowait(chunk)
                    except asyncio.QueueFull:
                        try:
                            _ = self.inbound_audio.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        try:
                            self.inbound_audio.put_nowait(chunk)
                        except asyncio.QueueFull:
                            pass
                    continue
                if msg.get("text"):
                    try:
                        payload = json.loads(msg["text"])
                    except Exception:
                        log.warning("bad json text frame: %r", msg["text"][:200])
                        continue
                    ptype = payload.get("type")
                    if ptype == "text" and self.gemini is not None:
                        text = (payload.get("text") or "").strip()
                        if text:
                            try:
                                await self.gemini.send_client_content(
                                    turns=[
                                        genai_types.Content(
                                            role="user",
                                            parts=[
                                                genai_types.Part.from_text(text=text)
                                            ],
                                        )
                                    ],
                                    turn_complete=True,
                                )
                            except Exception:
                                log.exception("send_client_content failed")
                    elif ptype == "interrupt":
                        # v1 no-op; reserved for explicit barge-in UX.
                        pass
        except WebSocketDisconnect:
            self.stop_event.set()
        finally:
            try:
                self.inbound_audio.put_nowait(None)
            except asyncio.QueueFull:
                pass

    async def _pump_mic_to_gemini(self, session: Any) -> None:
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

    async def _pump_gemini_to_client(self, session: Any) -> None:
        try:
            async for response in session.receive():
                if self.stop_event.is_set():
                    break

                data = getattr(response, "data", None)
                if data:
                    await self.send_bytes(data)

                sc = getattr(response, "server_content", None)
                if sc is not None:
                    in_tx = getattr(sc, "input_transcription", None)
                    if in_tx is not None and getattr(in_tx, "text", None):
                        if self.last_role == "agent":
                            await self._flush_role("agent")
                        self.last_role = "user"
                        self.user_buf += in_tx.text
                        await self.send_json(
                            {"type": "user_delta", "text": self.user_buf}
                        )

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
                        if self.last_role == "user":
                            await self._flush_role("user")
                        elif self.last_role == "agent":
                            await self._flush_role("agent")
                        self.last_role = None

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
        except Exception:
            log.exception("gemini receive failed")
            await self.send_json({"type": "error", "detail": "Gemini stream failed"})
            self.stop_event.set()

    async def _flush_role(self, role: str) -> None:
        if role == "user" and self.user_buf:
            text = self.user_buf
            self.user_buf = ""
            await self.send_json({"type": "user_done", "text": text})
            await self._persist_turn(role="user", text=text)
        elif role == "agent" and self.agent_buf:
            text = self.agent_buf
            self.agent_buf = ""
            await self.send_json(
                {"type": "agent_done", "text": text, "tool_calls": []}
            )
            await self._persist_turn(role="model", text=text)

    async def _persist_turn(self, role: str, text: str) -> None:
        """Append a transcript turn to session.history (in memory).

        Persisted to DB on shutdown / disconnect via update_session()
        to keep WS-hot-path overhead low.
        """
        if self.db_session is None:
            return
        try:
            entry = {
                "role": role,
                "parts": [{"text": text}],
            }
            self.db_session.history.append(entry)
        except Exception:
            log.exception("persist_turn failed for role=%s", role)

    async def _dispatch_tool(
        self, name: str, args: dict[str, Any], call_id: str | None
    ) -> genai_types.FunctionResponse:
        """Dispatch via the state-gated agent_tools surface.

        Emits tool_call, tool_result, frontend_event (if any), and a
        session_snapshot frame after the dispatch so the frontend mirrors
        the new state.
        """
        await self.send_json(
            {"type": "tool_call", "name": name, "arguments": args}
        )

        if self.db_session is None or self.tool_ctx is None:
            output: dict[str, Any] = {"error": "session not initialized"}
        else:
            result = await dispatch(self.db_session, name, args, self.tool_ctx)
            if result.error is not None:
                output = {"error": result.error, "output": result.output}
            else:
                output = {"output": result.output}
            if result.frontend_event:
                await self.send_json(
                    {
                        "type": "frontend_event",
                        "event": result.frontend_event,
                    }
                )

        await self.send_json(
            {"type": "tool_result", "name": name, "output": output}
        )
        # Snapshot after every state-mutating dispatch.
        if self.db_session is not None:
            await self.send_json(
                {
                    "type": "session_snapshot",
                    "snapshot": self.db_session.snapshot(),
                }
            )

        return genai_types.FunctionResponse(
            id=call_id, name=name, response=output
        )


@router.websocket("/voice/ws")
async def voice_ws(ws: WebSocket) -> None:
    await ws.accept()
    session = VoiceBridgeSession(ws=ws)
    try:
        await session.run()
    except WebSocketDisconnect:
        log.info("client disconnected mid-session")
    except Exception:
        log.exception("voice bridge crashed")
        await session.send_json({"type": "error", "detail": "Bridge error"})
    finally:
        # Persist session state (history + state + active_doc) on shutdown
        # so a reconnect picks up where we left off.
        if session.db_session is not None:
            try:
                update_session(session.db_session)
            except Exception:
                log.exception("update_session failed on shutdown")
        try:
            await ws.close()
        except Exception:
            pass
