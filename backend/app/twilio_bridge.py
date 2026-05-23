"""Twilio Media Streams ↔ Gemini Live bridge for phone calls.

Twilio sends 8 kHz mono μ-law in JSON envelopes over WebSocket. We transcode
to/from PCM16 (16 kHz in, 24 kHz out) and proxy to a Gemini Live session
configured with the phone system prompt and a restricted tool allowlist
(RAG-only — no document writes from phone).

Twilio Media Streams events handled:
    {"event": "connected", ...}
    {"event": "start", "streamSid": "...", "start": {...}}
    {"event": "media", "media": {"payload": "<base64 mulaw>"}}
    {"event": "stop", ...}
"""
from __future__ import annotations

import asyncio
import audioop
import base64
import json
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


def _phone_session_id() -> str:
    return secrets.token_urlsafe(8)

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types as genai_types

from app.agent_tools import ToolContext, dispatch
from app.config import get_settings
from app.prompts import build_system_prompt
from app.sessions import Session, SessionState

router = APIRouter(tags=["twilio"])
log = logging.getLogger("twilio_bridge")


PHONE_TOOL_ALLOWLIST: set[str] = {"lookup_procedure", "find_redirect"}


# ---- Audio codec helpers ----


def mulaw_to_pcm16_16k(mulaw_bytes: bytes) -> bytes:
    """8 kHz μ-law → 16 kHz PCM16 mono."""
    pcm8k = audioop.ulaw2lin(mulaw_bytes, 2)
    pcm16k, _ = audioop.ratecv(pcm8k, 2, 1, 8000, 16000, None)
    return pcm16k


def pcm16_24k_to_mulaw_8k(pcm24k_bytes: bytes) -> bytes:
    """24 kHz PCM16 → 8 kHz μ-law for Twilio."""
    pcm8k, _ = audioop.ratecv(pcm24k_bytes, 2, 1, 24000, 8000, None)
    return audioop.lin2ulaw(pcm8k, 2)


# ---- Twilio frame parsing ----


@dataclass
class TwilioFrame:
    event: str
    stream_sid: str | None
    audio_mulaw: bytes | None


def parse_twilio_frame(msg: dict[str, Any]) -> TwilioFrame:
    event = msg.get("event", "unknown")
    stream_sid = msg.get("streamSid")
    audio: bytes | None = None
    if event == "media":
        payload = (msg.get("media") or {}).get("payload")
        if payload:
            audio = base64.b64decode(payload)
    return TwilioFrame(event=event, stream_sid=stream_sid, audio_mulaw=audio)


# ---- Phone Gemini Live session ----


_PHONE_FUNCTION_DECLS: list[dict[str, Any]] = [
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
        "name": "find_redirect",
        "description": "Decide dacă cererea este în afara primăriei.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING"},
                "target": {"type": "STRING"},
            },
            "required": ["query"],
        },
    },
]


