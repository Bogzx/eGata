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
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.agent_tools import ToolContext, dispatch
from app.citizens import fetch_citizen_by_id
from app.documents import fetch_document
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
    SessionOwnershipError,
    SessionState,
    fetch_or_create_session,
    fetch_session,
    mark_review_confirmed,
    session_lock,
    transition,
    update_session,
)

log = logging.getLogger("agent")

router = APIRouter(prefix="/agent", tags=["agent"])


# ---- helpers ----


def check_document_owner(document_id: UUID | str, citizen_id: UUID | str) -> None:
    """403 unless `document_id` exists and belongs to `citizen_id`.

    A client-supplied document_id is folded into the session as its active
    document, and the per-turn preamble then prints that document's fields
    into the model context — so an unchecked id would leak another citizen's
    form into this citizen's chat.
    """
    doc = fetch_document(UUID(str(document_id)))
    if str(doc["citizen_id"]) != str(citizen_id):
        raise HTTPException(status_code=403, detail="Not your document")


def check_conversation_access(req: AgentChatRequest, citizen_id: UUID) -> None:
    """Refuse a foreign conversation_id / document_id before any work starts.

    Runs before the SSE response begins, so the refusal is a real 403 rather
    than an error frame inside a 200 stream.
    """
    if req.conversation_id:
        existing = fetch_session(req.conversation_id)
        if existing is not None and existing.citizen_id != str(citizen_id):
            log.warning(
                "agent.chat: forbidden conv=%s requester=%s",
                req.conversation_id,
                citizen_id,
            )
            raise HTTPException(status_code=403, detail="Not your conversation")
    if req.document_id:
        check_document_owner(req.document_id, citizen_id)


