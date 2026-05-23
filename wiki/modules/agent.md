---
type: module
path: "backend/app/agent.py"
status: active
language: python
purpose: "Text transport — SSE wrapper around session_engine.step() + widget result endpoint."
depends_on: [agent_tools, citizens, models, security, session_engine, sessions]
used_by: [frontend/lib/sseChat.ts, frontend/lib/api.ts (submitWidget)]
created: 2026-05-23
updated: 2026-05-23
---

# agent

The text-mode transport. Adapts `session_engine.step()` events to SSE frames.

## Routes

| Route | Verb | Returns | Notes |
|---|---|---|---|
| `POST /agent/chat/stream` | SSE | `StreamingResponse` | The main path. Wrapped in `session_lock` for the conversation. |
| `POST /agent/widget-result` | JSON | `WidgetResultResponse` | Resolve a pending widget without round-tripping through Gemini. |
| `POST /agent/chat` | JSON | `AgentChatResponse` | Non-streaming. Kept for tests and programmatic callers. |

## How `_stream_turn` works

1. Acquire `session_lock(req.conversation_id)` — the lock IS the conversation lock.
2. `_resolve_session(req, citizen_id)` — fetch or create, fold in `req.document_id` (legacy injection path) if needed.
3. Read citizen attrs once.
4. `yield _sse("conversation", {conversation_id})` so the client knows the canonical id (it may have sent `null`).
5. `async for ev in step(...)`: yield each event as `event: <kind>\ndata: <json>\n\n`.
6. On exception: yield `event: error`.
7. **Always**: `update_session(session)` in `finally`.

## Why a separate `/widget-result`?

When the user clicks a widget, the answer is structured. Two reasons not to go through chat:

- The model would have to re-parse "Da" / "27.04.2026" / "proprietar" as plain text — error prone.
- We already know the `target_field` from `PendingWidget`. Why ask the model.

Two paths:

- **Direct path** (`target_field` set): dispatch `set_field` server-side, append a synthetic history line so the model has transcript continuity ("user clicked Y"), return the snapshot. `requires_chat_followup: false`.
- **Signal path** (no `target_field`, typical confirm widget in CONFIRMING_MATCH): the answer IS a signal the agent must react to. Return `requires_chat_followup: true`. The FE follows up via `/agent/chat/stream` with the user's answer as a chat turn.

## Why `_coerce_widget_value`

Confirm widgets carry `"Da"`/`"Nu"` or boolean. The coercer maps to literal `True`/`False` so the `set_field` validator on the procedure schema can decide. Choice/date keep raw type.

## See also

- [[Flow Agent Text Turn]]
- [[Flow Widget Round-Trip]]
- [[SSE Frame Schema]]
- [[sessions]]`.session_lock`
