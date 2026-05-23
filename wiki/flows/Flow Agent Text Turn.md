---
type: flow
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Flow: Agent Text Turn

End-to-end lifecycle of a single `POST /agent/chat/stream` SSE request.

## Sequence

```
Frontend (lib/sseChat.ts)             Backend (agent.py)               session_engine    Gemini       Tools
        │                                  │                                │              │            │
        │  POST /agent/chat/stream         │                                │              │            │
        │  { conversation_id, message,     │                                │              │            │
        │    document_id?, preferences? }  │                                │              │            │
        │─────────────────────────────────►│                                │              │            │
        │                                  │  acquire session_lock(conv_id) │              │            │
        │                                  │  _resolve_session              │              │            │
        │  event: conversation             │                                │              │            │
        │  data: {conversation_id}         │                                │              │            │
        │◄─────────────────────────────────│                                │              │            │
        │  event: session_snapshot         │  yield first snapshot          │              │            │
        │◄─────────────────────────────────│────────────────────────────────►              │            │
        │                                  │   for iter in range(5):        │              │            │
        │                                  │     build config (state-       │              │            │
        │                                  │      filtered function_decls)  │              │            │
        │                                  │     generate_content_stream   ─►              │            │
        │  event: delta                    │     ← chunk → accumulate text  │              │            │
        │  data: {text: cumulative}        │                                │              │            │
        │◄─────────────────────────────────│                                │              │            │
        │  event: delta ...                │                                │              │            │
        │◄─────────────────────────────────│                                │              │            │
        │                                  │   if function_call:            │              │            │
        │  event: tool_call                │     yield tool_call            │              │            │
        │◄─────────────────────────────────│     dispatch(...) ────────────────────────────────────────►│
        │  event: tool_result              │     yield tool_result          │              │           │
        │◄─────────────────────────────────│                                │              │            │
        │  event: frontend_event           │     yield frontend_event       │              │            │
        │  (document_opened / widget_      │                                │              │            │
        │   proposed / field_updated /...) │                                │              │            │
        │◄─────────────────────────────────│                                │              │            │
        │  event: session_snapshot         │     yield snapshot             │              │            │
        │◄─────────────────────────────────│                                │              │            │
        │                                  │     append function_response,  │              │            │
        │                                  │     continue loop              │              │            │
        │                                  │   else: break (text-only end)  │              │            │
        │  event: session_snapshot         │  yield final snapshot          │              │            │
        │◄─────────────────────────────────│                                │              │            │
        │  event: done                     │                                │              │            │
        │  data: {message, tool_calls}     │                                │              │            │
        │◄─────────────────────────────────│  update_session() in finally   │              │            │
```

## Frontend handlers

`streamChat(req, handlers)` ([[Frontend Lib]]) dispatches each frame:

- `conversation` → store the canonical id (POST may have sent `null`).
- `delta` → replace the "live" agent bubble's text (cumulative, not delta).
- `tool_call` / `tool_result` → optional UI breadcrumbs.
- `frontend_event` → drive UI mutations (navigate to `/r/<doc>`, render widget, mark field updated, ...).
- `session_snapshot` → replace the Zustand mirror IF `seq` is greater than the last applied one.
- `done` → finalize the bubble; stop the "agent typing" spinner.
- `error` → show a system bubble.

## Why the cumulative-text contract

The text accumulates across **tool-loop iterations**. After a `tool_call` runs, the next iteration may emit more text. We rebroadcast `transcript_so_far + this_iter_text` so the bubble never loses iter-1's preamble when iter-2 starts. The UI just replaces — no diff math.

## The 5-iteration ceiling

`_MAX_TOOL_LOOP_ITERATIONS = 5`. Caps a runaway tool loop. On exhaustion, the engine emits a `done` with whatever `transcript_so_far` is + a fallback message — preserving whatever the model emitted last instead of swallowing it.

## See also

- [[session_engine]]
- [[agent]]
- [[SSE Frame Schema]]
- [[Frontend Lib]]
