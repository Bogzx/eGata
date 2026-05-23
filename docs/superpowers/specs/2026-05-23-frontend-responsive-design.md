# Frontend responsive design (mobile / tablet / desktop)

**Date:** 2026-05-23
**Scope:** `frontend/` — `ChatSurface`, `TopBar`, `Composer`, `RightPane`, `DocumentsDrawer`, login + OTP, `KioskShell`, and the `components/ui/` primitives.
**Approach:** A — CSS-only refinement of `app/globals.css` plus minimal React state in `ChatSurface` for the mobile view toggle. Desktop layout above 1024px is preserved byte-for-byte.

## Goal

Make every reachable page of the eGata frontend usable and visually correct on three classes of device:

- **Mobile** ≤ 640px
- **Tablet** 641px – 1024px
- **Desktop** ≥ 1025px (current behavior, unchanged)

The existing layout has a single breakpoint at `@media (max-width: 980px)` that hides the document preview entirely below 980px. This means mobile users cannot see the document they're filling out — only the chat. The redesign introduces a proper three-tier breakpoint system, a mobile-only Chat / Document segmented toggle, narrower tablet split, and touch-friendly sizing throughout.

## Non-goals

- No visual redesign — colors, typography, iconography, animations, and component styling stay as they are.
- No migration to Tailwind utility classes (this is Approach A, not B).
- No container queries (Approach C was rejected as overkill).
- No new Tailwind plugins or design tokens beyond two new breakpoint custom properties.
- No changes to backend, state machine, accessibility store, or component logic — purely layout/CSS plus one piece of React state.

## Breakpoints

Added to `:root` in `app/globals.css`:

```css
--bp-mobile: 640px;
--bp-tablet: 1024px;
```

Media queries throughout the file are written as:

```css
@media (max-width: 640px)                            /* mobile */
@media (min-width: 641px) and (max-width: 1024px)    /* tablet */
@media (pointer: coarse)                             /* touch devices */
```

The existing `@media (max-width: 980px)` block is replaced — its rules are split between the new mobile and tablet blocks.

## ChatSurface — mobile view toggle

### State

One new piece of state added to `components/chat/ChatSurface.tsx`:

```ts
const [mobileView, setMobileView] = useState<"chat" | "doc">("chat");
```

### Markup

A new `MobileViewToggle` component is rendered inside `.civic-shell`, just above `<main>`. It is always in the DOM but hidden by CSS at viewport widths > 640px.

```tsx
{showRight ? (
  <MobileViewToggle value={mobileView} onChange={setMobileView} />
) : null}
```

The toggle is a two-segment pill: **„Chat"** | **„Document"**. The active segment uses the same `--c-dark` background as `.chip.is-active`. When `showRight` is false (voice-only mode, or pre-engagement), the toggle is not rendered at all — there is only one view.

### Wiring

`mobileView` is written to `.civic-root` as `data-mobile-view="chat" | "doc"`. CSS at `≤640px` uses this attribute to toggle visibility:

```css
@media (max-width: 640px) {
  .civic-root[data-mobile-view="chat"] .civic-right { display: none; }
  .civic-root[data-mobile-view="doc"]  .civic-left  { display: none; }
  .civic-root[data-mobile-view="doc"]  .civic-right { display: flex; }
  .civic-root[data-mobile-view="doc"]  .composer    { display: none; }
}
```

When the session enters `filling` or `reviewing` while `mobileView === "chat"`, the "Document" segment gets a subtle 1.5s pulse animation as a hint that new content is available. Implementation:

```ts
useEffect(() => {
  if (mobileView === "chat" && (state === "filling" || state === "reviewing")) {
    setDocHinted(true);
    const t = setTimeout(() => setDocHinted(false), 1500);
    return () => clearTimeout(t);
  }
}, [state, mobileView]);
```

The pulse is a `box-shadow` animation defined in `globals.css`:

```css
@keyframes mobile-toggle-hint {
  0%, 100% { box-shadow: 0 0 0 0 rgba(47, 160, 132, 0.55); }
  50%      { box-shadow: 0 0 0 8px rgba(47, 160, 132, 0); }
}
.mobile-toggle-seg.is-hinted {
  animation: mobile-toggle-hint 1.5s ease-out 1;
}
```

The animation respects the existing `@media (prefers-reduced-motion: reduce)` block in `globals.css` (lines 157-174), which already neutralizes pulse animations.

## Layout grid

`.civic-main.is-engaged` becomes responsive:

| Viewport | grid-template-columns |
|---|---|
| Desktop ≥ 1025 | `minmax(420px, 1fr) minmax(420px, 560px)` (unchanged) |
| Tablet 641–1024 | `minmax(0, 1fr) minmax(320px, 420px)` |
| Mobile ≤ 640 | `1fr` (toggle controls which child is visible) |

Padding also scales:

| Viewport | `.civic-main` padding |
|---|---|
| Desktop | `0 28px 24px` |
| Tablet | `0 20px 18px` |
| Mobile | `0 12px 12px` |

## Viewport height

`.civic-root` is updated to use the dynamic viewport unit so mobile browser chrome (URL bar) does not push the composer off-screen:

