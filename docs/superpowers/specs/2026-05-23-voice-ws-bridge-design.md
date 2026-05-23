# CivicAI Voice WS Bridge — Design

**Status:** Draft for implementation
**Date:** 2026-05-23
**Owners:** Bogdan + team
**Builds on:** `docs/superpowers/specs/2026-05-23-chat-first-redesign-design.md`, `backend/app/twilio_bridge.py` (reference implementation)
**Demo:** 2026-05-24

---

## 1. Goal

Move the Gemini Live voice path from a browser-direct WebSocket (with the raw API key shipped to the client) to a backend bridge that:

1. **Holds the Gemini API key server-side** — kills the public-key leak in `voice.py:193` / `gemini-live.ts:127`.
2. **Unifies voice and text conversation history** — voice turns land in the same `_conversations[conv_id]` the text agent already uses; switching modes mid-conversation preserves context.
3. **Executes tools in-process** — Gemini's `toolCall` is handled directly by the existing `REGISTRY` + `ToolContext`, removing the JWT-mint / HTTPS / FIFO-race surface (audit bugs B-5, B-NEW-B, B-NEW-J).
4. **Streams the live transcript as the message itself** — input/output transcription partials arrive from Gemini Live and update a real chat message in place, not a separate "pending" bubble; no external STT.

The text chat path (`POST /agent/chat/stream`, SSE) is left untouched. Only the voice path migrates.

## 2. Constraints

- **Demo eve.** Ship is 2026-05-24. New code must be feature-flagged so we can revert to the existing direct-WS path if the bridge misbehaves during demo prep.
- **No regressions in the text path.** `agent.py:_stream_agent_turn`, `sessionStore.sendText`, and the SSE frame vocabulary stay exactly as they are.
- **Romanian UI strings stay Romanian.**
- **Surgical changes only.** Reuse `twilio_bridge.py:104-206` (`_run_phone_gemini_session`) shape; reuse `prompts.build_system_prompt(variant="conversational")`; reuse `tools.REGISTRY` + `ToolContext`.
- **No tests gating ship.** Note testable seams; write tests post-demo. (Open question C resolved.)

## 3. Non-goals

- Migrating text chat to WS. Keep SSE.
- Auto-reconnect on WS drop. v1 surfaces an error + manual retry. (Open question B resolved.)
- Optimistic UI on tool calls. v1 paints widget/field updates only after `tool_result`. (Open question A resolved.)
- Persistent server-side conversation store (Redis/SQLite). Process-local `_conversations` stays — bumped cap covered in the audit's B-12 fix.
- Deleting `voice.py` / `gemini-live.ts` / `useVoiceAgent.ts`. They remain as the fallback path behind `NEXT_PUBLIC_VOICE_BRIDGE` until post-demo.

## 4. Architecture

```
Browser                              FastAPI Backend                          Google
─────────                            ────────────────                          ─────────

Composer ──text───────►  POST /agent/chat/stream (SSE) ─────►  generate_content_stream
                                                                (unchanged)

ChatSurface
  └─voice mode─►  WS /agent/voice/ws ────────►  VoiceBridgeSession
                  ◄── JSON control frames ◄──   ├─ holds client.aio.live.connect()
                  ◄── binary PCM24 audio ◄──    ├─ shares _conversations[conv_id]
                                                ├─ ToolContext(citizen, doc)
AudioWorklet                                    └─ in-process REGISTRY dispatch
  mic ──PCM16 16kHz binary──►                                 │
                                                              ▼
                                                       Gemini Live (server-side WS)
```

One bridge session per browser WS. Lifetime = mic-on to mic-off (or disconnect).

## 5. Frame protocol

Control frames are JSON text. Audio frames are binary (raw PCM bytes, no base64 — saves ~33% bandwidth vs the current direct-WS approach).

### 5.1 Client → Server

