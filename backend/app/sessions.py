"""Session aggregate + state machine + persistence.

A `Session` is the agent's view of the world for a single conversation.
It owns the current state (exploring / confirming_match / filling /
reviewing / delivered / redirected), the active document id, the
conversation history (Gemini `Content` list serialized to JSON), and
any pending UI widgets. Tools mutate the Session via permitted
transitions; the result is snapshotted to the client.

State diagram::

    exploring ─┬── confirming_match ─── filling ─── reviewing ─── delivered
               │           │              │            │              │
               │           ▼              │            │              │
               └────── exploring          │            │              │
                                          ▼            ▼              ▼
                                       exploring    filling       exploring
                                                                  (next proc.)

    Any state can also flip to `redirected` (out-of-scope) or back to
    `exploring` (user resets). Conditional fields (applies_if) can flip
    reviewing → filling when a previously-required field becomes blank.

This module is independent of any transport layer. SP2 / SP4 wire it to
the agent loop and the WebSocket bridge.
"""
from __future__ import annotations

import asyncio
import enum
import json
import secrets
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.db import get_pg_connection


def _next_snapshot_seq() -> int:
    """Monotonic per-process counter for snapshot ordering.

    The session_lock serializes turns on the same conversation, so within a
    process snapshots already arrive in order. This seq is defense in depth
    so the frontend can reject any obviously-stale snapshot that slips
    through buffering / reconnect / future transports.
    """
    return time.monotonic_ns()


class SessionState(str, enum.Enum):
    EXPLORING = "exploring"
    CONFIRMING_MATCH = "confirming_match"
    FILLING = "filling"
    REVIEWING = "reviewing"
    DELIVERED = "delivered"
    REDIRECTED = "redirected"


# Allowed transitions: source -> set of permitted destinations. Self-loops
# are explicit so callers can "no-op transition" without special-casing.
_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.EXPLORING: {
        SessionState.EXPLORING,
        SessionState.CONFIRMING_MATCH,
        # Legacy doc-injection path: frontend POSTs /documents then chats with
        # an active document_id, so the transport jumps straight to FILLING.
        SessionState.FILLING,
        SessionState.REDIRECTED,
    },
    SessionState.CONFIRMING_MATCH: {
        SessionState.CONFIRMING_MATCH,
        SessionState.EXPLORING,
        SessionState.FILLING,
        SessionState.REDIRECTED,
    },
    SessionState.FILLING: {
        SessionState.FILLING,
        SessionState.REVIEWING,
        SessionState.EXPLORING,
        SessionState.REDIRECTED,
    },
    SessionState.REVIEWING: {
        SessionState.REVIEWING,
        SessionState.FILLING,
        SessionState.DELIVERED,
        SessionState.EXPLORING,
    },
    SessionState.DELIVERED: {
        SessionState.DELIVERED,
        SessionState.EXPLORING,
        SessionState.CONFIRMING_MATCH,  # scenario step continuation
        # Scenario chain step 2: start_procedure opens the next doc and jumps
        # straight to FILLING without an interactive confirm.
        SessionState.FILLING,
    },
    SessionState.REDIRECTED: {
        SessionState.REDIRECTED,
        SessionState.EXPLORING,
    },
}


def can_transition(from_state: SessionState, to_state: SessionState) -> bool:
    """True if the state machine allows from_state -> to_state."""
    return to_state in _TRANSITIONS.get(from_state, set())


@dataclass
class PendingWidget:
    """A widget the agent emitted that the user hasn't answered yet.

    The frontend round-trips the answer via a structured `widget_result`
    event keyed by `widget_id`; the bridge translates that into the
    appropriate `set_field` call without the LLM having to re-parse.
    """
    widget_id: str
    type: str  # 'choice' | 'confirm' | 'date'
    question: str
    target_field: str | None = None
    options: list[str] = field(default_factory=list)


@dataclass
class Session:
    id: str
    citizen_id: str
    state: SessionState = SessionState.EXPLORING
    active_document_id: str | None = None
    scenario_id: str | None = None
    step_index: int | None = None
    pending_widgets: list[PendingWidget] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def snapshot(self) -> dict[str, Any]:
        """Serializable snapshot pushed to the client over the wire.

        Excludes `history` (large + agent-internal). Includes everything
        the frontend needs to render the right pane and live messages.
        Each snapshot carries a monotonic `seq` so the frontend can drop
        stale snapshots if reordering ever creeps in.
        """
        return {
            "id": self.id,
            "citizen_id": self.citizen_id,
            "state": self.state.value,
            "active_document_id": self.active_document_id,
            "scenario_id": self.scenario_id,
            "step_index": self.step_index,
            "pending_widgets": [
                {
                    "widget_id": w.widget_id,
                    "type": w.type,
                    "question": w.question,
                    "target_field": w.target_field,
                    "options": list(w.options),
                }
                for w in self.pending_widgets
            ],
            "seq": _next_snapshot_seq(),
        }

    def add_pending_widget(self, w: PendingWidget) -> None:
        self.pending_widgets.append(w)

    def resolve_pending_widget(self, widget_id: str) -> PendingWidget | None:
        """Pop and return a pending widget by id (or None)."""
        for i, w in enumerate(self.pending_widgets):
            if w.widget_id == widget_id:
                return self.pending_widgets.pop(i)
        return None


