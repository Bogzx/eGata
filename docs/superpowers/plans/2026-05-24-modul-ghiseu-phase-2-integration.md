# Modul Ghișeu — Phase 2: Voice Agent + Backend Integration

> **For agentic workers:** This is a forward-looking roadmap. When you're ready to execute, use superpowers:writing-plans to expand each Phase 2.x section into a TDD plan with concrete code, then use superpowers:subagent-driven-development to execute.

**Goal:** Replace the scripted `setTimeout` flow in `/ghiseu` with a real wiring into the existing voice agent (`useVoiceAgentBridge`), the real session lifecycle (`sessionStore`), and real backend endpoints — so a user who toggles "Modul Ghișeu" on the login page can actually talk to the AI, complete a real procedure, review real document data, and submit it for real.

**Current state (Phase 1, complete on `feat/modul-ghiseu`):**
- `/ghiseu` route exists, design-faithful, gated by login
- `ghiseuStore` runs a scripted `idle → listening → thinking → speaking → review → export → done` state machine with hard-coded delays
- `attachVoiceBridge(bridge)` is a no-op stub
- `DocumentReview`, `CaptionStrip`, `DoneScreen` all use static sample data (Popescu Ana-Maria, REG-2026-08412, etc.)
- `ExportOptions.onPick` just advances state — no real HTTP call
- `/login` toggle persists pref; OTP redirects to `/ghiseu` when on