| Type | Shape | Notes |
|---|---|---|
| `start` | `{"type":"start","document_id":"...","preferences":{"simple_language":bool,"voice_only":bool},"conversation_id":"..."?}` | First frame after WS open. `conversation_id` optional — bridge falls back to generating one. |
| `text` | `{"type":"text","text":"..."}` | User typed during voice mode. Bridge forwards to Gemini as `client_content`. |
| `interrupt` | `{"type":"interrupt"}` | Manual barge-in. (Optional in v1; design hook included.) |
| *(binary)* | raw PCM16 mono 16kHz bytes | Mic chunks. Bridge wraps each in `Blob(mime_type="audio/pcm;rate=16000")` and calls `session.send_realtime_input(audio=...)`. |

### 5.2 Server → Client

| Type | Shape | Notes |
|---|---|---|
| `ready` | `{"type":"ready","conversation_id":"..."}` | Sent after Gemini Live setup-complete. |
| `user_delta` | `{"type":"user_delta","text":"<full accumulated>"}` | Input-transcription partials. Frontend mutates the live user message in place. |
| `user_done` | `{"type":"user_done","text":"<final>"}` | End-of-user-turn boundary. Bridge persists this turn to `_conversations`. |
| `agent_delta` | `{"type":"agent_delta","text":"<full accumulated>"}` | Output-transcription partials. Frontend mutates the live agent message. |
| `agent_done` | `{"type":"agent_done","text":"<final>","tool_calls":[...]}` | End-of-agent-turn boundary. Bridge persists to `_conversations`. |
| `tool_call` | `{"type":"tool_call","name":"...","arguments":{...}}` | Mirrors text-SSE vocab so frontend can reuse `applyToolResult`. |
| `tool_result` | `{"type":"tool_result","name":"...","output":{...}}` | Same. Includes `error` key on failure (per audit B-5 fix sketch). |
| `interrupted` | `{"type":"interrupted"}` | From Gemini `server_content.interrupted`. Frontend calls `player.flush()`. |
| `error` | `{"type":"error","detail":"..."}` | Bridge or Gemini fatal. Frontend shows Romanian error bubble; user can re-open mic. |
| *(binary)* | raw PCM16 mono 24kHz bytes | Agent audio. Frontend feeds into existing `PlayerHandle`. |

### 5.3 Why accumulated text per delta (not incremental)

The text SSE path already emits `delta` with the *full accumulated text* (`agent.py:404`). Frontend `sessionStore.applyDelta` replaces — not appends. The WS path follows the same convention so frontend code paths converge.

## 6. Backend

### 6.1 New module: `backend/app/agent_voice.py`

Single file, modeled on `twilio_bridge.py`. Key components:

- **`router = APIRouter(prefix="/agent", tags=["voice"])`** — registered in `app/main.py` next to the existing `voice.router`.
- **`@router.websocket("/voice/ws")`** — accept, auth via cookie (`current_citizen_id` resolved from the upgrade request's cookies), spawn the bridge session.
- **`VoiceBridgeSession` class** — owns:
  - `ws: WebSocket` (browser)
  - `gemini_session` (`client.aio.live` session, set up inside `async with`)
  - `conv_id: str`
  - `tool_ctx: ToolContext`
  - `user_buf: str`, `agent_buf: str`, `agent_tool_calls: list`
  - `inbound_audio_queue: asyncio.Queue[bytes | None]` (mic chunks)
  - Three concurrent tasks (started via `asyncio.gather`):
    - `pump_mic_to_gemini` — drain `inbound_audio_queue` into `session.send_realtime_input`.
    - `pump_gemini_to_client` — `async for response in session.receive()`: decode `response.data` (audio out → ws binary), `response.server_content.input_transcription` (→ `user_delta`), `response.server_content.output_transcription` (→ `agent_delta`), `response.server_content.turn_complete` (→ `*_done` + persist + reset bufs), `response.tool_call` (→ in-process dispatch → `send_tool_response`), `response.server_content.interrupted` (→ ws `interrupted`).
    - `pump_client_to_bridge` — `await ws.receive()`: binary → mic queue; text → parse JSON, route by `type`.
- **Tool dispatch**: lifted from `twilio_bridge.py:154-201`. No allowlist (browser path gets the full registry). On error, emit a `tool_result` frame with `{"error": "..."}` AND send the same error structure back to Gemini so the model can apologize verbally.
- **History seed**: on `start` frame, look up `_conversations[conv_id]` (from `agent.py:_conversations`) and pass as initial `client_content.turns` so voice has full text-chat context.
- **Persistence**: on each `*_done`, append `Content(role="user"/"model", parts=[Part.from_text(...)])` to `_conversations[conv_id]` via the existing `_remember` helper.

### 6.2 LiveConnectConfig

```python
config = genai_types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    system_instruction=build_system_prompt(
        variant="conversational",
        simple_language=prefs.simple_language,
        voice_only=prefs.voice_only,
    ) + citizen_doc_preamble,            # same preamble logic as voice.py:160-183
    tools=[{"function_declarations": _BROWSER_FUNCTION_DECLS}],
    speech_config=genai_types.SpeechConfig(
        voice_config=genai_types.VoiceConfig(
            prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                voice_name=settings.gemini_voice_name,
            )
        ),
        language_code="ro-RO",
    ),
    input_audio_transcription=genai_types.AudioTranscriptionConfig(),
    output_audio_transcription=genai_types.AudioTranscriptionConfig(),
)
```

`_BROWSER_FUNCTION_DECLS` is hand-written in the same shape as `twilio_bridge._PHONE_FUNCTION_DECLS`. Initial set mirrors the 7 tools from `useVoiceAgent.ts:65-156`. We hand-write the declarations rather than reusing `TOOL_SCHEMAS` from the frontend so the bridge has no frontend dependency.

⚠️ **Setup payload is fragile.** Recent commit `ffbb833 fix(voice): revert risky Live setup fields` and the comment at `gemini-live.ts:142` document this. If the Python SDK silently rejects any field (e.g. `language_code` placement, transcription config keys), the session looks dead with no error. Implementation must log the raw setup and the first `session.receive()` event explicitly.

### 6.3 Authentication

WS upgrades carry cookies. FastAPI exposes them on `websocket.cookies`. Reuse `app.security.current_citizen_id` logic: resolve the citizen from the session cookie; if unauthenticated, `await ws.close(code=4401)` before accepting.

No tool JWT, no `tool_base_url`, no `/voice/session` HTTP call. The bridge IS the trust boundary.

### 6.4 Shared conversation history

`_conversations` lives in `agent.py:146-155`. Both the text agent and the voice bridge import it as `from app.agent import _conversations, _remember`. Single source of truth.

**Mode-switch semantics:**
- Voice → text: text path reads `_conversations[conv_id]` and prepends as today (`agent.py:360`).
- Text → voice: bridge reads `_conversations[conv_id]` on `start` and seeds Gemini Live with all prior turns as `client_content` (no `turn_complete`) so the model has context without generating a response.

### 6.5 No tool JWT path

Tool-dispatch HTTP endpoints (`/tools/*`) and `issue_tool_jwt` / `verify_tool_jwt` remain — the old direct-WS path uses them. New bridge does not. No security implications either way; the endpoints already require a valid JWT.

## 7. Frontend

### 7.1 New module: `frontend/lib/voiceWs.ts`

Thin WebSocket client. ~150 lines.

```typescript
export type VoiceWsHandlers = {
  onReady: (convId: string) => void;
  onUserDelta: (text: string) => void;
  onUserDone: (text: string) => void;
  onAgentDelta: (text: string) => void;
  onAgentDone: (text: string, toolCalls: AgentToolCall[]) => void;
  onToolCall: (name: string, args: Record<string, unknown>) => void;
  onToolResult: (name: string, output: Record<string, unknown>) => void;
  onAudio: (pcm: ArrayBuffer) => void;
  onInterrupted: () => void;
  onError: (detail: string) => void;
  onClose: () => void;
};

export class VoiceWs {
  connect(url: string): Promise<void>;
  sendStart(payload: StartPayload): void;
  sendText(text: string): void;
  sendAudio(chunk: ArrayBuffer): void;  // binary frame
  sendInterrupt(): void;
  close(): void;
}
```

URL: `ws://<host>/agent/voice/ws` (or `wss://` in prod). Cookies travel automatically with the upgrade.

`ws.binaryType = "arraybuffer"`. Inbound: branch on `event.data` type — binary → `onAudio`, string → `JSON.parse` → branch on `type`.

### 7.2 New hook: `frontend/lib/useVoiceAgentBridge.ts`

Drop-in replacement for `useVoiceAgent` with the same `VoiceAgentHook` interface (`state`, `start`, `stop`, `sendText`, `registerToolHandler`). Internally:

- `start(opts)`:
  1. `setState("connecting")`.
  2. `const ws = new VoiceWs(); await ws.connect("/agent/voice/ws");`
  3. `ws.sendStart({document_id, preferences, conversation_id})`.
  4. Wait for `onReady` → `setState("listening")`.
  5. `const player = await startPlayer(); const recorder = await startMicRecorder(chunk => ws.sendAudio(chunk));`
- Handler wiring matches the existing `useVoiceAgent` semantics so `ChatSurface` doesn't change its consumption logic.
- `registerToolHandler` is still exposed so `applyToolResult` runs on `onToolResult` — but the side-effect callback no longer fires HTTP from the browser. It only updates the right-pane reflective state.

### 7.3 sessionStore changes

Currently the voice path uses `pendingUser` / `pendingAgent` placeholders that get promoted into real messages on `onUserMessage` / `onAgentMessage`. The new model: **the transcript is the message from the first delta**.

New actions:

```typescript
// lib/sessionStore.ts
beginLiveUserMessage(): string;        // returns messageId; appends an empty {role:"user", live:true} Message
updateLiveUserMessage(id, text);       // mutates Message.text; persists
finalizeLiveUserMessage(id, text);     // clears live flag; persists
beginLiveAgentMessage(): string;       // analogous for agent
updateLiveAgentMessage(id, text);
finalizeLiveAgentMessage(id, text, toolCalls);
```

Message type gains an optional `live?: boolean` flag. ChatStream renders `live: true` with a subtle indicator (e.g., a thin pulsing border or trailing caret) but otherwise as a normal message — no separate styled "pending" bubble.

`useVoiceAgentBridge` calls `beginLiveUserMessage` on first `user_delta`, `updateLiveUserMessage` on subsequent deltas, `finalizeLiveUserMessage` on `user_done`. Same for agent.

**Side effect**: voice transcripts are persisted to `localStorage` immediately (via the existing `saveMessages` autosave), so a refresh mid-utterance keeps what the user just said.

### 7.4 ChatSurface wiring

Add an env-gated hook switch:

```typescript
const useVoice =
  process.env.NEXT_PUBLIC_VOICE_BRIDGE === "1"
    ? useVoiceAgentBridge
    : useVoiceAgent;
const voice = useVoice();
```

Everything else (auth, mode toggle, `onSendText`, `onWidgetSubmit`) is untouched. The hook's external contract is preserved.

## 8. Migration & rollback

### 8.1 Feature flag

- `NEXT_PUBLIC_VOICE_BRIDGE=1` → new path (bridge).
- `NEXT_PUBLIC_VOICE_BRIDGE=0` or unset → old path (direct WS).

Default during the demo prep window: **`0`** until the bridge has been smoke-tested. Flip to `1` once verified.

### 8.2 What stays

`voice.py` (HTTP endpoints, JWT helpers, `/voice/session`), `gemini-live.ts`, `useVoiceAgent.ts`, `/tools/*` endpoints. All untouched. Old code path remains a one-flag-flip escape hatch.

### 8.3 What's added

- `backend/app/agent_voice.py` (new)
- `frontend/lib/voiceWs.ts` (new)
- `frontend/lib/useVoiceAgentBridge.ts` (new)
- `frontend/lib/sessionStore.ts` — new live-message actions, `live?: boolean` field on `Message` type
- `frontend/components/chat/ChatStream.tsx` — small render branch for `live: true` messages
- `frontend/components/chat/ChatSurface.tsx` — env-gated hook switch
- `backend/app/main.py` — register the new WS router
- `.env.example` / `.env.local` — document `NEXT_PUBLIC_VOICE_BRIDGE`

### 8.4 What's removed

Nothing in v1. Post-demo: delete the four files above + the JWT machinery + `/voice/session`.

## 9. Risk & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| `client.aio.live` Python SDK doesn't expose `input_audio_transcription` / `output_audio_transcription` on `LiveConnectConfig` | Low (Twilio bridge proves Live works, but doesn't currently use transcription) | Spike at start of implementation: connect and print one `response.server_content` to confirm field names. If missing, fall back to no live transcript (final text only) — log open issue. |
| Setup payload silently rejected (the historical footgun) | Medium | Mirror `twilio_bridge.py` config exactly where shared; log the raw setup; assert `session.receive()` yields *something* within 5s or `ws.close(4500)`. |
| Cookie auth on WS upgrade fails (CORS / SameSite quirks) | Medium | Test against the actual `frontend` dev origin early. Fallback: short-lived auth token in WS subprotocol header. |
| Backend audio relay adds noticeable latency | Low (EU-hosted backend, <50ms added RTT) | Measure end-to-end latency in demo prep. If >300ms total, defer to direct path via flag. |
| `_conversations` collisions between voice and text in concurrent flows | Low (single user per conv_id) | Per-conv_id `asyncio.Lock` around `_remember` writes. |
| Tool errors over voice not surfaced to user (audit B-NEW-J) | Resolved by design | `tool_result` frame with `error` key + `applyToolResult` handles it. |
| Implementation runs past demo prep window | Medium | Feature flag default `0` → flip to `1` only when bridge works. Demo can ship on old path if needed (with the API key leak; demo URL not publicly indexed). |

### 9.1 Time budget

| Phase | Estimate |
|---|---|
| Backend bridge (`agent_voice.py`) + WS router registration | 1.5h |
| Manual smoke test (audio in/out, transcripts, one tool call) | 0.5h |
| Frontend `voiceWs.ts` + `useVoiceAgentBridge.ts` | 1.5h |
| sessionStore live-message actions + ChatStream render | 1h |
| ChatSurface env switch + .env wiring | 0.5h |
| Browser end-to-end smoke (full happy path) | 1h |
| Buffer for SDK / setup-payload quirks | 1.5h |
| **Total** | **~7.5h** |

## 10. Testable seams (post-demo)

- `VoiceBridgeSession.handle_gemini_response(response)` — pure function on a single Gemini response object. Unit-testable with a fixture stream.
- `VoiceWs.dispatchFrame(frame)` — same idea on the frontend; pure routing.
- `sessionStore.{begin,update,finalize}Live{User,Agent}Message` — exercise via Zustand test harness.
- Tool dispatch in the bridge: parameterized over `REGISTRY` lookup — substitute a fake registry in tests.

No tests written in v1.

## 11. Open questions

All three from brainstorming were defaulted; revisit post-demo:
- **A** (optimistic UI on tool calls): no — accept paint-on-result for v1.
- **B** (WS drop handling): manual retry only — no auto-reconnect/text-fallback for v1.
- **C** (tests): note seams above; no tests gating ship.

Additional questions surfaced during design — none blocking, all post-demo:
- Should voice transcripts persist into the server-side `_conversations` as `Part.from_text` or as a richer `Part` that marks them as voice-originated? v1: plain text, indistinguishable from typed turns.
- Should `live: true` messages show a typing indicator (existing dots) or a different affordance? v1: thin pulsing border on the bubble (minimal CSS), no dots.
- Should the bridge auto-close after N seconds of mic silence to conserve Gemini Live quota? v1: no — close on user action only.

---

End of design.