```css
.civic-root {
  height: 100vh;       /* fallback for older browsers */
  height: 100dvh;      /* dynamic viewport */
}
```

## TopBar

At ≤640px:

- `.topbar` padding drops from `18px 28px` to `12px 14px`.
- `.topbar` `gap` drops from `16px` to `8px`.
- The "Documentele mele" chip hides its text label, keeping the folder icon + badge. The `aria-label` continues to read "Documentele mele, N documente" for screen readers.
- The profile chip hides its name text, showing only the circular avatar + caret. `aria-label` retained.
- The voice chip stays icon-only (already is).
- `.brand-sub` ("Primărie · România") is hidden on mobile to save horizontal space.

Implementation: chip text labels get a new utility class `.chip-text` and the rule:

```css
@media (max-width: 640px) {
  .chip-text { display: none; }
  .chip { padding: 8px; }
  .brand-sub { display: none; }
}
```

At tablet (641-1024) chips keep their text but `.topbar` padding shrinks to `14px 18px`.

## Composer

Hit target bumps for touch devices:

```css
@media (pointer: coarse) {
  .composer-mic, .composer-send {
    width: 44px;
    height: 44px;
  }
  .composer-attach {
    padding: 12px;
  }
}
```

Composer shell padding tightens on mobile so the input area has more thumb room:

```css
@media (max-width: 640px) {
  .composer { padding: 6px 12px 14px; }
  .composer-shell { padding: 4px 4px 4px 12px; }
  .composer-input { font-size: 16px; }   /* prevent iOS zoom-on-focus */
}
```

The composer stays pinned at the bottom of `.civic-left` via the existing flex layout — no `position: fixed`, which avoids the well-known iOS keyboard overlap bug.

## DocumentsDrawer

Drawer width becomes responsive:

| Viewport | `.drawer` width |
|---|---|
| Desktop | `min(420px, 100vw)` (unchanged) |
| Tablet | `min(440px, 88vw)` |
| Mobile | `100vw` (full-screen overlay) |

The nested `.doc-detail` panel currently positions itself with `right: min(420px, 100vw)`, which would push it off-screen behind a full-width mobile drawer. On mobile and tablet it becomes:

```css
@media (max-width: 1024px) {
  .doc-detail {
    right: 0;
    z-index: 3;          /* slides on top of the drawer */
  }
}
```

The close button (`◀`) takes the user back to the drawer list, as it does today.

`.drawer-head` and `.drawer-body` padding tightens on mobile:

```css
@media (max-width: 640px) {
  .drawer-head { padding: 16px 18px; }
  .drawer-body { padding: 10px; }
  .doc-row { padding: 12px; }
}
```

## Welcome / suggest grid

`.suggest-grid` already collapses to a single column at the existing 980px breakpoint. Re-anchored to 640px so tablets get the two-column treatment. Welcome vertical rhythm tightens on mobile so the keyboard does not overflow content:

```css
@media (max-width: 640px) {
  .welcome { padding: 16px 12px 8px; }
  .welcome-pill { margin-bottom: 18px; }
  .welcome-sub { margin: 0 0 20px; font-size: 15px; }
  .suggest-grid { grid-template-columns: 1fr; max-width: 100%; }
  .civic-left.idle { padding-bottom: 18vh; }   /* was 32vh — too much on phones */
}

@media (min-width: 641px) and (max-width: 1024px) {
  .suggest-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
```

`.hello` already uses `clamp(38px, 5.5vw, 64px)` so typography scales automatically.

## RightPane content

### DocPaper

```css
@media (max-width: 1024px) {
  .doc-paper { padding: 22px 20px; }
  .doc-paper-detail { padding: 28px 24px; }
}
@media (max-width: 640px) {
  .doc-paper { padding: 18px 14px; font-size: 12.5px; }
  .doc-paper-detail { padding: 20px 16px; }
  .doc-label { width: 42%; padding-right: 10px; font-size: 10.5px; }
  .doc-value { font-size: 12.5px; }
  .doc-title { font-size: 14px; margin-bottom: 12px; }
}
```

### DocPaper foot (signatures)

Stacks vertically on mobile so the two signature lines do not get crushed:

```css
@media (max-width: 640px) {
  .doc-foot { grid-template-columns: 1fr; gap: 18px; }
}
```

### `.doc-detail-meta` (the Emis / Trimis / Verificat row)

```css
@media (max-width: 640px) {
  .doc-detail-meta { grid-template-columns: repeat(2, 1fr); }
  .doc-detail-meta > :last-child { grid-column: span 2; }
}
```

### `.docpane-actions`

Already has `flex-wrap: wrap`. Confirmed sufficient — no change.

## Login + OTP pages

`/login` and `/login/otp`:

- The outer `<main className="flex min-h-screen items-center justify-center p-6">` becomes `flex min-h-screen items-center justify-center p-4 sm:p-6` so the card has room on 320px screens.
- `OtpInput` already overrides `Input` with `text-2xl` (24px), so iOS zoom-on-focus is not a concern there. No change needed.
- No structural changes.

