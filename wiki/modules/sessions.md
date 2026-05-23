---
type: module
path: "backend/app/sessions.py"
status: active
language: python
purpose: "Session aggregate + state machine + persistence + per-conv lock."
depends_on: [db]
used_by: [agent, agent_voice, session_engine, agent_tools/*]
created: 2026-05-23
updated: 2026-05-23
---

# sessions

The data structure that **owns the conversation**. All transports speak through a `Session` object. State, document pointer, history, and pending widgets live here.

## Session dataclass

```python
@dataclass
class Session:
    id: str                        # "sess_..." or legacy "conv_..."
    citizen_id: str                # UUID as str
    state: SessionState
    active_document_id: str | None
    scenario_id: str | None
    step_index: int | None
    pending_widgets: list[PendingWidget]
    history: list[dict]            # Gemini Content list, JSON
    created_at, updated_at
```

`snapshot()` returns the wire-shape pushed to the FE — excludes `history` (too big and agent-internal), includes a monotonic `seq` for stale-snapshot detection.

## The six states

```
SessionState = exploring | confirming_match | filling | reviewing | delivered | redirected
```

See [[Flow Session State Machine]] for the full transition table. The `_TRANSITIONS` dict in this module is the source of truth.

## `transition(session, to)`

Raises `IllegalTransitionError` if the move isn't allowed. Used by [[agent_tools]] dispatcher and by [[agent]] when folding a legacy `document_id` injection.

## Persistence

| Function | Use |
|---|---|
| `insert_session(citizen_id, session_id?) → Session` | Creates a row in `sessions` |
| `fetch_session(session_id) → Session \| None` | Loads + rehydrates `pending_widgets` and `history` from jsonb |
| `fetch_or_create_session(...)` | The common path |
| `update_session(session)` | Persists state + active_document_id + scenario fields + pending_widgets + history. Bumps `updated_at`. |

Persistence happens **at the transport edge** — `session_engine.step()` mutates in place; [[agent]] and [[agent_voice]] do the `update_session()` in their `finally` blocks.

## `session_lock(session_id)` — the race fix

```python
async with session_lock(req.conversation_id):
    # all of step() runs here
```

In-process `asyncio.Lock` per session_id. Stops two concurrent turns on the same conversation (voice + text, two tabs, reload-during-stream) from racing on `session.history`. Multi-worker scale = swap for a Postgres advisory lock.

> [!gotcha] PendingWidget rehydration
> `pending_widgets` is stored as jsonb. On load, the module does `[PendingWidget(**w) for w in raw]`. Adding a field to `PendingWidget` without a migration breaks old rows — keep the dataclass forward-compatible or write a migration.

## See also

- [[ADR State Machine Over Free-Form Agent]]
- [[Session Aggregate]] — component view
- [[Session Snapshot Schema]]
- [[Flow Session State Machine]]