async def _run_phone_gemini_session(
    inbound: asyncio.Queue[bytes | None],
    send_to_twilio: Callable[[bytes], Awaitable[None]],
    stop_event: asyncio.Event,
) -> None:
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)

    # Phone agent runs an ephemeral in-memory Session in EXPLORING — no
    # document creation, no persistence, no DB writes. Tool dispatch goes
    # through the unified agent_tools.dispatch with a phone allowlist
    # layered on top of state-gating.
    phone_session = Session(
        id=f"phone_{_phone_session_id()}",
        citizen_id="phone-anonymous",
        state=SessionState.EXPLORING,
    )
    phone_ctx = ToolContext(
        citizen_id="phone-anonymous",
        citizen_attributes={},
    )

    config = genai_types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=build_system_prompt(variant="phone"),
        tools=[{"function_declarations": _PHONE_FUNCTION_DECLS}],
        speech_config=genai_types.SpeechConfig(
            voice_config=genai_types.VoiceConfig(
                prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                    voice_name=settings.gemini_voice_name,
                )
            ),
            language_code="ro-RO",
        ),
    )

    log.info(
        "twilio_gemini: connecting model=%s voice=%s lang=ro-RO session=%s",
        settings.gemini_voice_model,
        settings.gemini_voice_name,
        phone_session.id,
    )
    async with client.aio.live.connect(
        model=settings.gemini_voice_model, config=config
    ) as session:
        log.info("twilio_gemini: connected session=%s", phone_session.id)

        async def pump_inbound() -> None:
            while not stop_event.is_set():
                pcm = await inbound.get()
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
                        "twilio_gemini: send_realtime_input failed session=%s",
                        phone_session.id,
                    )
                    break
            log.info("twilio_gemini: inbound pump stopped session=%s", phone_session.id)

        async def pump_outbound() -> None:
            async for response in session.receive():
                if getattr(response, "data", None):
                    try:
                        mulaw = pcm16_24k_to_mulaw_8k(response.data)
                        await send_to_twilio(mulaw)
                    except Exception:
                        log.exception(
                            "twilio_gemini: audio out failed session=%s",
                            phone_session.id,
                        )
                tc = getattr(response, "tool_call", None)
                if tc and getattr(tc, "function_calls", None):
                    fr_parts: list[genai_types.FunctionResponse] = []
                    for fc in tc.function_calls:
                        call_id = getattr(fc, "id", None)
                        if fc.name not in PHONE_TOOL_ALLOWLIST:
                            log.warning(
                                "twilio_gemini: phone tried disallowed tool=%s session=%s",
                                fc.name,
                                phone_session.id,
                            )
                            fr_parts.append(
                                genai_types.FunctionResponse(
                                    id=call_id,
                                    name=fc.name,
                                    response={"error": "tool_not_available_on_phone"},
                                )
                            )
                            continue
                        args = dict(fc.args) if fc.args else {}
                        log.info(
                            "twilio_gemini: tool_call session=%s name=%s args=%r",
                            phone_session.id,
                            fc.name,
                            args,
                        )
                        result = await dispatch(
                            phone_session, fc.name, args, phone_ctx
                        )
                        if result.error is not None:
                            response_obj = {
                                "error": result.error,
                                "output": result.output,
                            }
                        else:
                            response_obj = {"output": result.output}
                        fr_parts.append(
                            genai_types.FunctionResponse(
                                id=call_id, name=fc.name, response=response_obj
                            )
                        )
                    try:
                        await session.send_tool_response(function_responses=fr_parts)
                    except Exception:
                        log.exception(
                            "twilio_gemini: send_tool_response failed session=%s",
                            phone_session.id,
                        )
                sc = getattr(response, "server_content", None)
                if sc and getattr(sc, "interrupted", False):
                    log.info(
                        "twilio_gemini: barge-in (interrupted) session=%s",
                        phone_session.id,
                    )
            log.info("twilio_gemini: outbound pump stopped session=%s", phone_session.id)

        await asyncio.gather(pump_inbound(), pump_outbound())


# ---- WebSocket endpoint ----


