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

from app.agent_tools import ToolContext, dispatch
from app.citizens import fetch_citizen_by_id
from app.models import (
    AgentChatRequest,
    AgentChatResponse,
    ChatToolCall,
    WidgetResultEvent,
    WidgetResultRequest,
    WidgetResultResponse,
)
from app.security import current_citizen_id
from app.session_engine import Event, step
from app.sessions import (
    IllegalTransitionError,
    Session,
    SessionState,
    fetch_or_create_session,
    session_lock,
    transition,
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
        # The frontend opened a doc → we're filling, not exploring. Go through
        # the state machine so any illegal jump is loud, not silent.
        if session.state != SessionState.FILLING:
            try:
                transition(session, SessionState.FILLING)
            except IllegalTransitionError:
                log.warning(
                    "legacy doc-injection: illegal %s -> FILLING, leaving state alone",
                    session.state.value,
                )
    return session


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


async def _stream_turn(
    req: AgentChatRequest,
    citizen_id: UUID,
) -> AsyncIterator[bytes]:
    """One streaming turn end-to-end: resolve session, step(), persist.

    Wrapped in session_lock(conversation_id) so concurrent turns on the
    same conversation (voice + text, two tabs, reload-during-stream)
    serialize instead of racing on session.history overwrites.
    """
    async with session_lock(req.conversation_id):
        session = _resolve_session(req, citizen_id)
        citizen = fetch_citizen_by_id(citizen_id)
        citizen_attrs = citizen.get("attributes") or {}
        prefs = req.preferences

        yield _sse("conversation", {"conversation_id": session.id})
        try:
            async for ev in step(
                session,
                req.message,
                simple_language=bool(prefs and prefs.simple_language),
                voice_only=bool(prefs and prefs.voice_only),
                citizen_attrs=citizen_attrs,
            ):
                yield _sse(ev.kind, ev.data)
        except Exception as e:  # noqa: BLE001
            log.exception("session_engine.step crashed")
            yield _sse("error", {"detail": str(e)})
        finally:
            try:
                update_session(session)
            except Exception:
                log.exception("session persist failed")


# ---- streaming endpoint ----


@router.post("/chat/stream")
async def chat_stream(
    req: AgentChatRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> StreamingResponse:
    """SSE stream — see module docstring for the frame schema."""
    return StreamingResponse(
        _stream_turn(req, citizen_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---- non-streaming endpoint (kept for tests / programmatic callers) ----


def _coerce_widget_value(target_field_value: Any, widget_type: str) -> Any:
    """Map raw widget submission values into the set_field shape.

    Confirm widgets carry "Da"/"Nu" or boolean — keep the literal so the
    set_field validator on the procedure schema can decide. Choice/date
    keep their raw type. The agent never has to translate.
    """
    if widget_type == "confirm" and isinstance(target_field_value, str):
        v = target_field_value.strip().lower()
        if v in {"da", "yes", "true"}:
            return True
        if v in {"nu", "no", "false"}:
            return False
    return target_field_value


# ---- widget result endpoint ----


@router.post("/widget-result", response_model=WidgetResultResponse)
async def widget_result(
    req: WidgetResultRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> WidgetResultResponse:
    """Resolve a pending widget without bouncing through Gemini.

    Frontend posts {conversation_id, widget_id, value}. We pop the matching
    PendingWidget from session.pending_widgets, call set_field via the
    state-gated dispatcher when a target_field is bound, append a
    user-side message to the LLM history (so next turn the model sees the
    answer in context), persist, and return the updated snapshot plus any
    side-effect events.
    """
    async with session_lock(req.conversation_id):
        session = fetch_or_create_session(
            str(citizen_id), session_id=req.conversation_id
        )
        if session.citizen_id != str(citizen_id):
            raise HTTPException(status_code=403, detail="Not your session")

        widget = session.resolve_pending_widget(req.widget_id)
        if widget is None:
            raise HTTPException(
                status_code=404,
                detail=f"Widget {req.widget_id!r} not pending (already resolved?)",
            )

        events: list[WidgetResultEvent] = []
        user_visible = (
            str(req.value) if not isinstance(req.value, str) else req.value
        )

        if widget.target_field:
            citizen = fetch_citizen_by_id(citizen_id)
            citizen_attrs = citizen.get("attributes") or {}
            ctx = ToolContext(
                citizen_id=str(citizen_id), citizen_attributes=citizen_attrs
            )
            field_value = _coerce_widget_value(req.value, widget.type)
            result = await dispatch(
                session,
                "set_field",
                {"name": widget.target_field, "value": field_value},
                ctx,
            )
            events.append(
                WidgetResultEvent(
                    kind="tool_result",
                    name="set_field",
                    output=result.output,
                    error=result.error,
                )
            )
            if result.frontend_event:
                events.append(
                    WidgetResultEvent(
                        kind="frontend_event", event=result.frontend_event
                    )
                )

        # Synthesize a user-side history turn so the LLM sees the answer in
        # context on the next chat turn — keeps continuity even though we
        # bypassed the chat round-trip.
        history_entry = {
            "role": "user",
            "parts": [
                {
                    "text": (
                        f"[răspuns widget {widget.target_field or widget.widget_id}] "
                        f"{user_visible}"
                    )
                }
            ],
        }
        session.history.append(history_entry)

        update_session(session)

        return WidgetResultResponse(
            conversation_id=session.id,
            snapshot=session.snapshot(),
            user_message=user_visible,
            events=events,
        )


@router.post("/chat", response_model=AgentChatResponse)
async def chat(
    req: AgentChatRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> AgentChatResponse:
    async with session_lock(req.conversation_id):
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
