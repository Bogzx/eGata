---
type: component
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Session Aggregate

The conversation's single source of truth. See [[sessions]] for the dataclass + code.

## Owned state

| Field | Wire | Persisted |
|---|---|---|
| `id` | snapshot.id | text PK |
| `citizen_id` | snapshot.citizen_id | uuid |
| `state` | snapshot.state | text |
| `active_document_id` | snapshot.active_document_id | uuid \| null |
| `scenario_id` | snapshot.scenario_id | text \| null |
| `step_index` | snapshot.step_index | int \| null |
| `pending_widgets` | snapshot.pending_widgets | jsonb |
| `history` | (NOT in snapshot) | jsonb (Gemini Content list) |
| `created_at` / `updated_at` | — | timestamptz |

## Lifecycle

1. **Created** on the first `POST /agent/chat*` or first voice WS open. `fetch_or_create_session`.
2. **Mutated** by `session_engine.step()` (text) or `agent_voice` (voice) and by tool dispatchers.
3. **Persisted** at the transport edge (in `finally`), once per turn.
4. **Lifecycle** — never deleted. A "fresh start" is a new session with a new id.

## Two views

The same Session is read by:

- The text turn ([[Flow Agent Text Turn]]).
- The voice turn ([[Flow Voice Browser Turn]]).
- The HTTP `/agent/widget-result` endpoint ([[Flow Widget Round-Trip]]).

`session_lock(id)` serializes them. See [[sessions]]`.session_lock`.

## See also

- [[sessions]]
- [[Session Snapshot Schema]]
- [[Flow Session State Machine]]
