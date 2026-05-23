# Modul Ghișeu — voice-only kiosk page

A standalone, kiosk-style, voice-first experience for eGata. Opt-in from the login page via a "Modul Ghișeu" slide toggle. Routes to a dedicated `/ghiseu` URL after authentication, where the whole flow (request → AI conversation → document review → export → done) lives inside a single voice-driven page. Built static-first; the real voice agent gets wired in a later pass.

## Why

Today's `ChatSurface` mixes text and voice. For users who only want to talk — older users, kiosk visitors in a primărie lobby, anyone uncomfortable with typing — the chat layout is too busy: composer, right pane, document drawers, mobile toggles, all visible at once. Modul Ghișeu strips this down to a single big status sentence + caption strip + two pill controls, with the same visual language as the rest of eGata so it doesn't feel like a different product.

The design we are implementing comes from a Claude Design handoff bundle (`cluj-hackathon-audioonly`), which the user iterated on before this implementation. The final iteration removed the centerpiece visualizer; the mic ripple is the only audio cue. We honor that.

## Scope

**In scope (v1):**
- New `/ghiseu` route, auth-gated like `/`
- All design states implemented: `idle`, `listening`, `thinking`, `speaking`, `review`, `export`, `done`, `error`, `mic-denied`
- Scripted state machine (`setTimeout`-driven, no real backend) — matches the design's `handleStartTalking`
- Static sample data for the document review (Popescu Ana-Maria placeholder)
- Static `TRANSCRIPT` map for the caption strip
- `Modul Ghișeu` slide toggle on `/login` (both `LoginCard` desktop variant and `KioskLogin` terminal variant)
- Toggle preference persisted in `localStorage` (`egata.ghiseu`)
- After OTP success, redirect to `/ghiseu` when the toggle is on, `/` otherwise
- Top-bar profile menu (accessibility: large text / high contrast / dyslexic) using the existing `useAccessibilityPrefs` store
- Reset pill (`Ia-o de la capăt`) in the top-right
- Mic toggle (Pornește/Oprește microfonul) with ripple effect while listening
- Interrupt button (Întrerupe) enabled only during `speaking`
- Animated mesh background (canvas) in the green eGata palette
- Romanian copy throughout, matching the design verbatim
- Responsive (works on mobile per the design's `@media` rules)

**Out of scope (v1 — but seam preserved):**
- Real voice agent wiring (`useVoiceAgentBridge`, WS, audio worklets). A `attachVoiceBridge(store)` stub is exported from `lib/ghiseuStore.ts` for later.
- Real document data flow from `sessionStore`. Static sample data only.
- Real export side effects (send to primărie, send email). Buttons just advance to `done`.
- Tweaks panel from the design bundle (dev-only, not production).
- Centerpiece visualizers (`orb`, `aura`, `photo`, etc.) — removed by the user during design iteration.

## Architecture

### Route

```
/ghiseu       → app/ghiseu/page.tsx → <GhiseuShell />
```

`page.tsx` is a thin client component that runs the same auth gate as `ChatSurface` (redirect to `/login` if no session), hydrates the citizen from `sessionStore`, then renders `<GhiseuShell />`. The page does NOT use the `ChatSurface` layout — it's its own world.

### Component tree

```
<GhiseuShell>                                  components/ghiseu/GhiseuShell.tsx
  <AnimatedMesh palette={green} dark={false}/>  components/ghiseu/AnimatedMesh.tsx
  <header className="gh-top">
    <Brand />                                   inline
    <div className="gh-top-actions">
      <ResetPill onReset={…} disabled={…}/>     inline
      <GhiseuProfileMenu />                     components/ghiseu/GhiseuProfileMenu.tsx
    </div>
  </header>
  <main className="gh-main">
    {state ∈ {idle, listening, thinking, speaking, error, mic-denied}
      ? <VoiceStage state={state}/>             components/ghiseu/VoiceStage.tsx
      : state === "review"
      ? <DocumentReview onConfirm onAmend/>     components/ghiseu/DocumentReview.tsx
      : state === "export"
      ? <ExportOptions onPick/>                 components/ghiseu/ExportOptions.tsx
      : state === "done"
      ? <DoneScreen method/>                    components/ghiseu/DoneScreen.tsx
      : null
    }
  </main>
  <ControlsDock state muted on*Callbacks/>       components/ghiseu/ControlsDock.tsx
</GhiseuShell>
```

`<VoiceStage>` contains the status text (`<h2 className="gh-status-text">`) and the `<CaptionStrip>`. Caption strip is a thin presentational component that takes `state` and renders the `TRANSCRIPT[state]` lines.

### State machine

`lib/ghiseuStore.ts` exports a Zustand store:

```ts
type GhiseuState =
  | "idle" | "listening" | "thinking" | "speaking"
  | "review" | "export" | "done"
  | "error" | "mic-denied";

type ExportMethod = "city" | "email" | null;

type GhiseuStore = {
  state: GhiseuState;
  muted: boolean;
  exportMethod: ExportMethod;
  // actions
  startTalking(): void;     // idle → listening → thinking → speaking → review (scripted timers)
  toggleMute(): void;       // from idle+muted: also calls startTalking()
  interrupt(): void;        // speaking → listening, unmute
  confirmDoc(): void;       // review → export
  amendDoc(): void;         // review → listening (then speaking after 1.8s)
  pickExport(m): void;      // export → done, store method
  backToTalk(): void;       // review|export → listening, unmute
  reset(): void;            // any → idle, mute, clear export
};
```

Timer schedule (matches the design exactly):
- `startTalking()`: `listening` now → `thinking` at +2.8s → `speaking` at +4.3s → `review` at +7.4s
- `amendDoc()`: `listening` now → `speaking` at +1.8s

The store also exposes a no-op `attachVoiceBridge(bridge)` function. When real wiring lands, `attachVoiceBridge` will subscribe to the bridge's `state` and `message` events and call the matching store actions, replacing the scripted timers.

### Login → /ghiseu wiring

1. `components/ModulGhiseuToggle.tsx` — labeled "Modul Ghișeu" with hint "Doar vorbește cu asistentul. Fără ecrane complicate." Calls `setGhiseuPref(boolean)` on change. Reads initial value via `getGhiseuPref()`.
2. `lib/ghiseuPref.ts` — `getGhiseuPref(): boolean` / `setGhiseuPref(v: boolean): void`, backed by `localStorage` key `egata.ghiseu`. SSR-safe (returns `false` when `window` is undefined).
3. `app/login/page.tsx` — render `<ModulGhiseuToggle />` ABOVE the login CTA (`LoginButton`) inside `LoginCard`, AND above the chooser buttons inside `KioskLogin`.
4. `app/login/otp/page.tsx` — after `setSession(session)`, read `getGhiseuPref()` and call `router.push(pref ? "/ghiseu" : "/")`.

The toggle preference survives the OTP step via `localStorage`, so we don't need to thread it through the URL.

### Styling

The design ships `voice-styles.css` (~1000 lines) using `.vo-*` classnames. We port this to `app/ghiseu/ghiseu.css` with the prefix renamed `.gh-*`, imported from `app/ghiseu/page.tsx`. CSS-only port — no Tailwind rewrite — because:

1. The design is design-system-distinct (`--c-dark`, `--c-mid`, `--c-light` greens; custom `--r-md`/`--r-lg`/`--r-xl` radii; specific shadows) and reimplementing this in Tailwind utilities would lose fidelity.
2. The styles are scoped to `/ghiseu` so they can't bleed into the rest of the app.
3. The accessibility classes (`html.large-text`, `html.high-contrast`, `html.dyslexic`) already exist globally via `useAccessibilityClasses`; the design's overrides are appended for `.gh-*` selectors.

Font assets (Onest, JetBrains Mono) are already loaded in `app/layout.tsx` via `next/font/google` and exposed as CSS variables. We reference those, not the `<link>` import from the prototype.

### Animated mesh

`components/ghiseu/AnimatedMesh.tsx` ports the canvas blob loop from the design's `AnimatedMesh` component, with React 19 + TypeScript. Same algorithm: 5 radial-gradient blobs orbiting on staggered sin/cos paths, painted on a `requestAnimationFrame` loop, blurred at the CSS level (`filter: blur(38px)`). `ResizeObserver` keeps the canvas DPR-aware. Respects `prefers-reduced-motion` by skipping the rAF loop and painting a single static frame.

Accepts `palette` and `dark` props; v1 hardcodes green palette (`{ dark: "#1F6F5F", mid: "#2FA084", light: "#6FCF97", bg: "#EEEEEE" }`) and `dark={false}`.

### Accessibility

- Reuses the existing `useAccessibilityClasses` (called inside `GhiseuShell` so the `html` classes get applied while on `/ghiseu`).
- `GhiseuProfileMenu` writes to `useAccessibilityPrefs` (`largeText`, `highContrast`, `dyslexic`) — single source of truth across the app.
- CSS in `ghiseu.css` includes `html.large-text .gh-*`, `html.high-contrast .gh-*`, `html.dyslexic .gh-*` rules ported from `voice-styles.css`.
- All buttons have `aria-label` and `aria-pressed` where applicable.
- Caption strip uses `aria-live="polite"`.
- Color-only state never used — the mic button has both color change and icon change.
- Status text always reachable, no purely-decorative-without-text controls.

### Romanian copy

All user-visible text is taken verbatim from the design bundle (`STATUS_COPY`, `TRANSCRIPT`, button labels, document review labels, export card titles, profile menu labels). We do not invent new copy.

## File inventory

### New files

| Path | Purpose |
|---|---|
| `frontend/app/ghiseu/page.tsx` | Route entry, auth gate, mounts `GhiseuShell` |
| `frontend/app/ghiseu/ghiseu.css` | Scoped styles (port of `voice-styles.css`, `.vo-*` → `.gh-*`) |
| `frontend/components/ghiseu/GhiseuShell.tsx` | Shell: mesh + top bar + main + controls |
| `frontend/components/ghiseu/AnimatedMesh.tsx` | Canvas background |
| `frontend/components/ghiseu/VoiceStage.tsx` | Status + CaptionStrip for talk states + error states |
| `frontend/components/ghiseu/CaptionStrip.tsx` | Tu/eGata bubble pair |
| `frontend/components/ghiseu/ControlsDock.tsx` | Mic toggle + Interrupt (state-driven) |
| `frontend/components/ghiseu/DocumentReview.tsx` | Doc-paper + 2-col fields + confirm/amend |
| `frontend/components/ghiseu/ExportOptions.tsx` | 2 export cards (primărie / email) |
| `frontend/components/ghiseu/DoneScreen.tsx` | Checkmark + ref number + restart |
| `frontend/components/ghiseu/GhiseuProfileMenu.tsx` | Top-right accessibility dropdown |
| `frontend/components/ghiseu/icons.tsx` | SVG icon set ported from design |
| `frontend/components/ModulGhiseuToggle.tsx` | Slide toggle on the login page |
| `frontend/lib/ghiseuStore.ts` | Zustand state machine + scripted timers |
| `frontend/lib/ghiseuPref.ts` | localStorage `egata.ghiseu` get/set |

### Edited files

| Path | Change |
|---|---|
| `frontend/app/login/page.tsx` | Mount `<ModulGhiseuToggle />` above the login CTA in both `LoginCard` and `KioskLogin` |
| `frontend/app/login/otp/page.tsx` | After `setSession`, redirect via `getGhiseuPref()` |

No edits to `ChatSurface`, `RightPane`, `Composer`, `TopBar`, `VoiceProvider`, or `sessionStore`. Modul Ghișeu is fully additive.

## Testing

- Unit (Vitest): `lib/ghiseuStore.test.ts` — verify state transitions for `toggleMute` from idle, `interrupt` only-enabled-while-speaking, `confirmDoc`/`amendDoc`/`pickExport`/`backToTalk`/`reset`, and timer schedule (use `vi.useFakeTimers()`).
- Unit (Vitest): `lib/ghiseuPref.test.ts` — get/set roundtrip, SSR safety.
- Unit (Vitest): `components/ModulGhiseuToggle.test.tsx` — render, toggle changes localStorage.
- Manual (browser): walk all 9 states end-to-end via the scripted flow; verify the mic ripple appears only in `listening` + unmuted; verify Interrupt disabled outside `speaking`; toggle each accessibility class and verify CSS picks it up.
- No e2e in v1 — the static flow has no real network calls to assert against.

## Error handling

- `error` and `mic-denied` states are reachable via the store but never triggered by the scripted flow in v1. They're surfaced for the design pass (and will be wired to real bridge errors in v2). Visually: replace the status icon with `<Alert>` / `<MicSlash>` per the design.
- `getGhiseuPref` and `setGhiseuPref` swallow `localStorage` errors (private browsing) and default to `false`.

## Performance

- `AnimatedMesh` uses a single `<canvas>` + rAF loop, capped at the browser's frame rate. DPR clamped to 2 to keep mobile sane.
- `CaptionStrip` is keyed off `state`, so the entrance animation only re-plays when the state changes.
- No external libraries added (the project already has `zustand`, `framer-motion`, `lucide-react`). Icons in the design are inline SVG; we port them as React components rather than pulling `lucide` equivalents to preserve exact shapes.

## Done = these are true

- [ ] `/ghiseu` route renders the design's idle state on first visit (assuming logged-in citizen).
- [ ] The "Modul Ghișeu" toggle on `/login` persists, and OTP completion routes correctly.
- [ ] All 9 design states render correctly when forced (manually or by the scripted flow).
- [ ] Reset (`Ia-o de la capăt`) returns to idle from any state.
- [ ] Accessibility toggles (large text / high contrast / dyslexic) take effect on `/ghiseu` and persist.
- [ ] No regressions on `ChatSurface`, the existing voice-only mode inside ChatSurface, or the main login flow.
- [ ] `pnpm typecheck` and `pnpm test` pass.

## Open questions for later

- Real voice bridge integration plan (Phase 2): which events from `useVoiceAgentBridge` map to `listening`/`thinking`/`speaking`/etc., and where the document review reads its fields from once the conversation is real.
- Should the toggle on `/login` also be available in the in-app `ProfileMenu` so users can switch into Ghișeu mode without logging out? Out of scope for v1.