**Out of scope for Phase 2:**
- Dark-mode palette (`data-bg="dark"` exists in CSS but is never toggled in v1 either)
- Multi-procedure flow inside the kiosk (kiosk handles one procedure at a time)
- Reminders / "next steps" UI in the kiosk
- Procedure lookup widget — the kiosk relies on the agent's voice search to pick a procedure
- PDF download / print export options (the design's final iteration cut these — only city + email)

**Why a roadmap and not a single plan:** Phase 2 spans the frontend, backend, and the protocol between them. Each sub-phase produces a working slice on its own — voice without docs, then docs without export, then export. Splitting lets us ship incrementally and parallelize frontend + backend work.

---

## State-mapping table (the core design problem)

| `GhiseuState` | Source(s) of truth | When to enter |
|---|---|---|
| `idle` | Local (initial / post-reset) | Page load with no active session; after `reset()` |
| `listening` | `voice.state === "listening"` AND `voice.micOn === true` | After `enterVoiceMode()` resolves and mic permission granted |
| `thinking` | `voice.state === "listening"` AND no audio activity for >500ms AND agent hasn't started replying | Derived: brief gap between user finishing and agent starting |
| `speaking` | `voice.state === "speaking"` | Agent audio is playing |
| `review` | `session.state === "reviewing"` (from `sessionStore`) | Backend signals form is ready for review |
| `export` | Local (post-confirm-doc) | User clicks "Da, e corect" in review |
| `done` | Local (post-pick-export) | After successful `submit/<method>` API call returns ref number |
| `error` | `voice.state === "error"` OR API error | WS dropped, network failure, etc. |
| `mic-denied` | `enableMic()` rejects with `VoiceAgentMicDeniedError` | Browser denies mic permission |

**Key insight:** `thinking` doesn't exist in `useVoiceAgentBridge` — we derive it client-side from the gap between "user finished speaking" and "agent started speaking". If the agent's first audio chunk arrives within ~500ms, skip the `thinking` flash entirely.

---

## Phase 2.1 — Voice bridge integration (UI layer only, no backend changes)

**Outcome:** Real voice in/out works on `/ghiseu`. Captions show live transcripts. Document review and export remain stubbed.

### Files to touch

| Path | Change |
|---|---|
| `frontend/lib/ghiseuStore.ts` | Drop scripted timers. Replace `attachVoiceBridge` stub with a real implementation that subscribes to voice events and calls `setState`/`interrupt`. Add `caption: { user: Line; agent: Line }` field to the store so live transcripts can be written. Add `enterVoiceMode()` and `exitVoiceMode()` actions that wrap `voice.start()` + `voice.enableMic()` (mirror `ChatSurface.enterVoiceMode` lines 122-160). |
| `frontend/components/ghiseu/CaptionStrip.tsx` | Read live transcript from `useGhiseuStore` instead of the static `TRANSCRIPT` map. Keep TRANSCRIPT as a fallback when no live data exists yet. |
| `frontend/components/ghiseu/GhiseuShell.tsx` | Consume `useVoiceContext()` (the provider is already mounted at app/layout.tsx). Call `attachVoiceBridge(voice)` in a `useEffect` that runs once. On mount, call `enterVoiceMode()` so the WS opens and mic engages automatically (the kiosk is voice-first; no manual click needed for the auto-start). Mic toggle becomes pause/resume of the WS-attached mic, not a flow-trigger. |
| `frontend/components/ghiseu/ControlsDock.tsx` | No structural change. Mic still toggles muted via store. The `data-emit` ripple now reflects real `voice.micOn` AND real `voice.state === "listening"`. |
| `frontend/lib/ghiseuStore.test.ts` | Keep existing scripted-flow tests but mark them legacy — add new tests for `enterVoiceMode`, voice event handling, and live caption updates with a mock bridge. |

### Voice event → store action mapping

```
voice.onUserDelta(text)   → store.appendUserPartial(text)
voice.onUserMessage(text) → store.commitUserMessage(text)  + state → "thinking" (debounced 300ms)
voice.onAgentDelta(text)  → store.appendAgentPartial(text) + state → "speaking" if not already
voice.onAgentMessage(t)   → store.commitAgentMessage(t)
voice.state changes:
  "connecting"  → no store change (transient)
  "listening"   → if no agent partial in last 500ms → state = "listening"
  "speaking"    → state = "speaking"
  "error"       → state = "error"
```

### Tasks (TDD-driven, ~6 tasks)

1. Extend `GhiseuStore` shape with `caption: { user, agent }` and the four new actions (`appendUserPartial`, `commitUserMessage`, `appendAgentPartial`, `commitAgentMessage`). Tests verify each action updates the right field without bleeding.
2. Rewrite `attachVoiceBridge(bridge)` to wire `voice.start` callbacks (`onUserDelta`/`onAgentDelta`/etc.) to the new actions. Return a real cleanup that detaches the listeners and calls `voice.stop()`.
3. Add `enterVoiceMode()` and `exitVoiceMode()` to the store, lifted verbatim from `ChatSurface.enterVoiceMode`. Test by mocking `voice.start` + `voice.enableMic` and asserting they're called in parallel.
4. Wire `GhiseuShell` to call `attachVoiceBridge(voice)` in a `useEffect([voice])` and auto-enter voice mode on mount when citizen is hydrated (mirror `ChatSurface` lines 162-176).
5. Rewrite `CaptionStrip` to prefer `caption.user` / `caption.agent` from the store, falling back to `TRANSCRIPT[state]` if both are null.
6. Update `ControlsDock` mic button: on click, call `voice.disableMic()` if `voice.micOn`, else `voice.enableMic()`. The store's `muted` becomes a derived value from `voice.micOn`.

### Acceptance criteria

- [ ] Toggling Modul Ghișeu on, completing OTP, arriving on `/ghiseu` opens the voice WS and engages the mic automatically (with the green ripple).
- [ ] Speaking into the mic streams partial captions into the `Tu` bubble in real time.
- [ ] The agent's reply streams into the `eGata` bubble in real time and plays audio.
- [ ] `voice.state === "speaking"` → `Întrerupe` button is enabled. Clicking it calls `voice.stop()` and re-engages mic.
- [ ] Reset (`Ia-o de la capăt`) cancels the WS via `voice.stop()` and re-mounts a fresh session on next mic click.
- [ ] Existing chat surface (`/`) and its voice flow are unchanged — both share the same `VoiceProvider` and the WS is reused.

### Risks

- **WS sharing:** `VoiceProvider` mounts in `app/layout.tsx` and persists across routes. If a user navigates from `/` to `/ghiseu`, the existing chat surface's voice session is still attached. `attachVoiceBridge` must coordinate with `ChatSurface`'s listeners — only one should be "active" at a time. Either:
  - (a) Refactor `useVoiceAgentBridge` to support multiple subscribers (pub-sub fan-out), or
  - (b) Have `GhiseuShell` and `ChatSurface` exclusively own the bridge based on the current route — use `usePathname()` to decide who attaches.
- **Mic prewarm:** `VoiceProvider` already calls `prewarmMicPermission()` on mount, which is good for both surfaces.

---

## Phase 2.2 — Real session + document data

**Outcome:** `DocumentReview` shows the real form the AI just filled in, with the real procedure's title, fields, and auto-fill markers. `DoneScreen` shows the real ref number.

### Files to touch

| Path | Change |
|---|---|
| `frontend/lib/ghiseuStore.ts` | Subscribe to `useSessionStore`. When `session.state === "reviewing"`, transition Ghișeu state to `review` and snapshot the active `document` + `procedure`. Expose `activeDocument`, `activeProcedure` on the store. |
| `frontend/components/ghiseu/DocumentReview.tsx` | Drop the hard-coded `FIELDS` array. Read `activeProcedure.fields` + `activeDocument.fields` from the store. Build the field rows by joining: for each `ProcedureField`, render `label = pf.label`, `value = doc.fields[pf.name]`, `auto = pf.source === "citizen_attributes" || pf.source === "roeid"`. Doc-paper header reads `procedure.title` (e.g., "Adeverință de venit") instead of being hard-coded. Stamp + sub-line stay design copy. |
| `frontend/components/ghiseu/DoneScreen.tsx` | Read `activeDocument.ref_number` from the store. Fall back to `REG-PENDING` if not yet set (race during the submit API call). |

### Tasks (~4 tasks)

1. Add `activeDocument: Document | null` and `activeProcedure: Procedure | null` to `GhiseuStore`. Test: setting/clearing each.
2. In `GhiseuShell`, subscribe to `useSessionStore` and call `ghiseuStore.setSessionSnapshot({ document, procedure })` whenever they change. Test: render with mocked sessionStore.
3. Rewrite `DocumentReview` to render from store data, with a graceful "Se încarcă..." fallback when `activeDocument` is null but state is `review`. Test: render with mocked store data, assert correct labels/values.
4. Wire `DoneScreen` to use the real ref number with the fallback. Test: render with and without ref number.

### Acceptance criteria

- [ ] After the AI completes a procedure (e.g., "Adeverință de venit") via voice, the review screen shows the AI-filled values for that specific procedure's fields, with `✓ auto` next to fields filled from citizen ROeID data.
- [ ] The doc-paper header title matches the active procedure.
- [ ] If the user picks a different procedure (e.g., "Certificat de urbanism" instead), the field grid updates accordingly.
- [ ] DoneScreen ref number is the real one returned by the submit endpoint.

### Risks

- **Field source classification:** The current schema has `ProcedureField.source: string` but no enum. The Ghișeu UI needs to know which fields are "auto-filled" (badge) vs "asked of the user" (no badge). Decide on the convention: `source ∈ {"citizen_attributes", "roeid", "ai_inferred"}` get auto; `source ∈ {"user_input", "ai_asked"}` don't. Document this in `lib/types.ts`.

---

## Phase 2.3 — Export action wiring

**Outcome:** Clicking "Trimite la primărie" or "Trimite pe email" makes a real API call. On success, the user lands on the done screen with the real ref number.

### Backend changes required

**One new endpoint** (or extend the existing finalize/submit endpoint):

```
POST /api/documents/{document_id}/submit
Content-Type: application/json
Authorization: Bearer <session>

Body: {
  "method": "city" | "email",
  "email_address"?: string  // required when method=email; defaults to citizen.email if omitted
}

Response 200: {
  "ref_number": "REG-2026-08412",
  "delivery": "send" | "save",
  "delivered_at": "2026-05-24T15:32:11Z"
}

Response 409: { "error": "already_delivered", "ref_number": "..." }
```

Implementation notes:
- `method=city` → write a ledger entry (`event_type=delivered`, payload=`{recipient: "primarie"}`), generate the official PDF, mark the document as delivered, queue a notification to the destination department.
- `method=email` → write a ledger entry (`event_type=delivered`, payload=`{recipient: "email", to: <email>}`), generate the PDF, email it to the citizen, mark delivered.
- The ref number format `REG-{yyyy}-{8-digit-sequence}` should be issued atomically (e.g., postgres `nextval`) so two concurrent submits never collide.

### Frontend changes

| Path | Change |
|---|---|
| `frontend/lib/api.ts` | Add `submitDocument(docId, body): Promise<SubmitResponse>` (matches the new endpoint above). |
| `frontend/lib/ghiseuStore.ts` | Add `pickExport(method)` to make the API call instead of just advancing state. While the call is in flight, transition state to a new `submitting` substate so the UI can show a spinner; on success, transition to `done`; on failure, transition to `error` with a retry option. |
| `frontend/components/ghiseu/ExportOptions.tsx` | Disable both cards while `submitting`. Show a subtle pulse on the chosen card. |
| `frontend/components/ghiseu/VoiceStage.tsx` | Add a `submitting` case to `STATUS_COPY` with title "Trimit cererea..." + hint "Durează câteva secunde." |
| `frontend/lib/__tests__/ghiseuStore.test.ts` | Test the happy path (API resolves → done with real ref), the failure path (API rejects → error state), and the 409 already-delivered path (treat as success — show done with the existing ref). |

### Tasks (~5 tasks)

1. Backend: implement `POST /api/documents/{id}/submit`. Tests cover both methods + the 409 case.
2. Backend: emit the `delivered` ledger event. Tests verify the hash chain stays valid.
3. Frontend: add `api.submitDocument` + `SubmitResponse` type. Test the request shape with MSW.
4. Frontend: extend `ghiseuStore.pickExport` to make the call, manage `submitting` substate, and propagate ref_number to `activeDocument`. Test with mocked `api.submitDocument`.
5. Frontend: update `ExportOptions` and `VoiceStage` for the `submitting` UX. Verify the disabled state in tests.

### Acceptance criteria

- [ ] Picking "Trimite la primărie" calls the backend, shows a brief "Trimit cererea..." state, then lands on done with the real ref.
- [ ] Picking "Trimite pe email" does the same; citizen's email is auto-used.
- [ ] Network failure → state goes to `error` with copy that includes a retry button (which calls `pickExport(method)` again).
- [ ] Hitting the back button (or `Întreabă altceva`) during `submitting` does NOT cancel the in-flight call but lets the user keep talking (background completion still updates ref).
- [ ] Calling submit twice for the same document returns 409 the second time; UI treats it as success and shows the existing ref.

### Risks

- **Idempotency:** If the user double-clicks the export card, two submit requests fire. The backend needs to either dedupe by `(document_id, idempotency_key)` or accept that the second one returns 409. We pick the simpler 409 path here.
- **Email format:** If citizen email is missing from ROeID, the email card needs to either disable or prompt for an email. Out of scope for v2.3 — assume email is present (it is for all seeded demo users).

---

## Phase 2.4 — Polish + production readiness

**Outcome:** The kiosk holds up under stress: reconnects on WS drop, handles mic permission denial gracefully, recovers from network blips, plays nicely with the rest of the app.

### Tasks

1. **Mic permission flow.** When `enableMic()` throws `VoiceAgentMicDeniedError`, set state to `mic-denied`. Show a clear path forward in `VoiceStage` — a "Reîncearcă" button that calls `enterVoiceMode()` again. Make sure the design's `MicSlashIcon` is shown (already wired).
2. **WS reconnect.** `useVoiceAgentBridge` already handles WS errors, but the Ghișeu store needs to expose a "reconnect" action and update copy when `voice.state === "error"`. Show the existing `AlertIcon` and a "Reconectează" button.
3. **Reset cleanup.** `reset()` already cancels timers (fix from Phase 1). In Phase 2, also call `voice.stop()` AND clear the session via `sessionStore.reset()` so the next conversation starts fresh. Test: after reset, the citizen, document, and procedure should all be null.
4. **Visibility-pause.** When the tab is hidden (e.g., user switches windows), `voice.disableMic()` so we don't leak hot mic. Re-enable when visible if the previous state was `listening`. Use `document.visibilitychange`.
5. **Network-blip retry.** Wrap `api.submitDocument` in a one-shot retry with exponential backoff (200ms, then 800ms) for transient `5xx` only. Surface as a single `error` if both fail.
6. **Telemetry.** Emit page-view + key-event analytics: `ghiseu_session_started`, `ghiseu_review_reached`, `ghiseu_submitted{method}`, `ghiseu_error{kind}`. Pipe through the existing analytics layer (check `frontend/lib/` for what's already there — if nothing, defer to Phase 3).
7. **Smoke e2e test.** Add a Playwright spec at `frontend/e2e/ghiseu.spec.ts` that:
   - Logs in via the seeded user
   - Toggles Modul Ghișeu on
   - Lands on `/ghiseu`
   - Stubs the WS to fast-forward through listening → thinking → speaking → review
   - Picks "Trimite la primărie" (stubs the submit endpoint to return a known ref)
   - Asserts the done screen shows that ref
   - Note: the existing e2e config has a Playwright version mismatch — fix that first.
8. **Accessibility audit.** Run `axe-core` against `/ghiseu` for each state (use Playwright + `@axe-core/playwright`, already a dev dep). Address any violations.
9. **Memory leak check.** Mount/unmount `GhiseuShell` 50 times in a test and confirm no growing listeners or timer handles.
10. **Update the spec.** Mark Phase 1 / Phase 2 sections as "done" in `docs/superpowers/specs/2026-05-24-modul-ghiseu-design.md` and capture any new architectural decisions inline.

### Acceptance criteria

- [ ] Denied mic → clear UI path back, working "Reîncearcă"
- [ ] WS drop → error state + working "Reconectează"
- [ ] Reset → session truly fresh
- [ ] Tab hidden → mic actually paused (verify via system mic indicator)
- [ ] e2e green
- [ ] axe violations = 0

---

## Sequencing & estimates

| Phase | Frontend tasks | Backend tasks | Best estimate |
|---|---|---|---|
| 2.1 — Voice bridge | 6 | 0 | 1 day |
| 2.2 — Session + doc data | 4 | 0 (schema may need a `source` enum) | half day |
| 2.3 — Export wiring | 3 | 2 | 1 day |
| 2.4 — Polish | 10 | 0 | 1.5 days |
| **Total** | **23** | **2** | **~4 days** |

Phases 2.1 and 2.3-backend can run in parallel (different people / different repos). Phase 2.2 needs 2.1 to be partially landed (so the store can observe sessionStore in a real flow). Phase 2.4 starts as soon as 2.1+2.2+2.3 are usable end-to-end.

---

## What this gives us

After Phase 2.4:
- A real citizen logs in, toggles Modul Ghișeu, completes a procedure entirely by voice, reviews the AI-filled form, picks how to send it, and gets a real registration number.
- The same backend that powers `/` powers `/ghiseu` — no fork, no shadow API.
- The kiosk is genuinely accessible (mic permission failures are recoverable, screen reader friendly, network resilient).
- The seam between the kiosk and the regular chat surface is the `VoiceProvider` and `sessionStore`. Either surface can be modified without breaking the other.

## What we explicitly defer to Phase 3+

- **Multi-procedure in one Ghișeu session** — e.g., user finishes one form, then says "and also a parking permit". Today the kiosk handles one procedure per session.
- **Document attachments** — uploading photos of supporting docs by voice prompt. Out of scope.
- **Persona switching** — kiosk mode is single-user; no fast user-switching.
- **Offline mode** — the kiosk assumes connectivity. A real lobby kiosk might need a "queue request locally, sync later" mode.
- **Print export** — the design cut it; could be re-added if a physical printer is wired up at the kiosk.

---

## Notes for the executor

When you start Phase 2.x:
1. Branch off `main` (assuming Phase 1's branch is merged) as `feat/modul-ghiseu-phase-2.1`, then 2.2, 2.3, 2.4 — one branch per phase, each PR-reviewable independently.
2. Run `superpowers:writing-plans` against this roadmap's section for the phase you're starting, to produce a fine-grained TDD plan with concrete code in each task.
3. Use `superpowers:subagent-driven-development` to execute that plan.
4. The Phase 1 spec lives at `docs/superpowers/specs/2026-05-24-modul-ghiseu-design.md` — keep it as the canonical reference for the design and update it inline as decisions land.
5. The existing `ChatSurface.tsx` is the gold-standard reference for how voice + session integration looks in this codebase. When in doubt, mirror its pattern (especially `enterVoiceMode` and the auth-gate effect).