## KioskShell + KioskLogin

Defensive responsiveness — kiosk mode is intended for large touchscreens but should not break on a phone:

```css
/* Inline Tailwind utilities adjusted in KioskShell.tsx */
header.kiosk-header   "flex items-center justify-between border-b px-4 py-3 sm:px-8 sm:py-4"
main.kiosk-main       "flex-1 overflow-auto px-4 py-4 sm:px-8 sm:py-8 [&_button]:min-h-[3rem] [&_input]:min-h-[3rem]"
h1                    "text-xl sm:text-3xl font-bold"
```

`KioskLogin` chooser buttons scale:

```tsx
<Button size="xl" className="h-24 text-xl sm:h-32 sm:text-2xl" ... />
```

MRZ scanner camera preview wrapper gets `max-w-full` so portrait phones don't overflow.

## UI primitives (`components/ui/`)

### Button (`button.tsx`)

Tap target floor added via a coarse-pointer modifier on the smaller sizes:

```ts
default: "h-10 px-4 py-2 [@media(pointer:coarse)]:min-h-[44px]"
sm:      "h-9 rounded-md px-3 [@media(pointer:coarse)]:min-h-[44px]"
icon:    "h-10 w-10 [@media(pointer:coarse)]:min-h-[44px] [@media(pointer:coarse)]:min-w-[44px]"
```

`lg` (h-12) and `xl` (h-14) are already ≥ 44px and need no change.

### Dialog (`dialog.tsx`)

`DialogContent` `max-w-lg` is too rigid for mobile. Updated to:

```ts
"max-w-[calc(100vw-1rem)] sm:max-w-lg"
"max-h-[90dvh] overflow-y-auto"
```

### Input (`input.tsx`)

Currently `h-10` (40px), `text-sm` (14px). Both updated:

```ts
"flex h-10 w-full ... text-base sm:text-sm [@media(pointer:coarse)]:min-h-[44px] ..."
```

### Textarea (`textarea.tsx`)

Currently `min-h-[80px]` (already touch-friendly) and `text-sm`. Only the font size needs updating:

```ts
"flex min-h-[80px] w-full ... text-base sm:text-sm ..."
```

### Toast (`toast.tsx`)

The current viewport wrapper at line 44 is:

```tsx
"pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2"
```

Updated to span the full width on mobile:

```tsx
"pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col gap-2 sm:inset-x-auto sm:right-4 sm:max-w-[420px]"
```

### Card (`card.tsx`)

No changes — `Card` is a flex/padding wrapper that already scales with its parent. Login pages already constrain the card with `max-w-md` and a centered flex container.

## Testing matrix

Manual verification at three reference viewports during implementation:

| Device class | Viewport (px) | What to verify |
|---|---|---|
| iPhone SE | 375 × 667 | Tap targets ≥ 44px; composer not under URL bar; tab toggle works; drawer is full-width; doc-paper readable |
| iPad portrait | 768 × 1024 | Split layout present with narrower right pane; drawer is ~440px; suggest grid is 2-column |
| Desktop | 1440 × 900 | Pixel-identical to current main branch |

Plus DevTools Responsive mode with "Simulate touch events" enabled to confirm the `pointer: coarse` sizing applies correctly.

Smoke check golden path on mobile after implementation:
1. Open `/`, see welcome single-column
2. Type a message → engaged state, segmented toggle appears
3. Tap "Document" → chat hides, doc preview shows
4. Tap "Chat" → reverse
5. Open Documents drawer → full-screen overlay
6. Tap a document row → detail panel slides over drawer; back button works

## Out of scope (deferred)

- Visual redesign of any component
- Replacing `framer-motion` animations with CSS for performance
- Dark mode tuning (a separate concern, already partially scaffolded by `[data-theme="dark"]` in `globals.css`)
- Performance work (bundle size, CLS, etc.)
- Adding component tests for the new mobile toggle (the existing test suite is largely skipped per the README; not adding scope here)

## Files touched

- `frontend/app/globals.css` — new media queries, new `--bp-*` tokens, scoped overrides for topbar / composer / drawer / welcome / doc-paper / suggest-grid
- `frontend/components/chat/ChatSurface.tsx` — `mobileView` state, `MobileViewToggle` mount, `data-mobile-view` attribute, doc-hint effect
- `frontend/components/chat/MobileViewToggle.tsx` — **new file**, two-segment pill
- `frontend/components/chat/TopBar.tsx` — wrap chip text labels in `<span className="chip-text">`
- `frontend/components/KioskShell.tsx` — responsive Tailwind utilities for header / main
- `frontend/app/login/page.tsx` — outer main padding tweak; KioskLogin button sizing
- `frontend/app/login/otp/page.tsx` — outer main padding tweak
- `frontend/components/ui/button.tsx` — touch target floor
- `frontend/components/ui/dialog.tsx` — mobile width and max-height
- `frontend/components/ui/input.tsx` — mobile font size + touch target
- `frontend/components/ui/textarea.tsx` — mobile font size + touch target
- `frontend/components/ui/toast.tsx` — mobile viewport positioning

No backend, no contracts, no migrations.
