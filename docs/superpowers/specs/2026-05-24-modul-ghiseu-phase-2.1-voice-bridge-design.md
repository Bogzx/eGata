# Modul Ghișeu — Phase 2.1: Voice Bridge Integration (Design)

**Date:** 2026-05-24
**Status:** Approved for plan generation
**Roadmap parent:** `docs/superpowers/plans/2026-05-24-modul-ghiseu-phase-2-integration.md`
**Phase 1 spec:** `docs/superpowers/specs/2026-05-24-modul-ghiseu-design.md`

---

## Goal

Replace the scripted `setTimeout` flow in `frontend/lib/ghiseuStore.ts` with real wiring into `useVoiceAgentBridge`, so that on `/ghiseu` the user actually talks to the AI: live transcripts stream into the `Tu` / `eGata` bubbles, the agent's voice plays back, and `Întrerupe` cuts the agent off via a real backend frame.

Phase 2.1 is **voice-IO-only**. The agent can run a procedure to completion server-side (because `start_procedure` → `document_opened` still loads doc data into `sessionStore`), but the kiosk's `DocumentReview` and `DoneScreen` keep their static sample data until Phase 2.2 / 2.3 land.

---

## In scope

- Real voice in/out on `/ghiseu` via the existing `useVoiceAgentBridge`.
- Live partial transcripts streamed into a new `caption: { user, agent }` field on `ghiseuStore`.
- `Întrerupe` button calls a new `interrupt()` method on `VoiceAgentHook` that sends the existing `{type: "interrupt"}` WS frame.
- Auto-engage voice mode on `/ghiseu` mount (kiosk is voice-first).
- New `kioskMode` flag on `sessionStore` to short-circuit `pushPath()` so agent-triggered navigation (`start_procedure`, `redirect`) does not pull the user off `/ghiseu`.

## Out of scope (deferred)

- `DocumentReview` reading real `activeDocument` / `activeProcedure` from the store — **Phase 2.2**.
- `DoneScreen` real `ref_number` — **Phase 2.2**.
- `ExportOptions` making a real `POST /documents/{id}/deliver` (or new `/submit`) call — **Phase 2.3**.
- Mic-denied recovery button, WS reconnect button, tab-visibility pause, telemetry, e2e Playwright test, axe audit, memory-leak check — **Phase 2.4**.
- Refactor of `useVoiceAgentBridge` to multi-subscriber pub-sub — **not needed**. Because `/` and `/ghiseu` are different routes and only one is mounted at a time, surface-owned `voice.start()` + `voice.stop()` at mount/unmount is sufficient.

---

## State-mapping recap (from roadmap, scoped to 2.1)

| `GhiseuState` | Source(s) of truth | When to enter |
|---|---|---|
| `idle` | Local (initial / post-reset) | Page load with no engaged voice; after `reset()` |
| `listening` | `voice.state === "listening"` AND `voice.micOn === true` | After `enterVoiceMode()` resolves and mic permission granted |
| `thinking` | Derived: `onUserMessage` fired, no `onAgentDelta` within 300ms | Brief gap between user finishing and agent starting. Skipped if agent's first chunk arrives within window. |
| `speaking` | `onAgentDelta` fired (first chunk) | Agent audio is streaming |
| `error` | `voice.state === "error"` OR `voice.start()` rejection | WS dropped, network failure, handshake fail |
| `mic-denied` | `enableMic()` rejects with `VoiceAgentMicDeniedError` | Browser denies mic permission |
| `review`, `export`, `done` | Still set by legacy actions (`confirmDoc`, `pickExport`) | Driven by user clicks on the still-stubbed review/export screens; Phase 2.2 / 2.3 will rewire these to session events |

---

## Architecture decisions

### D1. Bridge ownership: surface-owned start/stop (no pub-sub refactor)

