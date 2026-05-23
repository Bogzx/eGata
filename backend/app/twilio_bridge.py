"""Twilio Media Streams ↔ Azure VoiceLive bridge for phone calls.

Twilio sends 8 kHz mono μ-law in JSON envelopes over WebSocket. We
transcode to/from PCM16 (24 kHz both directions for Azure) and proxy to
an Azure VoiceLive session configured with the phone system prompt and a
restricted tool allowlist (RAG-only — no document writes from phone).

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

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect

from azure.ai.voicelive.aio import connect as voicelive_connect
from azure.ai.voicelive.models import (
    AudioInputTranscriptionOptions,
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

from app.agent_tools import REGISTRY as TOOLS_REGISTRY, ToolContext, dispatch
from app.azure_clients import get_voicelive_credential, tools_for_realtime
from app.config import get_settings
from app.prompts import build_system_prompt
from app.sessions import Session, SessionState


def _phone_session_id() -> str:
    return secrets.token_urlsafe(8)


router = APIRouter(tags=["twilio"])
log = logging.getLogger("twilio_bridge")


PHONE_TOOL_ALLOWLIST: set[str] = {"lookup_procedure", "find_redirect"}
_AZURE_PCM_RATE = 24000


# ---- Audio codec helpers ----


def mulaw_8k_to_pcm16_24k(mulaw_bytes: bytes, state: Any) -> tuple[bytes, Any]:
    """8 kHz μ-law → 24 kHz PCM16 mono, state-preserving."""
    pcm8k = audioop.ulaw2lin(mulaw_bytes, 2)
    pcm24k, new_state = audioop.ratecv(pcm8k, 2, 1, 8000, _AZURE_PCM_RATE, state)
    return pcm24k, new_state


def pcm16_24k_to_mulaw_8k(pcm24k_bytes: bytes, state: Any) -> tuple[bytes, Any]:
    """24 kHz PCM16 → 8 kHz μ-law for Twilio, state-preserving."""
    pcm8k, new_state = audioop.ratecv(pcm24k_bytes, 2, 1, _AZURE_PCM_RATE, 8000, state)
    return audioop.lin2ulaw(pcm8k, 2), new_state


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


# ---- Phone VoiceLive session ----


def _phone_function_declarations() -> list[dict[str, Any]]:
    return [
        TOOLS_REGISTRY[n].function_declaration()
        for n in PHONE_TOOL_ALLOWLIST
        if n in TOOLS_REGISTRY
    ]


async def _run_phone_voicelive_session(
    inbound: asyncio.Queue[bytes | None],
    send_to_twilio: Callable[[bytes], Awaitable[None]],
    send_clear_to_twilio: Callable[[], Awaitable[None]],
    stop_event: asyncio.Event,
) -> None:
    settings = get_settings()

    # Phone agent runs an ephemeral in-memory Session in EXPLORING — no
    # document creation, no persistence, no DB writes.
    phone_session = Session(
        id=f"phone_{_phone_session_id()}",
        citizen_id="phone-anonymous",
        state=SessionState.EXPLORING,
    )
    phone_ctx = ToolContext(
        citizen_id="phone-anonymous",
        citizen_attributes={},
    )

    voice = AzureStandardVoice(name=settings.azure_voicelive_voice)
    session_config = RequestSession(
        modalities=[Modality.TEXT, Modality.AUDIO],
        instructions=build_system_prompt(variant="phone"),
        voice=voice,
        input_audio_format=InputAudioFormat.PCM16,
        output_audio_format=OutputAudioFormat.PCM16,
        input_audio_transcription=AudioInputTranscriptionOptions(
            model=settings.azure_voicelive_transcription_model,
            language=settings.azure_voicelive_transcription_language,
        ),
        turn_detection=AzureSemanticVadMultilingual(),
        tools=tools_for_realtime(_phone_function_declarations()),
        tool_choice="auto",
    )

    log.info(
        "twilio_voicelive: connecting endpoint=%s model=%s session=%s",
        settings.azure_voicelive_endpoint,
        settings.azure_voicelive_model,
        phone_session.id,
    )

    pending_tool_calls: dict[str, dict[str, str]] = {}

    async with voicelive_connect(
        endpoint=settings.azure_voicelive_endpoint,
        credential=get_voicelive_credential(),
        api_version=settings.azure_voicelive_api_version,
        model=settings.azure_voicelive_model,
    ) as connection:
        log.info("twilio_voicelive: connected session=%s", phone_session.id)
        await connection.session.update(session=session_config)

        # Greet immediately so the caller isn't met with silence.
        try:
            await connection.conversation.item.create(
                item=MessageItem(
                    role="system",
                    content=[
                        InputTextContentPart(
                            text="Salutați politicos cetățeanul și întrebați cum îl puteți ajuta."
                        )
                    ],
                )
            )
            await connection.response.create()
        except Exception:
            log.exception(
                "twilio_voicelive: greeting failed session=%s",
                phone_session.id,
            )

        async def pump_inbound() -> None:
            in_state: Any = None
            while not stop_event.is_set():
                pcm24k = await inbound.get()
                if pcm24k is None:
                    break
                try:
                    b64 = base64.b64encode(pcm24k).decode("ascii")
                    await connection.input_audio_buffer.append(audio=b64)
                except Exception:
                    log.exception(
                        "twilio_voicelive: input_audio_buffer.append failed session=%s",
                        phone_session.id,
                    )
                    break
            log.info(
                "twilio_voicelive: inbound pump stopped session=%s",
                phone_session.id,
            )

        async def pump_outbound() -> None:
            out_state: Any = None
            async for event in connection:
                et = getattr(event, "type", None)

                if et == ServerEventType.RESPONSE_AUDIO_DELTA:
                    delta = getattr(event, "delta", None)
                    if delta:
                        try:
                            pcm = (
                                base64.b64decode(delta)
                                if isinstance(delta, str)
                                else bytes(delta)
                            )
                            mulaw, out_state = pcm16_24k_to_mulaw_8k(pcm, out_state)
                            await send_to_twilio(mulaw)
                        except Exception:
                            log.exception(
                                "twilio_voicelive: audio out failed session=%s",
                                phone_session.id,
                            )

                elif et == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED:
                    # Caller barge-in. Two things must happen, in order:
                    #   1. Tell VoiceLive to stop generating more audio.
                    #   2. Tell Twilio to drop everything we've already
                    #      buffered for playback. VoiceLive emits TTS
                    #      faster than realtime, so cancelling step 1
                    #      alone still leaves seconds of agent audio
                    #      queued in Twilio's outbound stream.
                    try:
                        await connection.response.cancel()
                    except Exception:
                        pass
                    await send_clear_to_twilio()
                    log.info(
                        "twilio_voicelive: barge-in (caller spoke) session=%s",
                        phone_session.id,
                    )

                elif et == ServerEventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA:
                    call_id = getattr(event, "call_id", "") or ""
                    if not call_id:
                        continue
                    slot = pending_tool_calls.setdefault(
                        call_id,
                        {"name": getattr(event, "name", "") or "", "args": ""},
                    )
                    slot["args"] += getattr(event, "delta", "") or ""

                elif et == ServerEventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE:
                    call_id = getattr(event, "call_id", "") or ""
                    slot = pending_tool_calls.pop(call_id, None)
                    name = (
                        (slot.get("name") if slot else "")
                        or getattr(event, "name", "")
                        or ""
                    )
                    args_buf = (
                        (slot.get("args") if slot else "")
                        or getattr(event, "arguments", "")
                        or ""
                    )
                    try:
                        args = json.loads(args_buf) if args_buf else {}
                    except json.JSONDecodeError:
                        args = {}
                        log.warning(
                            "twilio_voicelive: tool args not json session=%s name=%s raw=%r",
                            phone_session.id,
                            name,
                            args_buf[:200],
                        )

                    if name not in PHONE_TOOL_ALLOWLIST:
                        log.warning(
                            "twilio_voicelive: phone tried disallowed tool=%s session=%s",
                            name,
                            phone_session.id,
                        )
                        output_payload = {"error": "tool_not_available_on_phone"}
                    else:
                        log.info(
                            "twilio_voicelive: tool_call session=%s name=%s args=%r",
                            phone_session.id,
                            name,
                            args,
                        )
                        result = await dispatch(
                            phone_session, name, args, phone_ctx
                        )
                        if result.error is not None:
                            output_payload = {
                                "error": result.error,
                                "output": result.output,
                            }
                        else:
                            output_payload = {"output": result.output}

                    try:
                        await connection.conversation.item.create(
                            item=FunctionCallOutputItem(
                                call_id=call_id,
                                output=json.dumps(
                                    output_payload, ensure_ascii=False
                                ),
                            )
                        )
                        await connection.response.create()
                    except Exception:
                        log.exception(
                            "twilio_voicelive: function_call_output failed session=%s",
                            phone_session.id,
                        )

                elif et == ServerEventType.ERROR:
                    err = getattr(event, "error", None)
                    msg = (
                        getattr(err, "message", None)
                        if err is not None
                        else str(event)
                    ) or "unknown"
                    if "no active response" not in msg.lower():
                        log.error(
                            "twilio_voicelive: error session=%s: %s",
                            phone_session.id,
                            msg,
                        )

            log.info(
                "twilio_voicelive: outbound pump stopped session=%s",
                phone_session.id,
            )

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
    counters = {"in_frames": 0, "in_bytes": 0, "out_frames": 0, "out_bytes": 0}
    last_log = [time.perf_counter()]
    resample_in_state: list[Any] = [None]

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

    async def send_clear_to_twilio() -> None:
        sid = stream_sid_holder.get("sid")
        if not sid:
            return
        try:
            await ws.send_text(
                json.dumps({"event": "clear", "streamSid": sid})
            )
            log.info("twilio_ws: clear (barge-in flush) sid=%s", sid)
        except Exception:
            log.exception("twilio_ws: send clear failed sid=%s", sid)

    voicelive_task = asyncio.create_task(
        _run_phone_voicelive_session(
            inbound, send_to_twilio, send_clear_to_twilio, stop_event
        )
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
                pcm24k, resample_in_state[0] = mulaw_8k_to_pcm16_24k(
                    frame.audio_mulaw, resample_in_state[0]
                )
                try:
                    inbound.put_nowait(pcm24k)
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
                        inbound.put_nowait(pcm24k)
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
        voicelive_task.cancel()
        try:
            await voicelive_task
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
    if not settings.azure_voicelive_api_key:
        return False
    if not settings.twilio_bridge_public_url:
        return False
    return True


@router.post("/voice/twilio/webhook")
async def twilio_voice_webhook(request: Request) -> Response:
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
            "twilio_webhook: bridge unhealthy (azure_key=%s bridge_url=%s) - returning fallback TwiML",
            bool(get_settings().azure_voicelive_api_key),
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
