"""Browser ↔ Azure VoiceLive WebSocket bridge.

The browser sends PCM16 mono 16 kHz audio over a WebSocket; the backend
resamples to 24 kHz, forwards to Azure VoiceLive via the SDK, relays
agent audio back at 24 kHz (frontend's playback rate), surfaces live
transcripts as JSON control frames, and dispatches tool-calls in-process
against app.agent_tools.REGISTRY.

The `start` frame carries a `token` field (same Bearer JWT used for
HTTP) because browsers cannot set Authorization headers on a WebSocket
upgrade.

Direct-model mode (no Foundry agent): we own the system_instruction +
tool declarations client-side and pass them via RequestSession at
session.update time.
"""
from __future__ import annotations

import asyncio
import audioop
import base64
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from azure.ai.voicelive.aio import connect as voicelive_connect
from azure.ai.voicelive.models import (
    AudioEchoCancellation,
    AudioInputTranscriptionOptions,
    AudioNoiseReduction,
    AzureSemanticVadMultilingual,
    AzureStandardVoice,
    FunctionCallOutputItem,
    InputAudioFormat,
    InputTextContentPart,
    MessageItem,
    Modality,
    OutputAudioFormat,
    RequestSession,
    ServerEventType,
)

from app.agent_tools import REGISTRY as TOOLS_REGISTRY, ToolContext, dispatch, permitted_tools
from app.azure_clients import (
    get_voicelive_credential,
    history_to_user_only_texts,
    tools_for_realtime,
)
from app.citizens import fetch_citizen_by_id
from app.config import get_settings
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

if TYPE_CHECKING:
    from azure.ai.voicelive.aio import VoiceLiveConnection

router = APIRouter(prefix="/agent", tags=["voice"])
log = logging.getLogger("agent_voice")


# Frontend audio worklet config (see frontend/lib/audioWorklet.ts):
#   recorder sampleRate = 16000
#   player   sampleRate = 24000
# Azure VoiceLive PCM16 is 24 kHz both directions. So we resample input
# 16k→24k, and pass output 24k through unchanged.
_BROWSER_INPUT_RATE = 16000
_AZURE_PCM_RATE = 24000


