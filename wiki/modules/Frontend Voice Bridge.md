---
type: module
path: "frontend/lib/useVoiceAgentBridge.ts"
status: active
language: typescript
created: 2026-05-23
updated: 2026-05-23
---

# Frontend Voice Bridge

The hook that owns the live audio loop with the backend.

## Public surface

```ts
{
  state: "idle"|"connecting"|"listening"|"speaking"|"error",
  wsReady: boolean,        // WS open + Live ready
  micOn: boolean,           // mic capture running
  start(opts): Promise<void>,
  stop(): void,
  enableMic(): Promise<void>,
  disableMic(): void,
  sendText(text): Promise<void>,
  submitWidget(widgetId, value): Promise<void>,
  registerToolHandler(handler): void,
}
```

## Why `wsReady` and `micOn` are orthogonal

See [[ADR Single Live Session Text + Voice]]. `start()` opens the WS even for text-only sessions so a later mic-on doesn't require a reconnect.

## start() sequence

1. Get the JWT from `localStorage`.
2. Open `WebSocket(voiceWsUrl())`.
3. Send `{type:"start", token, document_id?, conversation_id?, preferences?}`.
4. Await `{type:"ready", conversation_id}` (resolves the `start()` Promise).
5. Open the audio player (`audioWorklet.startPlayer`).
6. Wire frame handlers → callbacks (`onUserDelta`, `onAgentDelta`, `onToolCall`, etc.).

The mic stays OFF until `enableMic()`.

## enableMic() sequence

1. `getUserMedia({audio: ...})` with constraints for 16kHz mono.
2. `audioWorklet.startMicRecorder(...)` — captures PCM16/16k chunks.
3. Each chunk → `ws.sendAudio(arrayBuffer)`.
4. On permission deny: throw `VoiceAgentMicDeniedError` → ChatSurface falls back to text.

## State machine

```
        ┌──── start() ────► connecting ─── ready ────► listening
idle ───┤                                                   │
        └──── voice in/out ─────► speaking ◄────────────────┘
                                          │ done speaking
                                          ▼
                                       listening
```

`error` is reachable from any state (auth fail, Live stream fail, mic deny).

## Tool handler injection

`registerToolHandler` exists for tests / extension points. In normal use the bridge calls the **backend** dispatcher (which dispatches via [[agent_tools]]); this client-side handler is a no-op pass-through.

## See also

- [[agent_voice]]
- [[Voice WS Frame Schema]]
- [[ADR Single Live Session Text + Voice]]
- [[Flow Voice Browser Turn]]
- frontend/lib/audioWorklet.ts