`VoiceProvider` mounts `useVoiceAgentBridge` once at root layout. Both `ChatSurface` (`/`) and `GhiseuShell` (`/ghiseu`) consume the same hook via `useVoiceContext()`. Because Next.js only mounts one route surface at a time, the contention risk is limited to a stale WS surviving a route change.

**Decision:** The store splits "wiring" from "starting":

- `attachVoiceBridge(bridge)` stores the bridge reference on the store and returns a cleanup that calls `bridge.stop()` and clears the reference. No WS work happens here.
- `enterVoiceMode()` uses the stored bridge to call `bridge.start({…callbacks})` + `bridge.enableMic()` in parallel. Defensively calls `bridge.stop()` first if `bridge.wsReady === true` to evict a leftover session from `/`.
- `GhiseuShell` calls `attachVoiceBridge(voice)` once on mount and `enterVoiceMode()` once `citizen` is hydrated. Unmount cleanup runs `bridge.stop()` via the attach-cleanup.

Rejected: multi-subscriber pub-sub refactor of `useVoiceAgentBridge`. Adds complexity for zero current benefit since the two surfaces never coexist.

### D2. Caption data source: callback-driven, not sessionStore-subscribed

`useVoiceAgentBridge.start(opts)` already accepts `onUserDelta` / `onAgentDelta` / `onUserMessage` / `onAgentMessage`. The kiosk passes these directly so the events land in `ghiseuStore.caption` without going through `sessionStore.messages` (which the kiosk doesn't render anyway).

Rejected: subscribing to `sessionStore.messages` and pulling the latest live message. Indirect, and `sessionStore.messages` is used by the chat surface for things the kiosk doesn't care about.

### D3. Kiosk navigation suppression: single-line `pushPath` guard

`pushPath` in `sessionStore.ts` is the only place that calls `_navigate(path)`. A new `kioskMode: boolean` flag on the store, checked at the top of `pushPath`, short-circuits navigation when `true`. `GhiseuShell` sets the flag on mount and clears it on unmount.

Rejected: `usePathname()`-based detection inside store logic (couples store to URL conventions); per-surface navigate injection (over-flexible).

### D4. `Întrerupe` exposed via new `interrupt()` method on `VoiceAgentHook`

`voiceWs.sendInterrupt()` already exists and the backend already handles `{type: "interrupt"}` frames (`backend/app/agent_voice.py:660`). The hook surface just doesn't expose it. We add `interrupt(): void` to `VoiceAgentHook`, implemented as `wsRef.current?.sendInterrupt()`; throws if WS not started.

`ghiseuStore.interrupt()` calls `voice.interrupt()` and optimistically sets `state="listening"` for snappy UI; the backend's `interrupted` echo (which arrives ~50ms later) sets the same state via the existing `onInterrupted` handler — idempotent.

### D5. Reset is unmount-equivalent; auto-engage only on first mount

`reset()` calls `voice.stop()`, clears caption, sets `state=idle`. The user must click the mic to re-engage. Route-change unmount also runs `reset()` so a return to `/ghiseu` starts fresh.

Rationale: a kiosk is a single-session model. There's no "remember where we were" expectation.

### D6. The "thinking" state is debounced

`onUserMessage` schedules a `setTimeout(300ms)` to transition to `thinking`. `onAgentDelta` cancels the pending transition and goes straight to `speaking`. The flash only appears when there's a genuine pause.

300ms chosen empirically: short enough that even a 200ms pause feels "live", long enough that fast TTS doesn't cause a visible flash.

---

## Store shape

```ts
// frontend/lib/ghiseuStore.ts
type Line = { text: string; live: boolean };

type GhiseuStore = {
  state: GhiseuState;
  muted: boolean;             // mirror of voice.micOn (kept in sync by a one-line effect in GhiseuShell)
  exportMethod: ExportMethod;
  caption: { user: Line | null; agent: Line | null };

  // internal bridge reference (set by attachVoiceBridge; read by lifecycle actions)
  _bridge: VoiceAgentHook | null;

  // event handlers (passed as opts to bridge.start; invoked by the bridge)
  appendUserPartial(text: string): void;
  commitUserMessage(text: string): void;   // schedules thinking-transition with 300ms debounce
  appendAgentPartial(text: string): void;  // cancels pending thinking, sets state=speaking
  commitAgentMessage(text: string): void;  // sets state=listening, marks agent line non-live

  // lifecycle
  attachVoiceBridge(bridge: VoiceAgentHook): () => void;  // stores ref, returns cleanup that stops + nulls
  enterVoiceMode(): Promise<void>;          // uses _bridge to start + enableMic in parallel
  exitVoiceMode(): void;                    // uses _bridge to stop (no-op if not started)
  interrupt(): void;                        // uses _bridge to send interrupt frame
  setMuted(muted: boolean): void;           // setter so GhiseuShell can mirror voice.micOn

  // existing surface (unchanged signatures, but bodies updated per Mapping table)
  setState(state: GhiseuState): void;
  toggleMute(): void;        // idle → re-enters voice mode; otherwise toggles _bridge.disableMic / enableMic
  confirmDoc(): void;
  amendDoc(): void;
  pickExport(method: Exclude<ExportMethod, null>): void;
  backToTalk(): void;
  reset(): void;             // calls exitVoiceMode + clears caption + state=idle
};
```

## Voice event → store action mapping

| Voice callback / state | Store side-effect |
|---|---|
| `onUserDelta(text)` | `caption.user = { text, live: true }` |
| `onUserMessage(text)` | `caption.user = { text, live: false }`; schedule `setTimeout(300)` → `state=thinking` |
| `onAgentDelta(text)` | cancel pending thinking-timer; `caption.agent = { text, live: true }`; `state=speaking` |
| `onAgentMessage(text)` | `caption.agent = { text, live: false }`; `state=listening` |
| `voice.state === "error"` | `state=error` |
| `voice.state === "connecting"` | no change (transient) |

## sessionStore additions

```ts
// frontend/lib/sessionStore.ts
type SessionStore = {
  // ...existing
  kioskMode: boolean;
  setKioskMode(on: boolean): void;
};

function pushPath(path: string) {
  if (typeof window !== "undefined" && window.location.pathname === path) return;
  if (useSessionStore.getState().kioskMode) return;  // NEW guard
  _navigate(path);
}
```

## useVoiceAgentBridge additions

```ts
// frontend/lib/useVoiceAgentBridge.ts
export type VoiceAgentHook = {
  // ...existing
  interrupt(): void;  // calls wsRef.current?.sendInterrupt(); throws if !wsRef.current
};
```

---

## Component touch list

| File | Change |
|---|---|
| `frontend/lib/ghiseuStore.ts` | Replace `scriptedTalkingFlow` and timer machinery. Implement new store shape per above. `attachVoiceBridge` only stores the bridge reference and returns cleanup. `enterVoiceMode` does the actual `bridge.start({…callbacks}) + bridge.enableMic()` (parallel), defensively calling `bridge.stop()` first if `wsReady`. |
| `frontend/lib/sessionStore.ts` | Add `kioskMode: boolean` + `setKioskMode(on: boolean)`. Add the `kioskMode` guard inside `pushPath` (one line). |
| `frontend/lib/useVoiceAgentBridge.ts` | Add `interrupt(): void` to `VoiceAgentHook` and its implementation (calls `wsRef.current?.sendInterrupt()`; throws if `!wsRef.current`). |
| `frontend/components/ghiseu/GhiseuShell.tsx` | Consume `useVoiceContext()`. Effect A: on mount run `setKioskMode(true)` + `attachVoiceBridge(voice)`; cleanup runs `setKioskMode(false)` and the attach-cleanup (stops the bridge). Effect B: gated on `citizen` hydrated, call `enterVoiceMode()` once (use a ref to guard re-entry). Effect C: one-liner mirroring `voice.micOn` into `ghiseuStore.setMuted(!voice.micOn)`. |
| `frontend/components/ghiseu/CaptionStrip.tsx` | Read `caption.user` / `caption.agent` from `useGhiseuStore`. Fall back to `TRANSCRIPT[state]` design copy when either is null. |
| `frontend/components/ghiseu/ControlsDock.tsx` | Mic button calls `ghiseuStore.toggleMute()` (which routes through `_bridge.disableMic` / `enableMic`). Ripple reflects real `voice.micOn && voice.state === "listening"` (read via `useVoiceContext`). `Întrerupe` button calls `ghiseuStore.interrupt()`. |
| `frontend/components/ghiseu/VoiceStage.tsx` | No structural change. STATUS_COPY entries already exist for every state in the enum. |

---

## Error & edge-case matrix

| Scenario | Behavior |
|---|---|
| `voice.enableMic()` → `VoiceAgentMicDeniedError` | state → `mic-denied`; UI shows `MicSlashIcon`. Recovery deferred to 2.4. |
| `voice.state` → `"error"` | state → `error`; UI shows `AlertIcon`. Reconnect deferred to 2.4. |
| `voice.start()` rejects | state → `error`; caught in `enterVoiceMode().catch()`. |
| User clicks mic in `mic-denied` | Re-runs `enterVoiceMode()` — gives the browser a second chance. |
| User clicks reset during `speaking` | `voice.stop()` cuts audio cleanly; state → `idle`. |
| Agent fires `start_procedure` while kioskMode=true | `loadDocument` runs (snapshot lands in `sessionStore.document`); `pushPath` no-ops; URL stays `/ghiseu`. |
| Agent fires `document_delivered` while kioskMode=true | Doc snapshot updates with `ref_number`. Visually invisible in 2.1 (review/done still stubbed). |
| Agent fires `widget_proposed` | Widget attaches to `sessionStore.messages` — kiosk doesn't render it. Effectively a no-op for kiosk UX. |
| Agent fires `redirect` | Goes through `pushPath` → kiosk-guarded → no-op. |
| Route change away during `speaking` | Cleanup runs: `voice.stop()` flushes player and closes WS. |
| WS drops mid-conversation | `onClose` → state=`idle`, `wsReady=false`, `micOn=false`. User must click mic to retry. Auto-reconnect deferred to 2.4. |

---

## Testing strategy

| Test file | Status | Coverage |
|---|---|---|
| `frontend/lib/__tests__/ghiseuStore.test.ts` | **Rewrite** (delete scripted-flow tests, add event-driven tests) | `appendUserPartial`/`commitUserMessage`/`appendAgentPartial`/`commitAgentMessage` updating the right caption slot; `interrupt()` calls bridge interrupt + flips state; `reset()` clears caption and calls `voice.stop()`; 300ms thinking-debounce is canceled by `onAgentDelta`. |
| `frontend/lib/__tests__/ghiseuStore.bridge.test.ts` | **New** | Integration with `MockVoiceAgentHook`: `attachVoiceBridge(mock)` stores the ref + returns cleanup; subsequent `enterVoiceMode()` calls `mock.start({…callbacks})` and `mock.enableMic()` in parallel; firing `capturedOpts.onUserDelta("hello")` updates `caption.user.text`; `attachVoiceBridge` cleanup calls `mock.stop()`; `enterVoiceMode()` calls `mock.stop()` first when `mock.wsReady` is true. |
| `frontend/lib/__tests__/sessionStore.test.ts` | **Extend** | `setKioskMode(true)` → `pushPath`/`loadDocument` chain does NOT call `_navigate`; `setKioskMode(false)` → it does. |
| `frontend/lib/__tests__/voiceBridge.test.ts` | **New or extend** | `interrupt()` calls `wsRef.current?.sendInterrupt()`; throws when WS not started. |
| `frontend/components/ghiseu/__tests__/CaptionStrip.test.tsx` | **Update** | Both null (fallback to TRANSCRIPT[state]) and filled (live caption text) cases. |
| `frontend/components/ghiseu/__tests__/GhiseuShell.test.tsx` | **New** | Mount with mocked `useVoiceContext`: `attachVoiceBridge` runs once; kioskMode flips true on mount + false on unmount. |

Out of scope for 2.1 tests: Playwright e2e (Phase 2.4), WS reconnect (no auto-reconnect exists yet), backend interrupt integration (already covered server-side).

### Test doubles

- `MockVoiceAgentHook` — typed mock implementing `VoiceAgentHook` with `vi.fn()` spies. `start()` captures `opts` so tests can fire `capturedOpts.onUserDelta?.("foo")`. State and `micOn` are mutable from the test.
- Zustand stores reset via `useGhiseuStore.setState(...)` / `useSessionStore.setState(...)` between tests.

---

## Acceptance criteria

- [ ] Logging in with the "Modul Ghișeu" pref on, completing OTP, and landing on `/ghiseu` opens the voice WS and engages the mic automatically (green ripple visible).
- [ ] Speaking into the mic streams partial text into the `Tu` bubble in real time; on user-done the line stops being "live" and the `thinking`/`speaking` transition fires within 300ms.
- [ ] The agent's reply streams text into the `eGata` bubble and plays audio synchronously.
- [ ] Clicking `Întrerupe` while `state==="speaking"` cuts the agent's audio (via `voice.interrupt()` → backend `interrupted` frame → player flush) and returns to `listening`.
- [ ] Clicking `Ia-o de la capăt` cancels the WS, returns to `idle`, and waits for the next mic click.
- [ ] The agent calling `start_procedure` does NOT navigate the kiosk away from `/ghiseu`; `sessionStore.document` updates silently.
- [ ] `/` (chat surface) and `/ghiseu` both still work; navigating from one to the other does not leave a dangling WS.
- [ ] All listed tests pass; no scripted-timer tests remain in `ghiseuStore.test.ts`.

---

## Risks & open questions

| Risk | Mitigation |
|---|---|
| `voice.start()` race when navigating `/` → `/ghiseu` while WS is still tearing down | `attachVoiceBridge` calls `voice.stop()` synchronously before `voice.start()`. The hook's `stop()` is synchronous (sets refs to null, no async cleanup). |
| User triple-clicks mic during the WS handshake | `enableMic()` is idempotent (`if (recorderRef.current) return`). `start()` racing is unlikely in normal UX but worth a re-entrant guard on `enterVoiceMode` (early-return if a start is already in flight). |
| `thinking` debounce flashes briefly even when TTS arrives in ~310ms | Acceptable for v1. If users complain, raise to 500ms. |
| `widget_proposed` arriving during kiosk session pollutes `sessionStore.messages` with content the user never sees | Acceptable. If the kiosk's voice agent never proposes a widget (and the system prompt should discourage it for voice-only sessions), this is moot. Confirmed-fine for 2.1; if it becomes noisy in practice, gate widget tools off server-side based on `voice_only`. |

---

## Implementation order (for the writing-plans handoff)

1. `useVoiceAgentBridge.interrupt()` + its unit test (smallest, fully independent).
2. `sessionStore.kioskMode` + guard + its unit test.
3. `ghiseuStore` rewrite (state shape, event handlers, lifecycle actions, `attachVoiceBridge`).
4. `ghiseuStore` bridge integration tests with `MockVoiceAgentHook`.
5. `GhiseuShell` wire-up + its unit test.
6. `CaptionStrip` + `ControlsDock` updates + their unit tests.
7. Manual smoke: log in with Modul Ghișeu on, talk to the agent, verify transcripts + audio + interrupt + reset.