def _browser_function_declarations() -> list[dict[str, Any]]:
    """Single source of truth: agent_tools REGISTRY.

    VoiceLive locks tools at session.update time, so we send all
    declarations. The dispatcher refuses out-of-state calls — the model
    gets an error result it can apologize about, rather than a
    permitted-tools list that changes mid-session.
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
class _PendingToolCall:
    call_id: str
    name: str
    args_buf: str = ""


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
    voicelive: Any = None  # VoiceLiveConnection
    user_buf: str = ""
    agent_buf: str = ""
    last_role: str | None = None
    pending_tool_calls: dict[str, _PendingToolCall] = field(default_factory=dict)
    response_active: bool = False
    response_done: bool = True
    # Resampler state — persisting it across chunks avoids click artifacts
    # at chunk boundaries (audioop.ratecv with state=None resets every call).
    resample_state: Any = None
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

        async with session_lock(self.conv_id):
            await self._run_locked()

    async def _run_locked(self) -> None:
        assert self.start_payload is not None
        try:
            await self._run_inner()
        finally:
            if self.db_session is not None:
                try:
                    update_session(self.db_session)
                except Exception:
                    log.exception("update_session failed in _run_locked")

    async def _run_inner(self) -> None:
        assert self.start_payload is not None

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

        from app.session_engine import build_system_instruction

        full_prompt = build_system_instruction(
            self.db_session,
            citizen_attrs,
            simple_language=self.start_payload.simple_language,
            voice_only=self.start_payload.voice_only,
        )
        # Realtime APIs lock instructions at session.update time. Subsequent
        # state context lives in tool responses via the `_state` recap so
        # the model has a fresh view without us re-pushing instructions.
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

        # Build the session configuration. RequestSession is a TypedDict
        # in the SDK; pass tools+instructions+voice all at once.
        voice = AzureStandardVoice(name=settings.azure_voicelive_voice)
        session_config = RequestSession(
            modalities=[Modality.TEXT, Modality.AUDIO],
            instructions=full_prompt,
            voice=voice,
            input_audio_format=InputAudioFormat.PCM16,
            output_audio_format=OutputAudioFormat.PCM16,
            # Typed config with Romanian language hint — the speech-to-text
            # event (CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED)
            # only fires when transcription is explicitly enabled, and the
            # language hint is needed for `whisper-1` to land on Romanian
            # tokens instead of guessing English.
            input_audio_transcription=AudioInputTranscriptionOptions(
                model="whisper-1",
                language="ro",
            ),
            turn_detection=AzureSemanticVadMultilingual(),
            input_audio_echo_cancellation=AudioEchoCancellation(),
            input_audio_noise_reduction=AudioNoiseReduction(
                type="azure_deep_noise_suppression"
            ),
            tools=tools_for_realtime(_browser_function_declarations()),
            tool_choice="auto",
        )

        history_texts = history_to_user_only_texts(self.db_session.history)

        log.info(
            "voicelive: connecting endpoint=%s model=%s voice=%s conv=%s",
            settings.azure_voicelive_endpoint,
            settings.azure_voicelive_model,
            settings.azure_voicelive_voice,
            self.conv_id,
        )

        async with voicelive_connect(
            endpoint=settings.azure_voicelive_endpoint,
            credential=get_voicelive_credential(),
            api_version=settings.azure_voicelive_api_version,
            model=settings.azure_voicelive_model,
        ) as connection:
            self.voicelive = connection
            await connection.session.update(session=session_config)

            await self.send_json({"type": "ready", "conversation_id": self.conv_id})
            await self.send_json(
                {"type": "session_snapshot", "snapshot": self.db_session.snapshot()}
            )
            log.info(
                "voice bridge ready conv=%s citizen=%s doc=%s state=%s history_turns=%d",
                self.conv_id,
                self.citizen_id,
                self.db_session.active_document_id,
                self.db_session.state.value,
                len(history_texts),
            )

            # Seed prior user-turn text so the model has context. Items
            # arrive in order; we don't trigger response.create here — the
            # model just absorbs them.
            for txt in history_texts:
                try:
                    await connection.conversation.item.create(
                        item=MessageItem(
                            role="user",
                            content=[InputTextContentPart(text=txt)],
                        )
                    )
                except Exception:
                    log.exception(
                        "voice_ws: history seed item failed conv=%s",
                        self.conv_id,
                    )

            pump_tasks = [
                asyncio.create_task(
                    self._pump_mic_to_voicelive(connection),
                    name="voice_ws.mic_pump",
                ),
                asyncio.create_task(
                    self._pump_voicelive_to_client(connection),
                    name="voice_ws.voicelive_pump",
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
                await asyncio.gather(*pump_tasks, return_exceptions=True)
            finally:
                if not watchdog_task.done():
                    watchdog_task.cancel()
                    try:
                        await watchdog_task
                    except (asyncio.CancelledError, Exception):
                        pass

    def _maybe_log_audio_counters(self) -> None:
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

    def _resample_16k_to_24k(self, pcm16k: bytes) -> bytes:
        """Browser 16kHz PCM16 → Azure 24kHz PCM16, state-preserving."""
        out, self.resample_state = audioop.ratecv(
            pcm16k, 2, 1, _BROWSER_INPUT_RATE, _AZURE_PCM_RATE, self.resample_state
        )
        return out

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
                    if ptype == "text" and self.voicelive is not None:
                        text = (payload.get("text") or "").strip()
                        if text:
                            log.info(
                                "voice_ws: text frame conv=%s text=%r",
                                self.conv_id,
                                text[:120],
                            )
                            try:
                                await self.voicelive.conversation.item.create(
                                    item=MessageItem(
                                        role="user",
                                        content=[InputTextContentPart(text=text)],
                                    )
                                )
                                await self.voicelive.response.create()
                            except Exception:
                                log.exception(
                                    "voice_ws: text item.create failed conv=%s",
                                    self.conv_id,
                                )
                    elif ptype == "widget_submission" and self.voicelive is not None:
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
                        log.debug("voice_ws: interrupt frame conv=%s", self.conv_id)
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

    async def _pump_mic_to_voicelive(self, connection: Any) -> None:
        while not self.stop_event.is_set():
            pcm16k = await self.inbound_audio.get()
            if pcm16k is None:
                break
            try:
                pcm24k = self._resample_16k_to_24k(pcm16k)
                b64 = base64.b64encode(pcm24k).decode("ascii")
                await connection.input_audio_buffer.append(audio=b64)
            except Exception:
                log.exception(
                    "voice_ws: input_audio_buffer.append failed conv=%s",
                    self.conv_id,
                )
                self.stop_event.set()
                break
        log.info("voice_ws: mic pump stopped conv=%s", self.conv_id)

    async def _pump_voicelive_to_client(self, connection: Any) -> None:
        event_count = 0
        log.info("voice_ws: voicelive receive loop START conv=%s", self.conv_id)
        try:
            async for event in connection:
                event_count += 1
                if self.stop_event.is_set():
                    log.info(
                        "voice_ws: voicelive loop break conv=%s reason=stop_event events=%d",
                        self.conv_id,
                        event_count,
                    )
                    break
                await self._handle_voicelive_event(event, connection)
        except Exception:
            log.exception(
                "voice_ws: voicelive receive failed conv=%s after events=%d",
                self.conv_id,
                event_count,
            )
            await self.send_json({"type": "error", "detail": "VoiceLive stream failed"})
            self.stop_event.set()
        finally:
            log.info(
                "voice_ws: voicelive receive loop EXITED conv=%s events=%d stop_event=%s",
                self.conv_id,
                event_count,
                self.stop_event.is_set(),
            )
            tearing_down = not self.stop_event.is_set()
            if tearing_down:
                log.warning(
                    "voice_ws: voicelive loop ended without stop_event conv=%s — tearing down bridge",
                    self.conv_id,
                )
                self.stop_event.set()
                try:
                    await self.send_json(
                        {"type": "error", "detail": "VoiceLive stream ended unexpectedly"}
                    )
                except Exception:
                    pass
            try:
                await self.ws.close(code=1011 if tearing_down else 1000)
            except Exception:
                pass

    async def _handle_voicelive_event(self, event: Any, connection: Any) -> None:
        et = getattr(event, "type", None)

        if et == ServerEventType.SESSION_UPDATED:
            log.info("voice_ws: session ready conv=%s", self.conv_id)
            return

        if et == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED:
            log.info("voice_ws: user started speaking conv=%s", self.conv_id)
            if self.response_active and not self.response_done:
                try:
                    await connection.response.cancel()
                    log.debug("voice_ws: cancelled in-progress response (barge-in)")
                except Exception as e:  # noqa: BLE001
                    if "no active response" not in str(e).lower():
                        log.warning("voice_ws: response.cancel failed: %s", e)
            await self.send_json({"type": "interrupted"})
            return

        if et == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED:
            log.debug("voice_ws: user stopped speaking conv=%s", self.conv_id)
            return

        if et == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_DELTA:
            # Incremental user transcript while they're still speaking.
            delta = getattr(event, "delta", "") or ""
            if delta:
                if self.last_role == "agent":
                    await self._flush_role("agent")
                self.last_role = "user"
                self.user_buf += delta
                await self.send_json({"type": "user_delta", "text": self.user_buf})
            return

        if et == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
            text = getattr(event, "transcript", "") or ""
            if text:
                if self.last_role == "agent":
                    await self._flush_role("agent")
                self.last_role = "user"
                # Prefer the final transcript over whatever delta accumulated
                # — the server's final pass may correct mid-utterance guesses.
                self.user_buf = text
                await self.send_json({"type": "user_delta", "text": self.user_buf})
                await self._flush_role("user")
            return

        if et == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_FAILED:
            err = getattr(event, "error", None)
            msg = getattr(err, "message", None) or "transcription failed"
            log.warning(
                "voice_ws: transcription failed conv=%s: %s",
                self.conv_id,
                msg,
            )
            return

        if et == ServerEventType.RESPONSE_CREATED:
            self.response_active = True
            self.response_done = False
            return

        if et == ServerEventType.RESPONSE_AUDIO_DELTA:
            # delta is base64 PCM16 @ 24kHz — frontend plays at 24kHz, pass through
            delta = getattr(event, "delta", None)
            if delta:
                try:
                    pcm = (
                        base64.b64decode(delta)
                        if isinstance(delta, str)
                        else bytes(delta)
                    )
                    self.audio_out_bytes += len(pcm)
                    self._maybe_log_audio_counters()
                    await self.send_bytes(pcm)
                except Exception:
                    log.exception("voice_ws: audio delta decode/send failed")
            return

        if et == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA:
            delta = getattr(event, "delta", "") or ""
            if delta:
                if self.last_role == "user":
                    await self._flush_role("user")
                self.last_role = "agent"
                self.agent_buf += delta
                await self.send_json({"type": "agent_delta", "text": self.agent_buf})
            return

        if et == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DONE:
            transcript = getattr(event, "transcript", None)
            if transcript and not self.agent_buf:
                self.agent_buf = transcript
            if self.agent_buf:
                if self.last_role == "user":
                    await self._flush_role("user")
                self.last_role = "agent"
            return

        if et == ServerEventType.RESPONSE_AUDIO_DONE:
            log.debug("voice_ws: response audio done conv=%s", self.conv_id)
            return

        # Tool call streaming
        if et == ServerEventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA:
            call_id = getattr(event, "call_id", None) or ""
            delta = getattr(event, "delta", "") or ""
            if not call_id:
                return
            slot = self.pending_tool_calls.get(call_id)
            if slot is None:
                slot = _PendingToolCall(
                    call_id=call_id,
                    name=getattr(event, "name", "") or "",
                )
                self.pending_tool_calls[call_id] = slot
            slot.args_buf += delta
            return

        if et == ServerEventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE:
            call_id = getattr(event, "call_id", None) or ""
            slot = self.pending_tool_calls.pop(call_id, None)
            name = (
                (slot.name if slot else "")
                or getattr(event, "name", "")
                or ""
            )
            args_buf = (slot.args_buf if slot else "") or getattr(event, "arguments", "") or ""
            try:
                args = json.loads(args_buf) if args_buf else {}
            except json.JSONDecodeError:
                args = {}
                log.warning(
                    "voice_ws: tool args not valid json conv=%s name=%s raw=%r",
                    self.conv_id,
                    name,
                    args_buf[:200],
                )
            await self._dispatch_tool_and_respond(
                connection, name=name, args=args, call_id=call_id
            )
            return

        if et == ServerEventType.RESPONSE_DONE:
            self.response_active = False
            self.response_done = True
            if self.last_role == "agent":
                await self._flush_role("agent")
            self.last_role = None
            return

        if et == ServerEventType.ERROR:
            err = getattr(event, "error", None)
            msg = (
                getattr(err, "message", None)
                if err is not None
                else str(event)
            ) or "unknown"
            if "no active response" in msg.lower():
                log.debug("voice_ws: benign cancel error conv=%s: %s", self.conv_id, msg)
                return
            log.error("voice_ws: voicelive error conv=%s: %s", self.conv_id, msg)
            await self.send_json({"type": "error", "detail": msg})
            return

        # Anything else is logged at debug; covers
        # CONVERSATION_ITEM_CREATED, INPUT_AUDIO_BUFFER_COMMITTED, etc.
        log.debug("voice_ws: unhandled event conv=%s type=%r", self.conv_id, et)

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
            await self.send_json({"type": "agent_done", "text": text, "tool_calls": []})
            await self._persist_turn(role="assistant", text=text)

    async def _persist_turn(self, role: str, text: str) -> None:
        """Append a transcript turn to session.history in OpenAI message shape."""
        if self.db_session is None:
            return
        try:
            entry = {"role": role, "content": text}
            self.db_session.history.append(entry)
        except Exception:
            log.exception("persist_turn failed for role=%s", role)

    def _state_recap(self) -> dict[str, Any]:
        """Snapshot of session state to embed in every tool_response.

        Realtime instructions are frozen at session.update time, so we
        sneak the fresh state into every function response under a
        `_state` key so the model has a current view without rebuilding
        the system prompt.
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
        if self.db_session is None or self.tool_ctx is None or self.voicelive is None:
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

        from app.agent import _coerce_widget_value

        user_visible = str(value) if not isinstance(value, str) else value

        # Only dispatch set_field when there's a document to write into.
        # A pre-fix widget may have been created with target_field while
        # the session was in CONFIRMING_MATCH; treat its submission as a
        # text answer instead of crashing on the state-gate.
        can_set_field = (
            widget.target_field is not None
            and self.db_session.state
            in {SessionState.FILLING, SessionState.REVIEWING}
        )
        if can_set_field:
            coerced = _coerce_widget_value(value, widget.type)
            await self._dispatch_tool_and_emit(
                name="set_field",
                args={"name": widget.target_field, "value": coerced},
            )

            synthetic_text = (
                f"[Sistem: cetățeanul a răspuns widget-ului pentru câmpul "
                f"'{widget.target_field}' cu valoarea: {user_visible}. "
                f"Câmpul a fost setat automat — NU mai apela set_field "
                f"pentru acest câmp. Continuă conversația sau întreabă "
                f"următorul câmp lipsă.]"
            )
            try:
                await self.voicelive.conversation.item.create(
                    item=MessageItem(
                        role="user",
                        content=[InputTextContentPart(text=synthetic_text)],
                    )
                )
                # No response.create — UI already shows the update; let
                # the user speak next.
            except Exception:
                log.exception("voicelive: widget update item failed")

            self.db_session.history.append(
                {"role": "user", "content": synthetic_text}
            )
            return

        # No target_field: forward as the user's turn, model decides next.
        prompt = f"[Răspuns widget: {user_visible}]"
        try:
            await self.voicelive.conversation.item.create(
                item=MessageItem(
                    role="user",
                    content=[InputTextContentPart(text=prompt)],
                )
            )
            await self.voicelive.response.create()
        except Exception:
            log.exception("voicelive: widget followup item failed")

        self.db_session.history.append({"role": "user", "content": prompt})

        await self.send_json(
            {
                "type": "session_snapshot",
                "snapshot": self.db_session.snapshot(),
            }
        )

    async def _dispatch_tool_and_emit(
        self, name: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Run a tool locally + emit the JSON frames; return the output dict.

        Used by widget-submission path. The result dict is identical to
        what we'd send back over VoiceLive's function_call_output.
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
                    {"type": "frontend_event", "event": result.frontend_event}
                )

        output["_state"] = self._state_recap()
        await self.send_json(
            {"type": "tool_result", "name": name, "output": output}
        )
        if self.db_session is not None:
            await self.send_json(
                {
                    "type": "session_snapshot",
                    "snapshot": self.db_session.snapshot(),
                }
            )
        return output

    async def _dispatch_tool_and_respond(
        self,
        connection: Any,
        *,
        name: str,
        args: dict[str, Any],
        call_id: str,
    ) -> None:
        """Run a tool, send the function_call_output back, trigger response."""
        output = await self._dispatch_tool_and_emit(name=name, args=args)
        try:
            await connection.conversation.item.create(
                item=FunctionCallOutputItem(
                    call_id=call_id,
                    output=json.dumps(output, ensure_ascii=False),
                )
            )
            await connection.response.create()
        except Exception:
            log.exception(
                "voice_ws: function_call_output failed conv=%s call_id=%s",
                self.conv_id,
                call_id,
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
        try:
            await ws.close()
        except Exception:
            pass