@router.websocket("/voice/twilio")
async def twilio_media_stream(ws: WebSocket) -> None:
    client = f"{ws.client.host}:{ws.client.port}" if ws.client else "-"
    log.info("twilio_ws: accept from=%s", client)
    await ws.accept()

    inbound: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=200)
    stop_event = asyncio.Event()
    stream_sid_holder: dict[str, str] = {}
    # Counters flushed every ~3s so we can see whether mulaw frames are
    # actually arriving without a per-frame log line drowning everything.
    counters = {"in_frames": 0, "in_bytes": 0, "out_frames": 0, "out_bytes": 0}
    last_log = [time.perf_counter()]

    def maybe_log_counters() -> None:
        now = time.perf_counter()
        if now - last_log[0] < 3.0:
            return
        if not any(counters.values()):
            return
        log.info(
            "twilio_ws: audio sid=%s in_frames=%d in_bytes=%d out_frames=%d out_bytes=%d",
            stream_sid_holder.get("sid", "-"),
            counters["in_frames"],
            counters["in_bytes"],
            counters["out_frames"],
            counters["out_bytes"],
        )
        counters["in_frames"] = 0
        counters["in_bytes"] = 0
        counters["out_frames"] = 0
        counters["out_bytes"] = 0
        last_log[0] = now

    async def send_to_twilio(mulaw_bytes: bytes) -> None:
        sid = stream_sid_holder.get("sid")
        if not sid:
            return
        counters["out_frames"] += 1
        counters["out_bytes"] += len(mulaw_bytes)
        maybe_log_counters()
        try:
            await ws.send_text(
                json.dumps(
                    {
                        "event": "media",
                        "streamSid": sid,
                        "media": {"payload": base64.b64encode(mulaw_bytes).decode()},
                    }
                )
            )
        except Exception:
            log.exception("twilio_ws: send audio failed sid=%s", sid)

    gemini_task = asyncio.create_task(
        _run_phone_gemini_session(inbound, send_to_twilio, stop_event)
    )

    started = time.perf_counter()
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            frame = parse_twilio_frame(msg)
            if frame.event == "start" and frame.stream_sid:
                stream_sid_holder["sid"] = frame.stream_sid
                log.info(
                    "twilio_ws: stream started sid=%s payload=%s",
                    frame.stream_sid,
                    msg.get("start"),
                )
            elif frame.event == "media" and frame.audio_mulaw:
                counters["in_frames"] += 1
                counters["in_bytes"] += len(frame.audio_mulaw)
                maybe_log_counters()
                pcm = mulaw_to_pcm16_16k(frame.audio_mulaw)
                try:
                    inbound.put_nowait(pcm)
                except asyncio.QueueFull:
                    log.warning(
                        "twilio_ws: inbound queue full sid=%s, dropping oldest",
                        stream_sid_holder.get("sid", "-"),
                    )
                    try:
                        _ = inbound.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        inbound.put_nowait(pcm)
                    except asyncio.QueueFull:
                        pass
            elif frame.event == "stop":
                log.info(
                    "twilio_ws: stream stopped sid=%s",
                    stream_sid_holder.get("sid", "-"),
                )
                break
            else:
                log.debug(
                    "twilio_ws: event=%s sid=%s",
                    frame.event,
                    frame.stream_sid,
                )
    except WebSocketDisconnect:
        log.info(
            "twilio_ws: client disconnect sid=%s",
            stream_sid_holder.get("sid", "-"),
        )
    finally:
        log.info(
            "twilio_ws: close sid=%s duration_s=%.1f",
            stream_sid_holder.get("sid", "-"),
            time.perf_counter() - started,
        )
        stop_event.set()
        try:
            inbound.put_nowait(None)
        except asyncio.QueueFull:
            pass
        gemini_task.cancel()
        try:
            await gemini_task
        except (asyncio.CancelledError, Exception):
            pass


# ---- TwiML webhook ----


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
    Vă rugăm să vizitați civicai.ro pentru asistență completă.
    Mulțumim.
  </Say>
</Response>
"""


def _bridge_is_healthy() -> bool:
    settings = get_settings()
    if not settings.gemini_api_key:
        return False
    if not settings.twilio_bridge_public_url:
        return False
    return True


@router.post("/voice/twilio/webhook")
async def twilio_voice_webhook(request: Request) -> Response:
    # Twilio posts form fields like From, To, CallSid; log them so we can
    # diagnose "Twilio dialed in but nothing happened" against the call log.
    try:
        form = await request.form()
        log.info(
            "twilio_webhook: incoming CallSid=%s From=%s To=%s",
            form.get("CallSid"),
            form.get("From"),
            form.get("To"),
        )
    except Exception:
        log.exception("twilio_webhook: form parse failed")
    if not _bridge_is_healthy():
        log.warning(
            "twilio_webhook: bridge unhealthy (gemini_key=%s bridge_url=%s) - returning fallback TwiML",
            bool(get_settings().gemini_api_key),
            bool(get_settings().twilio_bridge_public_url),
        )
        return Response(content=_TWIML_FALLBACK, media_type="application/xml")
    settings = get_settings()
    ws_url = settings.twilio_bridge_public_url
    log.info("twilio_webhook: returning bridge TwiML ws_url=%s", ws_url)
    return Response(
        content=_TWIML_BRIDGE.format(ws_url=ws_url),
        media_type="application/xml",
    )
