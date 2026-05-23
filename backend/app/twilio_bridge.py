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
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types as genai_types

from app.config import get_settings
from app.prompts import build_system_prompt
from app.tools import REGISTRY, ToolContext

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
    phone_ctx = ToolContext(citizen_id="phone-anonymous", document_id=None)

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

    async with client.aio.live.connect(
        model=settings.gemini_voice_model, config=config
    ) as session:

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
                    log.exception("send_realtime_input failed")
                    break

        async def pump_outbound() -> None:
            async for response in session.receive():
                if getattr(response, "data", None):
                    try:
                        mulaw = pcm16_24k_to_mulaw_8k(response.data)
                        await send_to_twilio(mulaw)
                    except Exception:
                        log.exception("audio out failed")
                tc = getattr(response, "tool_call", None)
                if tc and getattr(tc, "function_calls", None):
                    fr_parts: list[genai_types.FunctionResponse] = []
                    for fc in tc.function_calls:
                        if fc.name not in PHONE_TOOL_ALLOWLIST:
                            log.warning("Phone agent tried disallowed tool %s", fc.name)
                            fr_parts.append(
                                genai_types.FunctionResponse(
                                    id=getattr(fc, "id", None),
                                    name=fc.name,
                                    response={"error": "tool_not_available_on_phone"},
                                )
                            )
                            continue
                        tool = REGISTRY.get(fc.name)
                        if tool is None:
                            fr_parts.append(
                                genai_types.FunctionResponse(
                                    id=getattr(fc, "id", None),
                                    name=fc.name,
                                    response={"error": "unknown_tool"},
                                )
                            )
                            continue
                        try:
                            result = await tool(phone_ctx, **(dict(fc.args) if fc.args else {}))
                            if hasattr(result, "model_dump"):
                                result = result.model_dump(mode="json")
                            fr_parts.append(
                                genai_types.FunctionResponse(
                                    id=getattr(fc, "id", None),
                                    name=fc.name,
                                    response={"output": result},
                                )
                            )
                        except Exception as e:  # noqa: BLE001
                            log.exception("Phone tool %s failed", fc.name)
                            fr_parts.append(
                                genai_types.FunctionResponse(
                                    id=getattr(fc, "id", None),
                                    name=fc.name,
                                    response={"error": str(e)},
                                )
                            )
                    try:
                        await session.send_tool_response(function_responses=fr_parts)
                    except Exception:
                        log.exception("send_tool_response failed")
                sc = getattr(response, "server_content", None)
                if sc and getattr(sc, "interrupted", False):
                    log.debug("Phone agent interrupted (barge-in)")

        await asyncio.gather(pump_inbound(), pump_outbound())


# ---- WebSocket endpoint ----


@router.websocket("/voice/twilio")
async def twilio_media_stream(ws: WebSocket) -> None:
    await ws.accept()
    log.info("Twilio Media Stream connected")

    inbound: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=200)
    stop_event = asyncio.Event()
    stream_sid_holder: dict[str, str] = {}

    async def send_to_twilio(mulaw_bytes: bytes) -> None:
        sid = stream_sid_holder.get("sid")
        if not sid:
            return
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
                    try:
                        _ = inbound.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        inbound.put_nowait(pcm)
                    except asyncio.QueueFull:
                        pass
            elif frame.event == "stop":
                log.info("Twilio stream stopped")
                break
    except WebSocketDisconnect:
        log.info("Twilio WS disconnected")
    finally:
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
async def twilio_voice_webhook(request: Request) -> Response:  # noqa: ARG001
    if not _bridge_is_healthy():
        return Response(content=_TWIML_FALLBACK, media_type="application/xml")
    settings = get_settings()
    ws_url = settings.twilio_bridge_public_url
    return Response(
        content=_TWIML_BRIDGE.format(ws_url=ws_url),
        media_type="application/xml",
    )