def new_session_id() -> str:
    return f"sess_{secrets.token_urlsafe(8)}"


def _jsonb(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


# ---- persistence ----

_SELECT_COLS = (
    "id, citizen_id, state, active_document_id, scenario_id, "
    "step_index, pending_widgets, history, created_at, updated_at"
)


def insert_session(
    citizen_id: str | UUID,
    session_id: str | None = None,
) -> Session:
    """Insert a session row. Race-safe via ON CONFLICT DO NOTHING.

    If `session_id` is already taken (e.g. two concurrent transports —
    text SSE + voice WS — both racing to create the same conversation),
    the INSERT silently does nothing and we SELECT the existing row.
    The caller sees either the row this call created or the row the
    competing call already had; both are correct.
    """
    sid = session_id or new_session_id()
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"insert into sessions (id, citizen_id) values (%s, %s) "
            f"on conflict (id) do nothing "
            f"returning {_SELECT_COLS};",
            (sid, str(citizen_id)),
        )
        row = cur.fetchone()
        if row is None:
            # Conflict — someone else inserted the same id just before us.
            cur.execute(
                f"select {_SELECT_COLS} from sessions where id = %s;",
                (sid,),
            )
            row = cur.fetchone()
        conn.commit()
    if row is None:
        raise RuntimeError("session insert returned no row even after conflict select")
    return _row_to_session(dict(row))


def fetch_session(session_id: str) -> Session | None:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"select {_SELECT_COLS} from sessions where id = %s;",
            (session_id,),
        )
        row = cur.fetchone()
    return _row_to_session(dict(row)) if row else None


def fetch_or_create_session(
    citizen_id: str | UUID, session_id: str | None = None
) -> Session:
    """If `session_id` is given AND exists, return it. Otherwise insert.

    Race-safe: `insert_session` uses ON CONFLICT DO NOTHING so two
    concurrent first-touch callers (text SSE + voice WS opening the
    same conversation at once) won't blow up with a UniqueViolation.
    """
    if session_id:
        existing = fetch_session(session_id)
        if existing is not None:
            return existing
    return insert_session(citizen_id, session_id=session_id)


def update_session(session: Session) -> Session:
    """Persist the full session state. Bumps `updated_at`."""
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "update sessions set "
            "state = %s, "
            "active_document_id = %s, "
            "scenario_id = %s, "
            "step_index = %s, "
            "pending_widgets = %s::jsonb, "
            "history = %s::jsonb, "
            "updated_at = now() "
            "where id = %s "
            "returning updated_at;",
            (
                session.state.value,
                session.active_document_id,
                session.scenario_id,
                session.step_index,
                _jsonb(
                    [
                        {
                            "widget_id": w.widget_id,
                            "type": w.type,
                            "question": w.question,
                            "target_field": w.target_field,
                            "options": list(w.options),
                        }
                        for w in session.pending_widgets
                    ]
                ),
                _jsonb(session.history),
                session.id,
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"session {session.id} not found")
        conn.commit()
        session.updated_at = row["updated_at"]
    return session


def transition(session: Session, to_state: SessionState) -> Session:
    """Mutate session.state if the transition is allowed; raise otherwise.

    Does NOT persist — callers `update_session(session)` after any series
    of mutations to keep round-trips low.
    """
    if not can_transition(session.state, to_state):
        raise IllegalTransitionError(
            f"Illegal transition {session.state.value} -> {to_state.value}"
        )
    session.state = to_state
    return session


class IllegalTransitionError(ValueError):
    """Raised when a state transition is not permitted."""


# ---- per-session in-process lock ----
#
# Single-worker scope (the demo runs one FastAPI process). Concurrent
# transports (voice WS + text SSE on the same conversation, or two browser
# tabs, or a reload mid-stream) all race on the same Session row. Without
# a lock, fetch → mutate → update_session writes overwrite each other:
# user message + model reply of the slower turn disappear.
#
# Multi-worker scale = swap this for a Postgres advisory lock (held on a
# dedicated connection for the whole step duration). Out of scope for the
# hackathon demo.

_SESSION_LOCKS: dict[str, asyncio.Lock] = {}


@asynccontextmanager
async def session_lock(session_id: str):
    """Async context manager: serialize concurrent step() calls per session.

    Holds an asyncio.Lock per session_id for the full body. Other turns on
    the same conversation queue rather than racing. The lock is held only
    in-process; multi-worker deployments need a Postgres advisory lock.
    """
    lock = _SESSION_LOCKS.setdefault(session_id, asyncio.Lock())
    async with lock:
        yield


def _row_to_session(row: dict[str, Any]) -> Session:
    pending_raw = row.get("pending_widgets") or []
    if isinstance(pending_raw, str):
        pending_raw = json.loads(pending_raw)
    pending = [PendingWidget(**w) for w in pending_raw]

    history = row.get("history") or []
    if isinstance(history, str):
        history = json.loads(history)

    active_doc = row.get("active_document_id")
    return Session(
        id=row["id"],
        citizen_id=str(row["citizen_id"]),
        state=SessionState(row["state"]),
        active_document_id=str(active_doc) if active_doc else None,
        scenario_id=row.get("scenario_id"),
        step_index=row.get("step_index"),
        pending_widgets=pending,
        history=history,
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )
