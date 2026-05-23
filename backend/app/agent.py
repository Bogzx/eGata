"""Text-transport SSE wrapper around session_engine.step().

The agent loop lives in app.session_engine. This module is a thin
adapter that:
  - Resolves or creates a Session keyed by req.conversation_id
  - Folds req.document_id into the session if the agent hasn't opened one yet
  - Runs step() and formats each Event as an SSE frame
  - Persists the session at end of turn

Two endpoints:
  POST /agent/chat         — non-streaming (kept for tests / programmatic callers)
  POST /agent/chat/stream  — SSE stream with `delta`, `tool_call`, `tool_result`,
                             `frontend_event`, `session_snapshot`, `done`, `error`
                             frames.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.citizens import fetch_citizen_by_id
from app.models import AgentChatRequest, AgentChatResponse, ChatToolCall
from app.security import current_citizen_id
from app.session_engine import Event, step
from app.sessions import (
    Session,
    SessionState,
    fetch_or_create_session,
    update_session,
)

log = logging.getLogger("agent")

router = APIRouter(prefix="/agent", tags=["agent"])


# ---- helpers ----


def _resolve_session(req: AgentChatRequest, citizen_id: UUID) -> Session:
    """Get-or-create a Session for this conversation.

    If the request carries a document_id and the session hasn't picked
    one up yet, fold it in and move to FILLING. This bridges the legacy
    frontend's `startProcedure → POST /documents` flow with the new
    state-machine world; SP5's UI deletes that path in favor of the
    agent calling start_procedure.
    """
    session = fetch_or_create_session(
        str(citizen_id), session_id=req.conversation_id
    )
    if req.document_id and not session.active_document_id:
        session.active_document_id = str(req.document_id)
        # The frontend opened a doc → we're filling, not exploring.
        if session.state == SessionState.EXPLORING:
            session.state = SessionState.FILLING
    return session


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


async def _events_to_sse(
    events: AsyncIterator[Event],
    *,
    conversation_id: str,
    on_finish: callable,
) -> AsyncIterator[bytes]:
    """Format each Event as one SSE frame; persist session at end."""
    yield _sse("conversation", {"conversation_id": conversation_id})
    try:
        async for ev in events:
            yield _sse(ev.kind, ev.data)
    except Exception as e:  # noqa: BLE001
        log.exception("session_engine.step crashed")
        yield _sse("error", {"detail": str(e)})
    finally:
        try:
            on_finish()
        except Exception:
            log.exception("session persist failed")


# ---- streaming endpoint ----


@router.post("/chat/stream")
async def chat_stream(
    req: AgentChatRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> StreamingResponse:
    """SSE stream — see module docstring for the frame schema."""
    session = _resolve_session(req, citizen_id)
    citizen = fetch_citizen_by_id(citizen_id)
    citizen_attrs = citizen.get("attributes") or {}

    prefs = req.preferences

    events = step(
        session,
        req.message,
        simple_language=bool(prefs and prefs.simple_language),
        voice_only=bool(prefs and prefs.voice_only),
        citizen_attrs=citizen_attrs,
    )

    def _persist():
        update_session(session)

    return StreamingResponse(
        _events_to_sse(events, conversation_id=session.id, on_finish=_persist),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---- non-streaming endpoint (kept for tests / programmatic callers) ----


@router.post("/chat", response_model=AgentChatResponse)
async def chat(
    req: AgentChatRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> AgentChatResponse:
    session = _resolve_session(req, citizen_id)
    citizen = fetch_citizen_by_id(citizen_id)
    citizen_attrs = citizen.get("attributes") or {}
    prefs = req.preferences

    final_message = "Cum te pot ajuta?"
    tool_calls: list[ChatToolCall] = []

    try:
        async for ev in step(
            session,
            req.message,
            simple_language=bool(prefs and prefs.simple_language),
            voice_only=bool(prefs and prefs.voice_only),
            citizen_attrs=citizen_attrs,
        ):
            if ev.kind == "tool_call":
                tool_calls.append(
                    ChatToolCall(
                        name=ev.data["name"],
                        arguments=ev.data.get("arguments") or {},
                    )
                )
            elif ev.kind == "done":
                final_message = ev.data.get("message") or final_message
            elif ev.kind == "error":
                raise HTTPException(
                    status_code=502, detail=ev.data.get("detail") or "Agent error"
                )
    finally:
        update_session(session)

    return AgentChatResponse(
        conversation_id=session.id,
        message=final_message,
        tool_calls=tool_calls,
    )
