"""Session aggregate + state machine + persistence.

A `Session` is the agent's view of the world for a single conversation.
It owns the current state (exploring / confirming_match / filling /
reviewing / delivered / redirected), the active document id, the
conversation history (OpenAI chat messages serialized to JSON), and
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
import weakref
from collections.abc import AsyncIterator
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
    # The citizen confirmed the filled form in REVIEWING (migrations/015).
    review_confirmed: bool = False
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
    "step_index, pending_widgets, history, review_confirmed, created_at, updated_at"
)


def insert_session(
    citizen_id: str | UUID,
    session_id: str | None = None,
) -> Session:
    sid = session_id or new_session_id()
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"insert into sessions (id, citizen_id) values (%s, %s) "  # noqa: S608 — constant column list
            f"returning {_SELECT_COLS};",
            (sid, str(citizen_id)),
        )
        row = cur.fetchone()
        conn.commit()
    if row is None:
        raise RuntimeError("session insert returned no row")
    return _row_to_session(dict(row))


def fetch_session(session_id: str) -> Session | None:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"select {_SELECT_COLS} from sessions where id = %s;",  # noqa: S608 — constant column list
            (session_id,),
        )
        row = cur.fetchone()
    return _row_to_session(dict(row)) if row else None


class SessionOwnershipError(PermissionError):
    """A caller named a conversation that belongs to another citizen."""


def fetch_or_create_session(
    citizen_id: str | UUID, session_id: str | None = None
) -> Session:
    """If `session_id` is given AND exists, return it. Otherwise insert one.

    Raises SessionOwnershipError when the existing session belongs to a
    different citizen. `conversation_id` arrives from the client, and the
    session it names carries the history (profile values, filled fields) and
    the `citizen_id` every tool acts as — handing it to whoever asks would let
    one citizen read and drive another's conversation.
    """
    if session_id:
        existing = fetch_session(session_id)
        if existing is not None:
            if existing.citizen_id != str(citizen_id):
                raise SessionOwnershipError(
                    f"session {session_id} does not belong to this citizen"
                )
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
            "review_confirmed = %s, "
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
                session.review_confirmed,
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
    # Leaving REVIEWING invalidates any prior review confirmation — if the
    # user edits a field (REVIEWING -> FILLING) or starts over, they must
    # re-confirm the form before the delivery widget unlocks again.
    if session.state == SessionState.REVIEWING and to_state != SessionState.REVIEWING:
        clear_review_confirmed(session)
    session.state = to_state
    return session


class IllegalTransitionError(ValueError):
    """Raised when a state transition is not permitted."""


# ---- per-session lock ----
#
# Concurrent transports (voice WS + text SSE on the same conversation, two
# browser tabs, a reload mid-stream, or two backend replicas) all race on the
# same Session row: fetch → mutate → update_session writes overwrite each
# other and the slower turn's messages disappear.
#
# Two layers: an asyncio.Lock orders turns inside this process cheaply, and a
# Postgres advisory lock (held on its own connection for the whole turn)
# orders them across processes. The advisory lock is taken with
# pg_try_advisory_lock in a polling loop so waiting never ties up a thread
# or a pool connection. DISTRIBUTED_LOCKS=0 keeps only the in-process layer
# (unit tests without a database).

# Weak values: a lock disappears once no turn holds or awaits it, instead of
# one entry per conversation accumulating for the life of the process.
_SESSION_LOCKS: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()

SESSION_LOCK_TIMEOUT_SECONDS = 180.0


class SessionBusyError(TimeoutError):
    """Another turn held the conversation for longer than the timeout."""


@asynccontextmanager
async def _advisory_lock(key: str, wait_seconds: float) -> AsyncIterator[None]:
    import psycopg

    from app.config import get_settings

    conn = await psycopg.AsyncConnection.connect(get_settings().supabase_db_url, autocommit=True)
    try:
        deadline = time.monotonic() + wait_seconds
        delay = 0.02
        while True:
            cur = await conn.execute(
                "select pg_try_advisory_lock(hashtextextended(%s, 0));", (key,)
            )
            row = await cur.fetchone()
            if row and row[0]:
                break
            if time.monotonic() >= deadline:
                raise SessionBusyError(f"{key} is busy")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 0.5)
        try:
            yield
        finally:
            await conn.execute("select pg_advisory_unlock(hashtextextended(%s, 0));", (key,))
    finally:
        # Closing the connection also releases the lock if unlock failed.
        await conn.close()


# The review gate: set when the citizen answers Da to the confirm widget in
# REVIEWING, so neither agent can jump to the delivery picker without the
# citizen having looked at the filled form. Cleared when the session leaves
# REVIEWING (e.g. back to FILLING for an edit). Stored on the session row
# (migrations/015), so it holds across replicas and restarts.


def mark_review_confirmed(session: Session) -> None:
    session.review_confirmed = True


def is_review_confirmed(session: Session) -> bool:
    return session.review_confirmed


def clear_review_confirmed(session: Session) -> None:
    session.review_confirmed = False


def apply_review_confirmation(session: Session, widget: PendingWidget, value: Any) -> bool:
    """A Da on a confirm widget while REVIEWING is the go-ahead for delivery.

    Shared by the HTTP (/agent/widget-result) and voice WebSocket widget
    paths; the voice path used to skip it, so a voice-only citizen who
    confirmed the form was then refused the delivery step. True if it fired.
    """
    if (
        widget.type == "confirm"
        and session.state == SessionState.REVIEWING
        and str(value).strip().lower() in {"da", "true", "yes"}
    ):
        mark_review_confirmed(session)
        return True
    return False


@asynccontextmanager
async def session_lock(
    session_id: str, wait_seconds: float = SESSION_LOCK_TIMEOUT_SECONDS
) -> AsyncIterator[None]:
    """Serialize turns on one conversation, in this process and across replicas."""
    from app.config import get_settings

    lock = _SESSION_LOCKS.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _SESSION_LOCKS[session_id] = lock
    async with lock:
        if not get_settings().distributed_locks:
            yield
            return
        async with _advisory_lock(f"egata:session:{session_id}", wait_seconds):
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
        review_confirmed=bool(row.get("review_confirmed")),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )
