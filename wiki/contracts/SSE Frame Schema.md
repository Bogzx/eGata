---
type: contract
status: active
created: 2026-05-23
updated: 2026-05-23
---

# SSE Frame Schema

`POST /agent/chat/stream` returns `text/event-stream`. Each frame is `event: <type>\ndata: <json>\n\n`.

## Vocabulary

| `event:` | `data:` JSON | When |
|---|---|---|
| `conversation` | `{conversation_id}` | First frame after lock acquisition. Tells the client the canonical id (POST may have sent `null`). |
| `delta` | `{text: cumulative}` | Agent text grew. Carries the FULL accumulated text since turn start — UI just replaces. |
| `tool_call` | `{name, arguments}` | Model emitted a function_call. |
| `tool_result` | `{name, output, error}` | Dispatcher returned. |
| `frontend_event` | `FrontendEvent` shape | A tool surfaced a UI directive. See [[Frontend Event Schema]]. |
| `session_snapshot` | `SessionSnapshot` | Pushed after every state mutation. See [[Session Snapshot Schema]]. |
| `done` | `{conversation_id, message, tool_calls}` | Terminal happy frame. |
| `error` | `{detail}` | Terminal sad frame. Engine crashed or Gemini failed. |

## Parser (FE)

`frontend/lib/sseChat.ts:parseFrames` splits on blank lines (handles both `\n\n` and `\r\n\r\n`). Reads `event:` and `data:` lines; the rest of `dataLines` is joined with `\n`. Trailing partial frames stay in the buffer until the next chunk arrives.

## Why `delta` carries cumulative text

The text accumulates across tool-loop iterations. After a `tool_call`, iter 2 may emit more text. By rebroadcasting `transcript_so_far + iter_text`, the bubble never loses iter-1's preamble. The UI does `setText(payload.text)` — no diff math.

> [!gotcha] Don't append `delta.text` to your local buffer
> It's the FULL text, not the increment. Append-by-mistake doubles every chunk.

## SSE-specific headers

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

`X-Accel-Buffering: no` defeats nginx/proxy buffering — without it, `delta` events arrive in a clump after the full turn.

## See also

- [[agent]]
- [[session_engine]] — Event taxonomy
- [[Frontend Event Schema]]
- [[Session Snapshot Schema]]