def _resolve_session(req: AgentChatRequest, citizen_id: UUID) -> Session:
    """Get-or-create a Session for this conversation.

    If the request carries a document_id and the session hasn't picked
    one up yet, fold it in and move to FILLING. This bridges the legacy
    frontend's `startProcedure → POST /documents` flow with the new
    state-machine world; SP5's UI deletes that path in favor of the
    agent calling start_procedure.
    """
    # Diagnostic: missing conversation_id on a chat request is normal on
    # the very first turn, but if it happens repeatedly for the same
    # browser the frontend isn't echoing the `event: conversation` SSE
    # frame back. Each fresh session means the AI has no history, which
    # presents as "the chat ignores my previous messages".
    is_new = req.conversation_id is None
    if is_new:
        log.info(
            "agent.chat: no conversation_id on request (citizen=%s, doc=%s) — "
            "creating fresh session. If this recurs for the same browser, "
            "the frontend may be dropping the `event: conversation` SSE frame.",
            citizen_id,
            req.document_id,
        )
    try:
        session = fetch_or_create_session(
            str(citizen_id), session_id=req.conversation_id
        )
    except SessionOwnershipError as exc:
        raise HTTPException(status_code=403, detail="Not your conversation") from exc
    log.info(
        "session: %s conv=%s citizen=%s state=%s doc=%s history_turns=%d",
        "created" if is_new else "loaded",
        session.id,
        citizen_id,
        session.state.value,
        session.active_document_id,
        len(session.history),
    )
    if req.document_id and not session.active_document_id:
        check_document_owner(req.document_id, citizen_id)
        session.active_document_id = str(req.document_id)
        # The frontend opened a doc → we're filling, not exploring. Go through
        # the state machine so any illegal jump is loud, not silent.
        if session.state != SessionState.FILLING:
            try:
                transition(session, SessionState.FILLING)
                log.info(
                    "session: doc-injection conv=%s doc=%s -> FILLING",
                    session.id,
                    req.document_id,
                )
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

    On the first turn `req.conversation_id` is None — locking on the literal
    None then serialises EVERY citizen's first turn across the whole demo,
    which is what was making the chat feel "stuck" under any concurrent
    load. Fall back to a per-citizen lock key so a fresh conversation only
    blocks other fresh conversations from the SAME citizen (a normal user
    can't have two simultaneous new sessions anyway).
    """
    lock_key = req.conversation_id or f"citizen:{citizen_id}:new"
    log.info(
        "chat_stream: in citizen=%s conv=%s doc=%s msg=%r prefs=%s",
        citizen_id,
        req.conversation_id,
        req.document_id,
        (req.message or "")[:120],
        req.preferences.model_dump() if req.preferences else None,
    )
    started = time.perf_counter()
    event_counts: dict[str, int] = {}
    async with session_lock(lock_key):
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
                event_counts[ev.kind] = event_counts.get(ev.kind, 0) + 1
                yield _sse(ev.kind, ev.data)
        except Exception as e:  # noqa: BLE001
            log.exception("session_engine.step crashed conv=%s", session.id)
            # Structured error frame so the frontend can branch on `code`
            # instead of guessing from a free-form `detail` string. The
            # `type` field carries the exception class for debugging; the
            # `detail` keeps the human-readable message for legacy clients
            # that still read it.
            yield _sse(
                "error",
                {
                    "code": "agent_error",
                    "type": type(e).__name__,
                    "detail": str(e),
                },
            )
        finally:
            try:
                update_session(session)
            except Exception:
                log.exception("session persist failed conv=%s", session.id)
            log.info(
                "chat_stream: out conv=%s duration_ms=%.0f events=%s state=%s",
                session.id,
                (time.perf_counter() - started) * 1000,
                event_counts,
                session.state.value,
            )


# ---- streaming endpoint ----


@router.post("/chat/stream")
async def chat_stream(
    req: AgentChatRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> StreamingResponse:
    """SSE stream — see module docstring for the frame schema."""
    check_conversation_access(req, citizen_id)
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
    """Resolve a pending widget without bouncing through the model.

    Frontend posts {conversation_id, widget_id, value}. We pop the matching
    PendingWidget from session.pending_widgets, call set_field via the
    state-gated dispatcher when a target_field is bound, append a
    user-side message to the LLM history (so next turn the model sees the
    answer in context), persist, and return the updated snapshot plus any
    side-effect events.
    """
    log.info(
        "widget_result: in citizen=%s conv=%s widget=%s value=%r",
        citizen_id,
        req.conversation_id,
        req.widget_id,
        req.value,
    )
    async with session_lock(req.conversation_id):
        # fetch, not fetch_or_create: a widget answer for a conversation that
        # does not exist has nothing to resolve, and creating an empty session
        # under a client-chosen id would only litter the table.
        session = fetch_session(req.conversation_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if session.citizen_id != str(citizen_id):
            log.warning(
                "widget_result: forbidden conv=%s owner=%s requester=%s",
                req.conversation_id,
                session.citizen_id,
                citizen_id,
            )
            raise HTTPException(status_code=403, detail="Not your session")

        widget = session.resolve_pending_widget(req.widget_id)
        if widget is None:
            log.warning(
                "widget_result: not pending conv=%s widget=%s (already resolved?)",
                req.conversation_id,
                req.widget_id,
            )
            raise HTTPException(
                status_code=404,
                detail=f"Widget {req.widget_id!r} not pending (already resolved?)",
            )
        log.info(
            "widget_result: resolved conv=%s widget=%s type=%s target_field=%s",
            session.id,
            req.widget_id,
            widget.type,
            widget.target_field,
        )

        # A confirm widget answered Da in REVIEWING is the user's go-ahead
        # for the form. Unlocks the delivery `choice` widget — propose_widget
        # otherwise refuses to keep the LLM from skipping the verification
        # step (it tends to jump straight to the delivery picker).
        if (
            widget.type == "confirm"
            and session.state == SessionState.REVIEWING
            and str(req.value).strip().lower() in {"da", "true", "yes"}
        ):
            mark_review_confirmed(session.id)

        events: list[WidgetResultEvent] = []
        user_visible = (
            str(req.value) if not isinstance(req.value, str) else req.value
        )

        # Only dispatch set_field when there's a document to write into.
        # A pre-fix widget may have been created with target_field while
        # the session was in CONFIRMING_MATCH; treat its submission as a
        # text answer instead of crashing on the state-gate.
        can_set_field = (
            widget.target_field is not None
            and session.state in {SessionState.FILLING, SessionState.REVIEWING}
        )
        if can_set_field:
            # Direct path: a field gets set; the agent doesn't need to
            # react this turn because the field_updated event + state recap
            # carry the change to the model on its next turn. We synthesize
            # a [răspuns widget X] history line so the model has transcript
            # continuity ("user clicked Y").
            citizen = fetch_citizen_by_id(citizen_id)
            citizen_attrs = citizen.get("attributes") or {}
            ctx = ToolContext(
                citizen_id=str(citizen_id), citizen_attributes=citizen_attrs
            )
            field_value = _coerce_widget_value(req.value, widget.type)
            prev_state = session.state
            result = await dispatch(
                session,
                "set_field",
                {"name": widget.target_field, "value": field_value},
                ctx,
            )

            # If set_field failed (e.g. the model invented an option label
            # that doesn't match the schema's enum), don't bubble the error
            # to the UI as a system bubble. Fall through to the chat-followup
            # path: the frontend re-posts the user's choice as a normal turn,
            # the model sees the validation error in the tool result, and
            # re-runs set_field with the corrected value.
            if result.error is not None:
                log.info(
                    "widget_result: set_field failed conv=%s field=%s value=%r — falling back to chat followup",
                    session.id,
                    widget.target_field,
                    field_value,
                )
                update_session(session)
                return WidgetResultResponse(
                    conversation_id=session.id,
                    snapshot=session.snapshot(),
                    user_message=user_visible,
                    events=events,
                    requires_chat_followup=True,
                )

            events.append(
                WidgetResultEvent(
                    kind="tool_result",
                    name="set_field",
                    output=result.output,
                    error=None,
                )
            )
            if result.frontend_event:
                events.append(
                    WidgetResultEvent(
                        kind="frontend_event", event=result.frontend_event
                    )
                )

            # If this set_field flipped the session into REVIEWING (i.e. it
            # was the last required field), the agent MUST run a turn so it
            # can propose the verification widget. Without this, a choice
            # widget bound to the last required field (e.g. `numar_arbori`
            # for taiere-arbore) leaves the session in REVIEWING with no
            # follow-up — user is stuck after answering the picker.
            # Skip the synthetic history line; sendText on the frontend
            # will append the real user message for the chat turn.
            log.info(
                "widget_result: post-dispatch conv=%s prev_state=%s new_state=%s",
                session.id,
                prev_state.value,
                session.state.value,
            )
            if (
                prev_state == SessionState.FILLING
                and session.state == SessionState.REVIEWING
            ):
                log.info(
                    "widget_result: FILLING→REVIEWING transition, returning requires_chat_followup=True conv=%s",
                    session.id,
                )
                update_session(session)
                return WidgetResultResponse(
                    conversation_id=session.id,
                    snapshot=session.snapshot(),
                    user_message=user_visible,
                    events=events,
                    requires_chat_followup=True,
                )

            # OpenAI message shape — matches the new session.history format.
            session.history.append(
                {
                    "role": "user",
                    "content": (
                        f"[răspuns widget {widget.target_field}] "
                        f"{user_visible}"
                    ),
                }
            )
            update_session(session)

            return WidgetResultResponse(
                conversation_id=session.id,
                snapshot=session.snapshot(),
                user_message=user_visible,
                events=events,
                requires_chat_followup=False,
            )

        # No target_field path (typical confirm widget in CONFIRMING_MATCH):
        # the answer is a signal — the agent must run a turn and decide
        # what to do (start_procedure, abandon, etc.). We persist the
        # widget resolution (pending_widgets popped) and ask the frontend
        # to follow up via /agent/chat/stream so the user message goes
        # through the normal turn pipeline. Skipping the synthetic history
        # line here — the chat turn will append the real one.
        update_session(session)
        return WidgetResultResponse(
            conversation_id=session.id,
            snapshot=session.snapshot(),
            user_message=user_visible,
            events=events,
            requires_chat_followup=True,
        )


@router.post("/chat", response_model=AgentChatResponse)
async def chat(
    req: AgentChatRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> AgentChatResponse:
    check_conversation_access(req, citizen_id)
    # Per-citizen fallback on first turn — see _stream_turn for details.
    lock_key = req.conversation_id or f"citizen:{citizen_id}:new"
    log.info(
        "chat: in citizen=%s conv=%s doc=%s msg=%r",
        citizen_id,
        req.conversation_id,
        req.document_id,
        (req.message or "")[:120],
    )
    started = time.perf_counter()
    async with session_lock(lock_key):
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
                    log.error(
                        "chat: agent error conv=%s detail=%r",
                        session.id,
                        ev.data.get("detail"),
                    )
                    # Mirror the SSE shape so programmatic callers can
                    # branch on `code` instead of substring-matching
                    # `detail`. FastAPI serializes `detail` as-is when
                    # it's a dict.
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "code": ev.data.get("code") or "agent_error",
                            "type": ev.data.get("type"),
                            "message": ev.data.get("detail") or "Agent error",
                        },
                    )
        finally:
            update_session(session)
            log.info(
                "chat: out conv=%s duration_ms=%.0f tool_calls=%d final_len=%d",
                session.id,
                (time.perf_counter() - started) * 1000,
                len(tool_calls),
                len(final_message),
            )

    return AgentChatResponse(
        conversation_id=session.id,
        message=final_message,
        tool_calls=tool_calls,
    )
