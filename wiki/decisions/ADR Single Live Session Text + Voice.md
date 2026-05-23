---
type: decision
status: active
created: 2026-05-23
updated: 2026-05-23
---

# ADR: Single Live Session Text + Voice

## Decision

The frontend opens **one Gemini Live WebSocket per chat session**, even when the user is in text-only mode. Mic on/off is decoupled from WS open/close.

## Why

- A user typing can switch to voice mid-conversation. With separate connections, that's "tear down text + open WS + re-seed history + wait for Live ready" — a 2–3 second hiccup.
- Sharing the WS means the agent's context (session.history seeded into Live) is already there. Mic-on is instant.
- One WS = one session_lock holder = no races between "text turn" and "voice turn" on the same conversation.

## Implementation

`useVoiceAgentBridge` ([[Frontend Voice Bridge]]) has two orthogonal booleans:

- `wsReady` — Gemini Live is connected, system prompt sent, history rehydrated.
- `micOn` — actual mic capture is running.

Text-only callers do `start()` to get `wsReady=true` with `micOn=false`. Mic-on later is just `enableMic()`. See `frontend/lib/useVoiceAgentBridge.ts`.

The backend doesn't care — the WS sees `{type:"text", text:"..."}` frames or audio frames interchangeably. Live handles both.

## Token in the start frame

Browsers cannot set `Authorization` on a WS upgrade. The token is the first thing in the JSON `start` frame; bridge calls `decode_token(token)` and rejects (`ws.close(4401)`) on failure. Frame schema: [[Voice WS Frame Schema]].

## Cost

- The frontend always pays the WS open cost on chat init, even if the user never talks.
- Backend always pays the Gemini Live connect cost. Live charges per session-time anyway, so this is real.
- Mitigation: only open the WS once `wsReady` is needed (lazy `start()` in `ChatSurface`).

## See also

- [[Frontend Voice Bridge]]
- [[agent_voice]]
- [[ADR Shared Engine For Text + Voice]]
