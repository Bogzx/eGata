---
type: flow
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Flow: Voice Browser Turn

Browser microphone → Gemini Live → browser speaker, with tool dispatch in the middle.

## Wire-level sequence

```
Browser (useVoiceAgentBridge)        Backend (agent_voice)                 Gemini Live          Tools
        │                                  │                                    │                  │
        │  WSS /agent/voice/ws             │                                    │                  │
        │ ────────────────────────────────►│                                    │                  │
        │  {type:"start", token, doc?,     │                                    │                  │
        │   conversation_id?, preferences} │  decode_token → citizen_id         │                  │
        │                                  │  fetch_or_create_session           │                  │
        │                                  │  build full system prompt          │                  │
        │                                  │  live.connect(model, config) ─────►│                  │
        │                                  │  send_client_content(history,      │                  │
        │                                  │    turn_complete=False)            │                  │
        │  {type:"ready", conv_id}         │                                    │                  │
        │◄─────────────────────────────────│                                    │                  │
        │  {type:"session_snapshot"...}    │                                    │                  │
        │◄─────────────────────────────────│                                    │                  │
        │                                  │                                    │                  │
        │  PCM16/16k mono chunks  ────────►│  send_realtime_input(Blob)  ──────►│                  │
        │  (recurring as user speaks)      │                                    │                  │
        │                                  │                                    │  audio out       │
        │                                  │                                    │   ── 24k PCM ───►│
        │  binary audio (24k PCM)         ◄│  ws.send_bytes                     │                  │
        │◄─────────────────────────────────│                                    │                  │
        │                                  │                                    │  transcript      │
        │  {type:"user_delta", text}      ◄│  input_transcription.text → buf    │                  │
        │  {type:"agent_delta", text}     ◄│  output_transcription.text → buf   │                  │
        │  {type:"user_done", text}       ◄│  flush on role switch              │                  │
        │  {type:"agent_done", text, tc}  ◄│                                    │                  │
        │                                  │                                    │  tool_call       │
        │  {type:"tool_call", name, args} ◄│  ◄────── function_calls list      │                  │
        │                                  │  dispatch(session, name, args) ───────────────────────►│
        │  {type:"tool_result"...}        ◄│  ◄ ToolResult                      │                  │
        │  {type:"frontend_event"...}     ◄│  if result.frontend_event          │                  │
        │  {type:"session_snapshot"...}   ◄│  after dispatch                    │                  │
        │                                  │  send_tool_response(responses, _state) ─►              │
        │                                  │                                    │  ... more audio  │
```

## Why a single WS instead of multiple

The voice hook ([[Frontend Voice Bridge]]) **opens the WS even for text-only sessions** so a later mic-on doesn't require a reconnect. WS readiness and mic on/off are orthogonal — see [[ADR Single Live Session Text + Voice]].

## Token in the start frame

Browsers cannot set `Authorization` on a WS upgrade. The token rides inside the first JSON frame; the bridge decodes it and rejects (`ws.close(4401)`) if invalid.

## State recap on every tool_response

Gemini Live freezes `system_instruction` at connect time. We can't refresh the "tools permitted" / "missing fields" preamble per turn the way the text path does. Workaround: every tool response carries a `_state` key with the current state, permitted tools, active doc, and applies_if-aware missing fields. The system prompt explicitly tells the model to consult `_state` instead of the (stale) preamble — see [[State Recap]] + [[agent_voice]]`._state_recap`.

## Why all 7 tools at connect

Same Live constraint — tools are locked at connect time. We send all 7 declarations; the dispatcher refuses out-of-state calls and returns an error result that the model can apologize about. See [[ADR State-Gated Tool Surface]].

## History rehydration

The voice session inherits any prior text-chat history. On connect, the bridge reads `session.history` (Gemini Content list), validates each entry, and pushes them via `send_client_content(turns, turn_complete=False)` — the model absorbs them but doesn't respond. The user's first spoken word continues the existing conversation.

## See also

- [[agent_voice]]
- [[Voice WS Frame Schema]]
- [[Frontend Voice Bridge]]
- [[State Recap]]
- [[ADR Shared Engine For Text + Voice]]
