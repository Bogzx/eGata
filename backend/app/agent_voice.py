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
import time
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
    IllegalTransitionError,
    Session as DbSession,
    SessionState,
    fetch_or_create_session,
    session_lock,
    transition,
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
    # Counters for periodic audio-flow log — without this every frame would
    # log and drown the rest of the diagnostics. Flush every ~3s.
    audio_in_chunks: int = 0
    audio_in_bytes: int = 0
    audio_out_bytes: int = 0
    last_audio_log: float = 0.0

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
        log.info("voice_ws: awaiting start frame")
        try:
            self.start_payload = await self.wait_for_start()
            self.citizen_id = self._resolve_citizen(self.start_payload.token)
        except Exception as e:  # noqa: BLE001
            log.warning("voice_ws: start frame rejected: %s", e)
            await self.send_json({"type": "error", "detail": f"auth: {e}"})
            await self.ws.close(code=4401)
            return

        self.conv_id = (
            self.start_payload.conversation_id
            or f"conv_{secrets.token_urlsafe(8)}"
        )
        log.info(
            "voice_ws: auth ok citizen=%s conv=%s doc=%s simple=%s voice_only=%s",
            self.citizen_id,
            self.conv_id,
            self.start_payload.document_id,
            self.start_payload.simple_language,
            self.start_payload.voice_only,
        )

        # Hold the per-session lock for the lifetime of the voice call.
        # Prevents a concurrent text turn on the same conversation from
        # overwriting session.history while audio is in flight.
        async with session_lock(self.conv_id):
            await self._run_locked()

    async def _run_locked(self) -> None:
        """Body of run() that mutates session state — holds the lock."""
        assert self.start_payload is not None  # set by caller
        try:
            await self._run_inner()
        finally:
            # Persist inside the lock so a subsequent turn (text or voice
            # reconnect) waits for our final history write before it loads.
            if self.db_session is not None:
                try:
                    update_session(self.db_session)
                except Exception:
                    log.exception("update_session failed in _run_locked")

    async def _run_inner(self) -> None:
        assert self.start_payload is not None

        # Resolve or create the Session and pull citizen attributes.
        self.db_session = fetch_or_create_session(
            self.citizen_id, session_id=self.conv_id
        )
        if (
            self.start_payload.document_id
            and not self.db_session.active_document_id
        ):
            self.db_session.active_document_id = self.start_payload.document_id
            if self.db_session.state != SessionState.FILLING:
                try:
                    transition(self.db_session, SessionState.FILLING)
                except IllegalTransitionError:
                    log.warning(
                        "voice: illegal %s -> FILLING on doc-injection, "
                        "leaving state alone",
                        self.db_session.state.value,
                    )

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
        # Voice-only addendum: Gemini Live can't refresh system_instruction
        # mid-call, so we shipped state into every tool_response. Tell the
        # model where to find it.
        full_prompt += (
            "\n\n---\n"
            "Notă tehnică (voce): după fiecare apel de unealtă, răspunsul "
            "conține o cheie `_state` cu starea curentă a sesiunii: "
            "`state`, `permitted_tools`, `active_document_id`, și (dacă "
            "este deschis un document) `doc.fields` și `doc.missing_required`. "
            "Folosește această cheie pentru a ști ce câmpuri mai lipsesc și "
            "ce unelte poți chema acum — NU te baza pe instrucțiunea de "
            "sistem inițială, care nu se actualizează în timp ce vorbim."
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
        #
        # Two layered safeguards:
        #   1. Share the text-path's sanitizer so a half-written turn
        #      from text mode (orphan user/model turn from a crashed
        #      step) doesn't leak into the Live seed. Leftover user text
        #      is preserved and appended as a final user turn so the
        #      prior intent isn't lost.
        #   2. Filter to user-role turns only. Gemini Live's
        #      send_client_content rejects mixed-role replay with a 1007
        #      "invalid argument" close (see b81oxv9gs.txt: second voice
        #      WS, responses=0). User-only seeding is enough for the
        #      model to re-derive context.
        from app.session_engine import _sanitize_history_for_gemini

        sanitized_history, leftover_text = _sanitize_history_for_gemini(
            self.db_session.history
        )
        if len(sanitized_history) != len(self.db_session.history):
            log.warning(
                "voice: trimmed %d orphan turn(s) from prior failed step "
                "(leftover_user_text=%s)",
                len(self.db_session.history) - len(sanitized_history),
                "yes" if leftover_text else "no",
            )
            self.db_session.history = sanitized_history

        history: list[genai_types.Content] = []
        skipped_roles: list[str] = []
        for entry in sanitized_history:
            role = entry.get("role")
            if role != "user":
                skipped_roles.append(str(role))
                continue
            try:
                history.append(genai_types.Content.model_validate(entry))
            except Exception:
                log.exception(
                    "voice_ws: history entry rehydrate failed conv=%s entry=%r",
                    self.conv_id,
                    entry,
                )
        if skipped_roles:
            log.info(
                "voice_ws: history filtered conv=%s kept_user=%d skipped_roles=%s",
                self.conv_id,
                len(history),
                skipped_roles,
            )
        if leftover_text:
            history.append(
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text=leftover_text)],
                )
            )

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
                log.info(
                    "voice_ws: seeding gemini with history conv=%s turns=%d",
                    self.conv_id,
                    len(history),
                )
                try:
                    await gemini.send_client_content(
                        turns=history,
                        turn_complete=False,
                    )
                    log.info("voice_ws: history seed sent conv=%s", self.conv_id)
                except Exception:
                    log.exception(
                        "voice_ws: history seed failed conv=%s — continuing without",
                        self.conv_id,
                    )

            # Run all three pumps with a watchdog that cancels them the
            # moment stop_event fires. Without this, `session.receive()`
            # blocks waiting for Gemini events with no way to poll
            # stop_event — and when the client disconnects mid-call, the
            # gemini pump kept running for up to a minute (the byf5bkodh.txt
            # log showed 51 seconds), holding session_lock the whole time.
            # That made the NEXT voice attempt with the same conv_id hang
            # forever — exactly the "does not connect" symptom.
            pump_tasks = [
                asyncio.create_task(
                    self._pump_mic_to_gemini(gemini),
                    name="voice_ws.mic_pump",
                ),
                asyncio.create_task(
                    self._pump_gemini_to_client(gemini),
                    name="voice_ws.gemini_pump",
                ),
                asyncio.create_task(
                    self._pump_client_to_bridge(),
                    name="voice_ws.client_pump",
                ),
            ]

            async def _watchdog() -> None:
                await self.stop_event.wait()
                log.info(
                    "voice_ws: watchdog firing conv=%s — cancelling pumps",
                    self.conv_id,
                )
                for t in pump_tasks:
                    if not t.done():
                        t.cancel()

            watchdog_task = asyncio.create_task(
                _watchdog(), name="voice_ws.watchdog"
            )
            try:
                # return_exceptions=True so a CancelledError from one pump
                # doesn't short-circuit the gather and leave others orphan.
                await asyncio.gather(*pump_tasks, return_exceptions=True)
            finally:
                # Watchdog is either already done (it set stop_event) or
                # waiting; cancel it either way so this task tree drains.
                if not watchdog_task.done():
                    watchdog_task.cancel()
                    try:
                        await watchdog_task
                    except (asyncio.CancelledError, Exception):
                        pass

    def _maybe_log_audio_counters(self) -> None:
        """Emit a single line summarising audio flow every ~3 seconds.

        Without this we either log per-chunk (drowns the rest of the diags)
        or never (then we can't tell if the mic is even capturing).
        """
        now = time.perf_counter()
        if now - self.last_audio_log < 3.0:
            return
        if not (self.audio_in_chunks or self.audio_out_bytes):
            return
        log.info(
            "voice_ws: audio conv=%s in_chunks=%d in_bytes=%d out_bytes=%d",
            self.conv_id,
            self.audio_in_chunks,
            self.audio_in_bytes,
            self.audio_out_bytes,
        )
        self.audio_in_chunks = 0
        self.audio_in_bytes = 0
        self.audio_out_bytes = 0
        self.last_audio_log = now

    async def _pump_client_to_bridge(self) -> None:
        try:
            while not self.stop_event.is_set():
                msg = await self.ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    log.info("voice_ws: client disconnect conv=%s", self.conv_id)
                    self.stop_event.set()
                    break
                if msg.get("bytes") is not None:
                    chunk = msg["bytes"]
                    self.audio_in_chunks += 1
                    self.audio_in_bytes += len(chunk)
                    self._maybe_log_audio_counters()
                    try:
                        self.inbound_audio.put_nowait(chunk)
                    except asyncio.QueueFull:
                        log.warning(
                            "voice_ws: audio queue full conv=%s, dropping oldest",
                            self.conv_id,
                        )
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
                        log.warning(
                            "voice_ws: bad json text frame conv=%s: %r",
                            self.conv_id,
                            msg["text"][:200],
                        )
                        continue
                    ptype = payload.get("type")
                    if ptype == "text" and self.gemini is not None:
                        text = (payload.get("text") or "").strip()
                        if text:
                            log.info(
                                "voice_ws: text frame conv=%s text=%r",
                                self.conv_id,
                                text[:120],
                            )
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
                                log.exception(
                                    "voice_ws: send_client_content (text) failed conv=%s",
                                    self.conv_id,
                                )
                    elif ptype == "widget_submission" and self.gemini is not None:
                        widget_id = payload.get("widget_id")
                        value = payload.get("value")
                        if not isinstance(widget_id, str) or not widget_id:
                            log.warning(
                                "voice_ws: widget_submission missing widget_id conv=%s",
                                self.conv_id,
                            )
                            continue
                        log.info(
                            "voice_ws: widget_submission conv=%s widget=%s value=%r",
                            self.conv_id,
                            widget_id,
                            value,
                        )
                        await self._handle_widget_submission(widget_id, value)
                    elif ptype == "interrupt":
                        # v1 no-op; reserved for explicit barge-in UX.
                        log.debug("voice_ws: interrupt frame conv=%s", self.conv_id)
                        pass
                    else:
                        log.debug(
                            "voice_ws: unhandled frame conv=%s type=%r",
                            self.conv_id,
                            ptype,
                        )
        except WebSocketDisconnect:
            log.info("voice_ws: client WebSocketDisconnect conv=%s", self.conv_id)
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
                log.exception(
                    "voice_ws: send_realtime_input failed conv=%s",
                    self.conv_id,
                )
                self.stop_event.set()
                break
        log.info("voice_ws: mic pump stopped conv=%s", self.conv_id)

    async def _pump_gemini_to_client(self, session: Any) -> None:
        # Counters for diagnosing the voice loop. The b81oxv9gs.txt run
        # showed turns=1 + stop_event=False — confirming Gemini Live's
        # `session.receive()` yields events for ONE turn then ends naturally.
        # Without an outer while loop, voice wedges after the first
        # agent_done: audio keeps flowing in but nothing reads the responses,
        # and the session_lock stays held — which then blocks every future
        # chat turn on the same conv_id.
        response_count = 0
        turn_complete_count = 0
        interrupted_count = 0
        no_useful_count = 0
        iter_count = 0
        log.info(
            "voice_ws: gemini receive loop START conv=%s",
            self.conv_id,
        )
        try:
            while not self.stop_event.is_set():
                iter_count += 1
                iter_start_responses = response_count
                log.debug(
                    "voice_ws: entering receive() iter=%d conv=%s",
                    iter_count,
                    self.conv_id,
                )
                async for response in session.receive():
                    response_count += 1
                    if self.stop_event.is_set():
                        log.info(
                            "voice_ws: gemini loop break conv=%s reason=stop_event responses=%d",
                            self.conv_id,
                            response_count,
                        )
                        break

                    data = getattr(response, "data", None)
                    sc = getattr(response, "server_content", None)
                    tc = getattr(response, "tool_call", None)
                    log.debug(
                        "voice_ws: response conv=%s iter=%d #%d data_bytes=%d sc=%s tc=%s",
                        self.conv_id,
                        iter_count,
                        response_count,
                        len(data) if data else 0,
                        bool(sc),
                        bool(tc and getattr(tc, "function_calls", None)),
                    )
                    if not data and not sc and not (tc and getattr(tc, "function_calls", None)):
                        no_useful_count += 1
                    if data:
                        self.audio_out_bytes += len(data)
                        self._maybe_log_audio_counters()
                        await self.send_bytes(data)

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
                            interrupted_count += 1
                            log.info(
                                "voice_ws: server_content interrupted conv=%s count=%d responses=%d",
                                self.conv_id,
                                interrupted_count,
                                response_count,
                            )
                            await self.send_json({"type": "interrupted"})

                        if getattr(sc, "turn_complete", False):
                            turn_complete_count += 1
                            log.info(
                                "voice_ws: turn_complete conv=%s count=%d responses=%d last_role=%s",
                                self.conv_id,
                                turn_complete_count,
                                response_count,
                                self.last_role,
                            )
                            if self.last_role == "user":
                                await self._flush_role("user")
                            elif self.last_role == "agent":
                                await self._flush_role("agent")
                            self.last_role = None

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
                            log.exception(
                                "voice_ws: send_tool_response failed conv=%s",
                                self.conv_id,
                            )
                # Inner async-for ended (one turn complete in SDK terms).
                # Loop back into session.receive() for the next turn unless
                # we're shutting down.
                log.debug(
                    "voice_ws: receive() iter=%d done conv=%s iter_events=%d total=%d",
                    iter_count,
                    self.conv_id,
                    response_count - iter_start_responses,
                    response_count,
                )
        except Exception:
            log.exception(
                "voice_ws: gemini receive failed conv=%s after responses=%d turns=%d",
                self.conv_id,
                response_count,
                turn_complete_count,
            )
            await self.send_json({"type": "error", "detail": "Gemini stream failed"})
            self.stop_event.set()
        finally:
            log.info(
                "voice_ws: gemini receive loop EXITED conv=%s iters=%d responses=%d turns=%d interrupted=%d empty=%d stop_event=%s",
                self.conv_id,
                iter_count,
                response_count,
                turn_complete_count,
                interrupted_count,
                no_useful_count,
                self.stop_event.is_set(),
            )
            # If the iterator ended on its own (not from stop_event), signal
            # the other pumps to wind down. Then close the WS to unblock
            # _pump_client_to_bridge's `await self.ws.receive()` — without
            # this it sits forever, the gather() never returns, the
            # session_lock never releases, and every subsequent chat turn on
            # the same conv_id deadlocks at `async with session_lock(...)`.
            # That was the "chat also broken" symptom in b81oxv9gs.txt.
            tearing_down = not self.stop_event.is_set()
            if tearing_down:
                log.warning(
                    "voice_ws: gemini loop ended without stop_event conv=%s — tearing down bridge",
                    self.conv_id,
                )
                self.stop_event.set()
                try:
                    await self.send_json(
                        {"type": "error", "detail": "Gemini stream ended unexpectedly"}
                    )
                except Exception:
                    pass
            try:
                # Closing the WS here is what releases _pump_client_to_bridge
                # from its blocking ws.receive() call so gather() can return.
                await self.ws.close(code=1011 if tearing_down else 1000)
            except Exception:
                # Already closed (client disconnect arrived first) or in a
                # closing state — both fine.
                pass

    async def _flush_role(self, role: str) -> None:
        if role == "user" and self.user_buf:
            text = self.user_buf
            self.user_buf = ""
            log.info(
                "voice_ws: user_done conv=%s text=%r",
                self.conv_id,
                text[:200],
            )
            await self.send_json({"type": "user_done", "text": text})
            await self._persist_turn(role="user", text=text)
        elif role == "agent" and self.agent_buf:
            text = self.agent_buf
            self.agent_buf = ""
            log.info(
                "voice_ws: agent_done conv=%s text=%r",
                self.conv_id,
                text[:200],
            )
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

    def _state_recap(self) -> dict[str, Any]:
        """Snapshot of session state to embed in every tool_response.

        Gemini Live freezes system_instruction at connect time, so the
        model's "Stare sesiune / Tool-uri permise / Câmpuri obligatorii"
        preamble grows stale the moment a tool fires. We sneak the fresh
        state into every function_response under a `_state` key so the
        model has a current view without rebuilding the system prompt.
        """
        if self.db_session is None:
            return {}
        recap: dict[str, Any] = {
            "state": self.db_session.state.value,
            "permitted_tools": permitted_tools(self.db_session.state),
            "active_document_id": self.db_session.active_document_id,
        }
        doc_id = self.db_session.active_document_id
        if not doc_id:
            return recap
        try:
            from app.documents import fetch_document
            from app.procedures import get_registry
            from app.procedure_state import evaluate_field_states

            doc = fetch_document(UUID(doc_id))
            fields = doc.get("fields") or {}
            reg = get_registry()
            proc = reg.get(doc["procedure_id"])
            recap["doc"] = {
                "procedure_id": doc["procedure_id"],
                "status": doc.get("status"),
                "fields": fields,
            }
            if proc:
                citizen_attrs = (
                    self.tool_ctx.citizen_attributes if self.tool_ctx else {}
                )
                states = evaluate_field_states(proc, fields, citizen_attrs)
                recap["doc"]["missing_required"] = states.missing
        except Exception:
            log.exception("state_recap doc lookup failed")
        return recap

    async def _handle_widget_submission(
        self, widget_id: str, value: Any
    ) -> None:
        """Resolve a widget click during an active Live session.

        Mirrors `agent.widget_result` (the HTTP path used in text-only mode)
        but injects the result into Gemini Live's in-session context via
        `send_client_content`, so the model knows the field was answered
        without us having to re-seed history or end the session.

        Two paths, like the HTTP endpoint:
        * widget has `target_field` → dispatch set_field locally, then send
          a synthetic system note to Live with turn_complete=False (the
          model absorbs the context but doesn't respond — UI already shows
          the field updated).
        * widget has no target_field (confirm in confirming_match) → forward
          the user's choice as a real turn (turn_complete=True) so the
          model picks the next action (start_procedure, abandon, etc.).
        """
        if self.db_session is None or self.tool_ctx is None or self.gemini is None:
            return

        widget = self.db_session.resolve_pending_widget(widget_id)
        if widget is None:
            await self.send_json(
                {
                    "type": "error",
                    "detail": (
                        f"Widget {widget_id!r} nu este în așteptare "
                        f"(deja rezolvat?)"
                    ),
                }
            )
            return

        # Reuse the same Da/Nu/true/false coercion as the HTTP endpoint.
        from app.agent import _coerce_widget_value

        user_visible = str(value) if not isinstance(value, str) else value

        if widget.target_field:
            coerced = _coerce_widget_value(value, widget.type)
            # _dispatch_tool emits tool_call / frontend_event / tool_result /
            # session_snapshot for us. The FunctionResponse return value is
            # for replying to Gemini-initiated calls — discard it here because
            # this call was initiated by the user clicking a widget.
            await self._dispatch_tool(
                name="set_field",
                args={"name": widget.target_field, "value": coerced},
                call_id=None,
            )

            synthetic_text = (
                f"[Sistem: cetățeanul a răspuns widget-ului pentru câmpul "
                f"'{widget.target_field}' cu valoarea: {user_visible}. "
                f"Câmpul a fost setat automat — NU mai apela set_field "
                f"pentru acest câmp. Continuă conversația sau întreabă "
                f"următorul câmp lipsă.]"
            )
            try:
                await self.gemini.send_client_content(
                    turns=[
                        genai_types.Content(
                            role="user",
                            parts=[
                                genai_types.Part.from_text(text=synthetic_text)
                            ],
                        )
                    ],
                    turn_complete=False,
                )
            except Exception:
                log.exception(
                    "send_client_content for widget update failed"
                )

            # Persist into session.history so a reconnect re-seeds the
            # same synthetic context the live session just absorbed.
            self.db_session.history.append(
                {"role": "user", "parts": [{"text": synthetic_text}]}
            )
            return

        # No target_field: the answer IS the user's turn. Forward to Live
        # with turn_complete=True so the model produces a response.
        prompt = f"[Răspuns widget: {user_visible}]"
        try:
            await self.gemini.send_client_content(
                turns=[
                    genai_types.Content(
                        role="user",
                        parts=[genai_types.Part.from_text(text=prompt)],
                    )
                ],
                turn_complete=True,
            )
        except Exception:
            log.exception("send_client_content for widget followup failed")

        self.db_session.history.append(
            {"role": "user", "parts": [{"text": prompt}]}
        )

        # Snapshot so frontend sees pending_widgets shrink.
        await self.send_json(
            {
                "type": "session_snapshot",
                "snapshot": self.db_session.snapshot(),
            }
        )

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

        # Embed fresh state recap in every response — see _state_recap.
        output["_state"] = self._state_recap()

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
    client = f"{ws.client.host}:{ws.client.port}" if ws.client else "-"
    log.info("voice_ws: accept from=%s", client)
    await ws.accept()
    session = VoiceBridgeSession(ws=ws)
    started = time.perf_counter()
    try:
        await session.run()
    except WebSocketDisconnect:
        log.info(
            "voice_ws: disconnected mid-session conv=%s",
            session.conv_id or "-",
        )
    except Exception:
        log.exception(
            "voice_ws: bridge crashed conv=%s",
            session.conv_id or "-",
        )
        await session.send_json({"type": "error", "detail": "Bridge error"})
    finally:
        log.info(
            "voice_ws: close conv=%s duration_s=%.1f from=%s",
            session.conv_id or "-",
            time.perf_counter() - started,
            client,
        )
        # Persistence happens inside _run_locked (under session_lock); the
        # finally here only closes the socket.
        try:
            await ws.close()
        except Exception:
            pass
