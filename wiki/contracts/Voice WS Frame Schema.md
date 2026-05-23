---
type: contract
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Voice WS Frame Schema

`WSS /agent/voice/ws`. Bidirectional. Binary frames = audio. Text frames = JSON control messages.

## Audio

| Direction | Format |
|---|---|
| Browser → Backend | **PCM16, mono, 16 kHz** raw bytes |
| Backend → Browser | **PCM16, mono, 24 kHz** raw bytes |

The frontend uses an AudioWorklet (`frontend/lib/audioWorklet.ts`) to capture mic and play back agent audio.

## Client → Server JSON

| `type` | Fields | When |
|---|---|---|
| `start` | `{token, document_id?, conversation_id?, preferences:{simple_language, voice_only}}` | First frame. MUST contain a valid JWT — bridge closes with code 4401 otherwise. |
| `text` | `{text}` | Send a text-mode message through the same Live session (text-only callers do this). |
| `widget_submission` | `{widget_id, value}` | User clicked a widget. See [[Flow Widget Round-Trip]]. |
| `interrupt` | `{}` | Reserved for explicit barge-in UX. v1 no-op. |

## Server → Client JSON

| `type` | Fields | When |
|---|---|---|
| `ready` | `{conversation_id}` | Live is connected, tools registered, server ready to accept audio/text. |
| `session_snapshot` | `{snapshot: SessionSnapshot}` | After every state mutation (and at connect). See [[Session Snapshot Schema]]. |
| `user_delta` | `{text}` | Cumulative input transcription. |
| `user_done` | `{text}` | Final user transcript for this segment. |
| `agent_delta` | `{text}` | Cumulative agent output transcription. |
| `agent_done` | `{text, tool_calls}` | Final agent text for this turn. |
| `tool_call` | `{name, arguments}` | Right before dispatch. |
| `tool_result` | `{name, output}` | After dispatch. `output._state` is the [[State Recap]]. |
| `frontend_event` | `{event: FrontendEvent}` | Tool surfaced a UI directive. See [[Frontend Event Schema]]. |
| `interrupted` | `{}` | Server detected barge-in (Gemini Live `server_content.interrupted=true`). |
| `error` | `{detail}` | Auth failure, Live stream failure, etc. |

## The `start` frame

```json
{
  "type": "start",
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "document_id": "uuid (optional)",
  "conversation_id": "sess_xxx (optional)",
  "preferences": {
    "simple_language": false,
    "voice_only": false
  }
}
```

`token` is required. The bridge calls `decode_token(token)` ([[security]]) and rejects with code 4401 on any failure. **Browsers can't set `Authorization` on a WS upgrade** — see [[ADR Single Live Session Text + Voice]].

## Role-flip transcript flush

The Live API doesn't draw the line between turns the same way our UI does. The bridge tracks `last_role`:

- If `last_role` changes, emit a `user_done` / `agent_done` for the previous role's buffer.
- This is also what triggers `_persist_turn` — appending to `session.history` in memory.

## Close codes

| Code | Meaning |
|---|---|
| 1000 | Normal close. |
| 4401 | Token rejected in the `start` frame. |
| (any) | `_run_inner` exception → `error` frame, then close. |

## See also

- [[agent_voice]]
- [[Flow Voice Browser Turn]]
- [[voiceWs (frontend)]] — see [[Frontend Lib]]
