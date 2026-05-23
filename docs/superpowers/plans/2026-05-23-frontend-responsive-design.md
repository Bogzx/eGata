# Frontend Responsive Design Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the eGata frontend usable on mobile (≤640px), tablet (641–1024px), and desktop (≥1025px) via CSS-only refinement of `app/globals.css`, plus a small mobile Chat/Document segmented toggle in `ChatSurface`.

**Architecture:** Approach A from the spec — extend `globals.css` with new `@media` blocks, introduce one piece of React state (`mobileView`) in `ChatSurface`, render a new `MobileViewToggle` component, and adjust the `components/ui/` primitives for touch targets and mobile sizing. Desktop layout above 1024px is preserved byte-for-byte.

**Tech Stack:** Next.js 15, React 19, Tailwind CSS 3.4, vanilla CSS (custom properties + `@media`), Vitest + Testing Library for the one unit test, manual browser verification at three viewports.

**Spec:** `docs/superpowers/specs/2026-05-23-frontend-responsive-design.md`

---

## File Structure

**New files:**

| File | Purpose |
|---|---|
| `frontend/components/chat/MobileViewToggle.tsx` | Two-segment pill that toggles `chat` / `doc` view on mobile; pure controlled component (props in, callback out) |
| `frontend/components/chat/__tests__/MobileViewToggle.test.tsx` | Vitest unit test for the toggle (renders both segments, calls `onChange` on click, respects `hinted` prop) |

**Modified files:**

| File | What changes |
|---|---|
| `frontend/app/globals.css` | Add breakpoint custom properties, switch to `100dvh`, replace the existing `@media (max-width: 980px)` block with new mobile + tablet blocks, add segmented-control CSS, add hint keyframes |
| `frontend/components/chat/ChatSurface.tsx` | Add `mobileView` state + `docHinted` effect, render `MobileViewToggle`, write `data-mobile-view` attribute to `.civic-root` |
| `frontend/components/chat/TopBar.tsx` | Wrap chip text labels (`"Documentele mele"`, profile name) in `<span className="chip-text">` so CSS can hide them on mobile |
| `frontend/components/KioskShell.tsx` | Responsive Tailwind utilities for header padding and h1 sizing |
| `frontend/app/login/page.tsx` | Outer `<main>` padding `p-6` → `p-4 sm:p-6`; kiosk chooser buttons scale from `h-32 text-2xl` to `h-24 text-xl sm:h-32 sm:text-2xl` |
| `frontend/app/login/otp/page.tsx` | Outer `<main>` padding `p-6` → `p-4 sm:p-6` |
| `frontend/components/ui/button.tsx` | Coarse-pointer `min-h-[44px]` on `default`/`sm`/`icon` size variants |
| `frontend/components/ui/dialog.tsx` | `DialogContent` width `max-w-lg` → `max-w-[calc(100vw-1rem)] sm:max-w-lg`; add `max-h-[90dvh] overflow-y-auto` |
| `frontend/components/ui/input.tsx` | Font `text-sm` → `text-base sm:text-sm`; add coarse-pointer min-height |
| `frontend/components/ui/textarea.tsx` | Font `text-sm` → `text-base sm:text-sm` |
| `frontend/components/ui/toast.tsx` | Viewport wrapper: full-width on mobile, restored to right-edge on `sm:` |

---

## Pre-flight

- [ ] **Step 0: Verify dev environment**

Run from `frontend/`:
```bash
cd frontend
npm run typecheck
npm test
```
Expected: typecheck passes; the existing `ChoiceWidget` test passes. If either fails on `main`, fix the baseline before starting.

---

### Task 1: Add foundation tokens and switch to dvh

**Files:**
- Modify: `frontend/app/globals.css` (lines 9-86 add tokens; line 178-184 update `.civic-root`; lines 1388-1409 remove old media block)

- [ ] **Step 1: Add breakpoint custom properties**

In `frontend/app/globals.css`, inside the `:root { }` block (between line 9 `@layer base { :root {` and the existing custom properties), add the two breakpoint tokens at the top so they sit with the other tokens. Insert after the `/* eGata palette */` comment block and before `/* Bridge to legacy shadcn tokens */`:

```css
    /* Responsive breakpoint tokens (used in human-readable comments,
       not in @media — @media cannot consume CSS custom properties). */
    --bp-mobile: 640px;
    --bp-tablet: 1024px;
```

- [ ] **Step 2: Update `.civic-root` to use dynamic viewport height**

Find the `.civic-root` rule (around line 178) and replace its `height: 100vh;` with:

```css
.civic-root {
  position: relative;
  height: 100vh;        /* fallback for older browsers */
  height: 100dvh;       /* dynamic viewport — accounts for mobile URL bar */
  width: 100%;
  overflow: hidden;
  isolation: isolate;
}
```

- [ ] **Step 3: Remove the existing 980px media block**

Find the `/* responsive */` comment near the end (around line 1388) and delete the entire `@media (max-width: 980px) { ... }` block. The new mobile and tablet blocks added in subsequent tasks will replace it.

Leave a placeholder comment in its place so subsequent tasks know where to append:

```css
/* =====================================================================
   Responsive — mobile (≤640px) and tablet (641-1024px). Desktop stays
   as-is above. New rules are appended by task.
   ===================================================================== */
```

- [ ] **Step 4: Verify the dev server still starts**

```bash
npm run dev
```
Open `http://localhost:3000` in a browser. The page should render identically to before at desktop width. Stop the server with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/globals.css
git commit -m "Add responsive tokens and switch civic-root to 100dvh"
```

---

### Task 2: Create MobileViewToggle component + unit test

**Files:**
- Create: `frontend/components/chat/MobileViewToggle.tsx`
- Create: `frontend/components/chat/__tests__/MobileViewToggle.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/components/chat/__tests__/MobileViewToggle.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MobileViewToggle } from "../MobileViewToggle";

describe("MobileViewToggle", () => {
  it("renders both segments with the active one aria-pressed", () => {
    render(<MobileViewToggle value="chat" onChange={() => {}} />);
    const chat = screen.getByRole("button", { name: /chat/i });
    const doc = screen.getByRole("button", { name: /document/i });
    expect(chat).toHaveAttribute("aria-pressed", "true");
    expect(doc).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onChange with the other view when the inactive segment is clicked", () => {
    const onChange = vi.fn();
    render(<MobileViewToggle value="chat" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /document/i }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("doc");
  });

  it("does not call onChange when the active segment is clicked", () => {
    const onChange = vi.fn();
    render(<MobileViewToggle value="chat" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /chat/i }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("adds the is-hinted class on the document segment when hinted", () => {
    render(<MobileViewToggle value="chat" onChange={() => {}} hinted />);
    const doc = screen.getByRole("button", { name: /document/i });
    expect(doc.className).toMatch(/is-hinted/);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
npm test -- MobileViewToggle
```
Expected: FAIL with a module-not-found error for `../MobileViewToggle`.

- [ ] **Step 3: Implement the component**

Create `frontend/components/chat/MobileViewToggle.tsx`:

```tsx
"use client";

export type MobileView = "chat" | "doc";

type Props = {
  value: MobileView;
  onChange: (next: MobileView) => void;
  /** When true, the inactive "Document" segment briefly pulses. */
  hinted?: boolean;
};

export function MobileViewToggle({ value, onChange, hinted = false }: Props) {
  return (
    <div className="mobile-toggle" role="group" aria-label="Comută între chat și document">
      <button
        type="button"
        className={
          "mobile-toggle-seg " + (value === "chat" ? "is-active" : "")
        }
        aria-pressed={value === "chat"}
        onClick={() => {
          if (value !== "chat") onChange("chat");
        }}
      >
        Chat
      </button>
      <button
        type="button"
        className={
          "mobile-toggle-seg " +
          (value === "doc" ? "is-active" : "") +
          (hinted && value !== "doc" ? " is-hinted" : "")
        }
        aria-pressed={value === "doc"}
        onClick={() => {
          if (value !== "doc") onChange("doc");
        }}
      >
        Document
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
npm test -- MobileViewToggle
```
Expected: 4 tests pass.

- [ ] **Step 5: Run typecheck**

```bash
npm run typecheck
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/chat/MobileViewToggle.tsx frontend/components/chat/__tests__/MobileViewToggle.test.tsx
git commit -m "Add MobileViewToggle segmented control"
```

---

### Task 3: Wire MobileViewToggle into ChatSurface

**Files:**
- Modify: `frontend/components/chat/ChatSurface.tsx`

- [ ] **Step 1: Add the import and types**

In `frontend/components/chat/ChatSurface.tsx`, at the top of the imports (after the React imports on line 3, before the `useRouter` import on line 4), add:

```tsx
import { MobileViewToggle, type MobileView } from "./MobileViewToggle";
```

- [ ] **Step 2: Add the new state and hint effect inside `ChatSurface`**

Inside the `ChatSurface` function, right after the `voice` constant declaration and `voiceStartedRef` (around line 53-54), add:

```tsx
const [mobileView, setMobileView] = useState<MobileView>("chat");
const [docHinted, setDocHinted] = useState(false);
```

The `useState` import is already in use on line 3 — no import change needed.

- [ ] **Step 3: Add the doc-hint effect**

After the existing `useEffect` blocks (after the auto-start voice effect, around line 121), add a new effect that pulses the Document segment when the session enters `filling` or `reviewing` while the user is on the Chat view:

```tsx
useEffect(() => {
  if (mobileView !== "chat") return;
  if (sessionState !== "filling" && sessionState !== "reviewing") return;
  setDocHinted(true);
  const t = window.setTimeout(() => setDocHinted(false), 1500);
  return () => window.clearTimeout(t);
}, [mobileView, sessionState]);
```

- [ ] **Step 4: Write the `data-mobile-view` attribute and render the toggle**

In the JSX `return`, find the `<div className="civic-root" ...>` (around line 194-199). Add the `data-mobile-view` attribute:

```tsx
<div
  className="civic-root"
  data-mode={engaged ? "engaged" : "idle"}
  data-kiosk={isKiosk ? "true" : "false"}
  data-mobile-view={mobileView}
>
```

Then find the `<TopBar ... />` line inside `.civic-shell` (around line 210) and add the toggle right after it, before `<ProfileMenu />`:

```tsx
<TopBar voiceOn={voiceActive} onToggleVoice={toggleVoice} />
{showRight ? (
  <MobileViewToggle
    value={mobileView}
    onChange={setMobileView}
    hinted={docHinted}
  />
) : null}
<ProfileMenu />
```

- [ ] **Step 5: Run typecheck and tests**

```bash
npm run typecheck
npm test
```
Expected: typecheck clean, all tests still pass (the `MobileViewToggle` test plus the existing `ChoiceWidget` test).

- [ ] **Step 6: Verify the dev server still renders correctly at desktop width**

```bash
npm run dev
```
Open `http://localhost:3000`. The toggle is in the DOM but should be invisible at desktop width (no CSS rule for `.mobile-toggle` exists yet — it will appear as default-styled buttons until Task 4). To confirm wiring: open the browser inspector, find `.civic-root`, and verify `data-mobile-view="chat"` is present. Stop the server.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/chat/ChatSurface.tsx
git commit -m "Wire MobileViewToggle into ChatSurface"
```

---

### Task 4: Layout shell responsive CSS

**Files:**
- Modify: `frontend/app/globals.css` (append to the placeholder block added in Task 1)

This is the largest CSS task — covers `.civic-main` grid, mobile visibility rules driven by `data-mobile-view`, the `.mobile-toggle` segmented control styling, and the hint keyframes.

- [ ] **Step 1: Append the mobile-toggle styles**

In `frontend/app/globals.css`, immediately after the responsive section comment from Task 1, append:

```css
/* ============ Mobile view toggle (only visible at ≤640px) ============ */

.mobile-toggle {
  display: none;
  align-items: center;
  gap: 4px;
  margin: 0 14px 8px;
  padding: 4px;
  background: var(--c-card-solid);
  border: 1px solid var(--c-line);
  border-radius: 999px;
  box-shadow: var(--shadow-card);
}
.mobile-toggle-seg {
  appearance: none;
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  color: var(--c-ink-soft);
  background: transparent;
  border: 0;
  padding: 8px 18px;
  border-radius: 999px;
  flex: 1;
  cursor: pointer;
  transition:
    background 0.2s ease,
    color 0.2s ease;
}
.mobile-toggle-seg.is-active {
  background: var(--c-dark);
  color: var(--c-bg);
  box-shadow: 0 4px 12px -6px rgba(31, 111, 95, 0.55);
}
.mobile-toggle-seg.is-hinted {
  animation: mobile-toggle-hint 1.5s ease-out 1;
}
@keyframes mobile-toggle-hint {
  0%, 100% { box-shadow: 0 0 0 0 rgba(47, 160, 132, 0.55); }
  50%      { box-shadow: 0 0 0 8px rgba(47, 160, 132, 0); }
}
```

- [ ] **Step 2: Append the tablet block (641-1024px)**

Continue appending:

```css
/* ============ Tablet (641-1024px) ============ */

@media (min-width: 641px) and (max-width: 1024px) {
  .civic-main.is-engaged {
    grid-template-columns: minmax(0, 1fr) minmax(320px, 420px);
  }
  .civic-main {
    padding: 0 20px 18px;
  }
  .topbar {
    padding: 14px 18px;
  }
}
```

- [ ] **Step 3: Append the mobile block (≤640px)**

Continue appending:

```css
/* ============ Mobile (≤640px) ============ */

@media (max-width: 640px) {
  .mobile-toggle {
    display: flex;
  }

  .civic-main {
    padding: 0 12px 12px;
  }
  .civic-main.is-engaged {
    grid-template-columns: 1fr;
  }

  /* Mobile view toggle: show left or right based on data-mobile-view. */
  .civic-root[data-mobile-view="chat"] .civic-right { display: none; }
  .civic-root[data-mobile-view="doc"]  .civic-left  { display: none; }
  .civic-root[data-mobile-view="doc"]  .civic-right { display: flex; }
  .civic-root[data-mobile-view="doc"]  .composer    { display: none; }
}
```

- [ ] **Step 4: Verify at three widths**

```bash
npm run dev
```

Open `http://localhost:3000` and resize the window:
- **≥1025px**: looks identical to before; mobile toggle not visible
- **641-1024px**: right pane is present but narrower (~320-420px); mobile toggle not visible
- **≤640px**: mobile toggle pill appears under the TopBar; clicking "Document" hides the chat and shows the right pane; clicking "Chat" reverses it

If the right pane shows nothing in `doc` view, it's because the session hasn't engaged yet (need to send a message). That's expected — the toggle only renders when `showRight` is true.

Stop the server.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/globals.css
git commit -m "Add responsive layout shell and mobile view toggle CSS"
```

---

### Task 5: TopBar responsive

**Files:**
- Modify: `frontend/components/chat/TopBar.tsx`
- Modify: `frontend/app/globals.css` (append)

- [ ] **Step 1: Wrap chip text labels in TopBar**

In `frontend/components/chat/TopBar.tsx`, wrap the text inside the "Documentele mele" chip and the profile chip with `<span className="chip-text">` so CSS can hide them on mobile.

Around line 102, change:
```tsx
<span>Documentele mele</span>
```
to:
```tsx
<span className="chip-text">Documentele mele</span>
```

Around line 148, change:
```tsx
<span>{profileLabel}</span>
```
to:
```tsx
<span className="chip-text">{profileLabel}</span>
```

The `.brand-sub` span at line 36 already has its own class — no change needed there, just a CSS rule.

- [ ] **Step 2: Append the TopBar mobile rules to globals.css**

In `frontend/app/globals.css`, inside the existing `@media (max-width: 640px) { ... }` block from Task 4, add the TopBar rules. Append before the closing `}`:

```css
  /* ---- TopBar ---- */
  .topbar {
    padding: 12px 14px;
    gap: 8px;
  }
  .chip {
    padding: 8px;
    gap: 6px;
  }
  .chip .chip-text {
    display: none;
  }
  .brand-sub {
    display: none;
  }
  .brand-mark {
    width: 32px;
    height: 32px;
  }
```

- [ ] **Step 3: Run typecheck**

```bash
npm run typecheck
```
Expected: no errors.

- [ ] **Step 4: Visually verify at mobile width**

```bash
npm run dev
```

Open the page at 375px (DevTools responsive mode). The TopBar should show:
- Brand mark (32px) + "eGata" name only (no "Primărie · România" sub-label)
- "Documentele mele" chip collapsed to icon-only with badge
- Voice chip icon-only (was already)
- Profile chip with avatar circle + caret only (no name)

Hover/tap the chips and confirm `aria-label` still reads correctly (use a screen reader or inspect the DOM).

Stop the server.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/chat/TopBar.tsx frontend/app/globals.css
git commit -m "Collapse TopBar chips to icons on mobile"
```

---

### Task 6: Composer responsive

**Files:**
- Modify: `frontend/app/globals.css` (append)

The composer markup itself is fine — only CSS changes. Hit targets bumped to 44px on touch devices; mobile padding tightens; input font goes to 16px to prevent iOS zoom-on-focus.

- [ ] **Step 1: Append coarse-pointer hit target rules**

In `frontend/app/globals.css`, after the `@media (max-width: 640px) { ... }` block from Tasks 4-5, add a separate block for coarse pointers:

```css
/* ============ Touch targets on coarse pointers ============ */

@media (pointer: coarse) {
  .composer-mic,
  .composer-send {
    width: 44px;
    height: 44px;
  }
  .composer-attach {
    padding: 12px;
  }
}
```

- [ ] **Step 2: Append composer mobile padding rules**

Inside the existing `@media (max-width: 640px) { ... }` block, append (before the closing brace):

```css
  /* ---- Composer ---- */
  .composer {
    padding: 6px 12px 14px;
  }
  .composer-shell {
    padding: 4px 4px 4px 12px;
  }
  .composer-input {
    font-size: 16px; /* prevent iOS zoom-on-focus */
  }
```

- [ ] **Step 3: Verify visually**

```bash
npm run dev
```

At 375px:
- The composer pill spans the available width with reasonable padding
- Tap the composer input — should not trigger iOS zoom on a real phone (you can only verify on a real device; the 16px rule is the correct way to prevent it)
- Mic and send buttons should appear ~44px tall when DevTools "Simulate touch events" is enabled

Stop the server.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/globals.css
git commit -m "Bump composer touch targets and prevent iOS zoom"
```

---

### Task 7: DocumentsDrawer and doc-detail responsive

**Files:**
- Modify: `frontend/app/globals.css` (append)

The drawer width and the slide-over doc-detail panel both need mobile/tablet handling. The drawer becomes full-width on mobile, ~440px on tablet. The `.doc-detail` slides over with `right: 0` below 1024px so it doesn't fall off-screen.

- [ ] **Step 1: Append a 1024px-and-below block for the doc-detail panel**

In `frontend/app/globals.css`, after the existing coarse-pointer block from Task 6, add:

```css
/* ============ Drawer + doc-detail responsive ============ */

@media (max-width: 1024px) {
  .doc-detail {
    right: 0;
    z-index: 3;          /* slides on top of the drawer */
  }
}
```

- [ ] **Step 2: Add tablet drawer width**

Inside the existing tablet block from Task 4 (`@media (min-width: 641px) and (max-width: 1024px)`), append before the closing brace:

```css
  /* ---- Drawer (tablet) ---- */
  .drawer {
    width: min(440px, 88vw);
  }
```

- [ ] **Step 3: Add mobile drawer width and tighter padding**

Inside the existing mobile block (`@media (max-width: 640px)`), append before the closing brace:

```css
  /* ---- Drawer (mobile) ---- */
  .drawer {
    width: 100vw;
  }
  .drawer-head {
    padding: 16px 18px;
  }
  .drawer-body {
    padding: 10px;
  }
  .doc-row {
    padding: 12px;
  }
```

- [ ] **Step 4: Verify at three viewport widths**

```bash
npm run dev
```

- **Desktop**: open the drawer (My Documents chip) → 420px wide overlay from the right
- **Tablet (768px)**: drawer is ~440px wide (~57% of screen)
- **Mobile (375px)**: drawer takes the full screen; tap a document → doc-detail slides over from the right at full width; back arrow returns to the drawer list

Stop the server.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/globals.css
git commit -m "Make drawer full-width on mobile and tablet-friendly"
```

---

### Task 8: Welcome and suggest-grid responsive

**Files:**
- Modify: `frontend/app/globals.css` (append)

The welcome screen needs tighter vertical rhythm on mobile and the suggest grid should explicitly be 2-column on tablet, 1-column on mobile.

- [ ] **Step 1: Append welcome and suggest rules**

Inside the existing mobile block (`@media (max-width: 640px)`), append before the closing brace:

```css
  /* ---- Welcome / suggestions ---- */
  .welcome {
    padding: 16px 12px 8px;
  }
  .welcome-pill {
    margin-bottom: 18px;
  }
  .welcome-sub {
    margin: 0 0 20px;
    font-size: 15px;
  }
  .suggest-grid {
    grid-template-columns: 1fr;
    max-width: 100%;
  }
  .civic-left.idle {
    padding-bottom: 18vh;
  }
```

Inside the existing tablet block (`@media (min-width: 641px) and (max-width: 1024px)`), append:

```css
  /* ---- Suggestions (tablet) ---- */
  .suggest-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    max-width: 600px;
  }
```

- [ ] **Step 2: Verify the welcome screen at three widths**

```bash
npm run dev
```

- **Desktop**: 2-column suggest grid centered, `.civic-left.idle` pads bottom by 32vh as before
- **Tablet (768px)**: 2-column suggest grid, slightly narrower
- **Mobile (375px)**: single-column suggest grid, welcome heading fits above the composer, less bottom padding so content sits comfortably above the keyboard area

Stop the server.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "Tighten welcome rhythm and stack suggest grid on mobile"
```

---

### Task 9: RightPane content (DocPaper, fields, foot, meta) responsive

**Files:**
- Modify: `frontend/app/globals.css` (append)

The doc-paper element renders the form preview. On smaller screens it needs less padding, the field label column needs to shrink, and the signatures need to stack vertically.

- [ ] **Step 1: Append doc-paper tablet rules**

Inside the existing tablet block (`@media (min-width: 641px) and (max-width: 1024px)`), append before the closing brace:

```css
  /* ---- DocPaper (tablet) ---- */
  .doc-paper {
    padding: 22px 20px;
  }
  .doc-paper-detail {
    padding: 28px 24px;
  }
```

- [ ] **Step 2: Append doc-paper mobile rules**

Inside the existing mobile block (`@media (max-width: 640px)`), append before the closing brace:

```css
  /* ---- DocPaper (mobile) ---- */
  .doc-paper {
    padding: 18px 14px;
    font-size: 12.5px;
  }
  .doc-paper-detail {
    padding: 20px 16px;
  }
  .doc-title {
    font-size: 14px;
    margin-bottom: 12px;
  }
  .doc-label {
    width: 42%;
    padding-right: 10px;
    font-size: 10.5px;
  }
  .doc-value {
    font-size: 12.5px;
  }
  .doc-foot {
    grid-template-columns: 1fr;
    gap: 18px;
  }
  .doc-detail-meta {
    grid-template-columns: repeat(2, 1fr);
  }
  .doc-detail-meta > :last-child {
    grid-column: span 2;
  }
  .docpane-head {
    padding: 18px 18px 12px;
  }
  .docpane-doc {
    padding: 14px 14px;
  }
  .docpane-title {
    font-size: 18px;
  }
```

- [ ] **Step 3: Verify the doc preview at mobile width**

```bash
npm run dev
```

Steps to reach a filled doc preview on mobile:
1. Resize browser to 375px
2. Log in as Maria (`123456` OTP)
3. Send "vreau să-mi schimb domiciliul" in the chat
4. Pick the schimbare-domiciliu match
5. Tap the "Document" segment in the mobile toggle
6. Inspect: the doc-paper should fit comfortably with no horizontal overflow; field labels should be readable; signature blocks (if visible) stack vertically

If the doc-paper overflows horizontally, increase the mobile rule's right-padding or further reduce `font-size`.

Stop the server.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/globals.css
git commit -m "Scale DocPaper padding and typography for tablet and mobile"
```

---

### Task 10: UI primitives — Button, Input, Textarea, Dialog, Toast

**Files:**
- Modify: `frontend/components/ui/button.tsx`
- Modify: `frontend/components/ui/input.tsx`
- Modify: `frontend/components/ui/textarea.tsx`
- Modify: `frontend/components/ui/dialog.tsx`
- Modify: `frontend/components/ui/toast.tsx`

These are small, additive class changes. No tests needed; the primitives are visual.

- [ ] **Step 1: Button — add coarse-pointer min-height to `default`, `sm`, and `icon` sizes**

In `frontend/components/ui/button.tsx`, replace the `size` block (lines 19-26) with:

```ts
      size: {
        default: "h-10 px-4 py-2 [@media(pointer:coarse)]:min-h-[44px]",
        sm: "h-9 rounded-md px-3 [@media(pointer:coarse)]:min-h-[44px]",
        lg: "h-12 rounded-md px-8 text-base",
        xl: "h-14 rounded-md px-10 text-lg",
        icon: "h-10 w-10 [@media(pointer:coarse)]:min-h-[44px] [@media(pointer:coarse)]:min-w-[44px]",
      },
```

- [ ] **Step 2: Input — add `text-base sm:text-sm` and coarse-pointer min-height**

In `frontend/components/ui/input.tsx`, replace the `className` value (lines 12-14) with:

```ts
        className={cn(
          "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-base ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 sm:text-sm [@media(pointer:coarse)]:min-h-[44px]",
          className,
        )}
```

- [ ] **Step 3: Textarea — add `text-base sm:text-sm`**

In `frontend/components/ui/textarea.tsx`, replace the `className` value (lines 11-13) with:

```ts
        className={cn(
          "flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-base ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 sm:text-sm",
          className,
        )}
```

- [ ] **Step 4: Dialog — make content responsive**

In `frontend/components/ui/dialog.tsx`, replace the `DialogContent` `className` (lines 32-35) with:

```ts
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-[calc(100vw-1rem)] translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg sm:max-w-lg sm:rounded-lg max-h-[90dvh] overflow-y-auto",
        className,
      )}
```

- [ ] **Step 5: Toast — make viewport full-width on mobile**

In `frontend/components/ui/toast.tsx`, replace the toast viewport `className` (line 44) with:

```tsx
        className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col gap-2 sm:inset-x-auto sm:right-4 sm:max-w-[420px]"
```

- [ ] **Step 6: Run typecheck and tests**

```bash
npm run typecheck
npm test
```
Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/ui/button.tsx frontend/components/ui/input.tsx frontend/components/ui/textarea.tsx frontend/components/ui/dialog.tsx frontend/components/ui/toast.tsx
git commit -m "Make UI primitives touch- and mobile-friendly"
```

---

### Task 11: Login + OTP page padding

**Files:**
- Modify: `frontend/app/login/page.tsx`
- Modify: `frontend/app/login/otp/page.tsx`

- [ ] **Step 1: LoginPage — outer main padding**

In `frontend/app/login/page.tsx`, find the `<main>` element in the default export (line 96):

```tsx
<main className="flex min-h-screen items-center justify-center p-6">
```

Replace with:

```tsx
<main className="flex min-h-screen items-center justify-center p-4 sm:p-6">
```

- [ ] **Step 2: KioskLogin chooser buttons — scale for small screens**

In the same file, find the two chooser buttons inside `KioskLogin` (around lines 59-69):

```tsx
<Button size="xl" className="h-32 text-2xl" onClick={() => setPath("roeid")}>
  {t("login.roeid_button")}
</Button>
<Button
  size="xl"
  variant="outline"
  className="h-32 text-2xl"
  onClick={() => setPath("mrz")}
>
  {t("login.scan_id_button")}
</Button>
```

Update both `className` values to scale down on mobile:

```tsx
<Button size="xl" className="h-24 text-xl sm:h-32 sm:text-2xl" onClick={() => setPath("roeid")}>
  {t("login.roeid_button")}
</Button>
<Button
  size="xl"
  variant="outline"
  className="h-24 text-xl sm:h-32 sm:text-2xl"
  onClick={() => setPath("mrz")}
>
  {t("login.scan_id_button")}
</Button>
```

- [ ] **Step 3: OtpPage — outer main padding**

In `frontend/app/login/otp/page.tsx`, find the `<main>` element in `OtpPage` (line 50):

```tsx
<main className="flex min-h-screen items-center justify-center p-6">
```

Replace with:

```tsx
<main className="flex min-h-screen items-center justify-center p-4 sm:p-6">
```

- [ ] **Step 4: Visually verify the login pages on mobile**

```bash
npm run dev
```

At 375px:
- `/login` — the LoginCard fills most of the width with breathing room around it (not crushed against edges)
- `/login/otp?challenge_id=test&phone_hint=07XXX` — same treatment; OTP input cells are large enough to tap

Stop the server.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/login/page.tsx frontend/app/login/otp/page.tsx
git commit -m "Add mobile padding to login and OTP pages"
```

---

### Task 12: KioskShell + KioskLogin responsive utilities

**Files:**
- Modify: `frontend/components/KioskShell.tsx`

- [ ] **Step 1: Update header, main, and h1 classes**

In `frontend/components/KioskShell.tsx`, replace the entire returned JSX (lines 17-40) with:

```tsx
  return (
    <div className="fixed inset-0 flex flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b px-4 py-3 sm:px-8 sm:py-4">
        <h1 className="text-xl sm:text-3xl font-bold">{t("app.title")}</h1>
        <Button
          variant="outline"
          size="lg"
          className="text-base sm:text-lg"
          onClick={() => setAccessibilityOpen((v) => !v)}
          aria-expanded={accessibilityOpen}
        >
          {t("kiosk.accessibility_corner")}
        </Button>
      </header>
      {accessibilityOpen ? (
        <section className="border-b bg-muted/30 px-4 py-4 sm:px-8 sm:py-6">
          <AccessibilityToggles />
        </section>
      ) : null}
      <main className="flex-1 overflow-auto px-4 py-4 sm:px-8 sm:py-8 [&_button]:min-h-[3rem] [&_input]:min-h-[3rem]">
        {children}
      </main>
    </div>
  );
```

- [ ] **Step 2: Verify the kiosk route on mobile**

```bash
npm run dev
```

Open `http://localhost:3000/login?kiosk=1` at 375px (the `?kiosk=1` query toggles kiosk mode — verify by checking `frontend/lib/kioskMode.ts` if unsure).

Expected:
- Header padding is `px-4 py-3` instead of `px-8 py-4`
- Title shrinks from `text-3xl` to `text-xl`
- Two large chooser buttons stack vertically (already do via `sm:grid-cols-2`); each is `h-24 text-xl` not `h-32 text-2xl`
- Accessibility section padding tightens
- Page does not horizontally scroll

Stop the server.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/KioskShell.tsx
git commit -m "Make KioskShell responsive for small screens"
```

---

### Task 13: Verification matrix

**Files:** none.

This task confirms the spec's testing matrix end-to-end. Run the dev server once and walk through each viewport with the golden-path scenario.

- [ ] **Step 1: Start the dev server**

```bash
cd frontend
npm run dev
```

- [ ] **Step 2: Desktop verification (1440 × 900)**

Resize the browser to 1440×900 (or close to it). Walk:
1. Open `http://localhost:3000` → redirects to `/login`
2. Sign in as Maria, OTP `123456`
3. Home: split-pane layout, welcome screen on the left, no document
4. Type "schimbare domiciliu" → engages, suggestion list appears
5. Pick the procedure → fills, right pane shows DocPaper
6. Verify: mobile toggle is NOT visible, layout matches main branch pixel-for-pixel

- [ ] **Step 3: Tablet verification (768 × 1024 portrait)**

Switch DevTools to a tablet preset (iPad 768×1024). Walk:
1. Refresh the page
2. Verify: split layout is present but the right pane is noticeably narrower (~360-420px instead of 420-560px)
3. Open the Documents drawer → ~440px wide, not full screen
4. Click a document → doc-detail slides over the drawer from the right at full drawer width

- [ ] **Step 4: Mobile verification (iPhone SE 375 × 667)**

Switch DevTools to iPhone SE preset. Walk:
1. Refresh — welcome shows single column, no suggest grid sprawl, composer pinned at bottom
2. Send a message → mobile toggle appears under TopBar with "Chat" active
3. Tap "Document" → chat hides, right pane fills width, composer disappears (no input while viewing doc)
4. Tap "Chat" → reverse
5. Open the Documents drawer → full-screen overlay
6. Tap a document → doc-detail slides over at full width; back arrow returns to drawer list
7. Open `/login` in a fresh tab at 375px → card has padding, not crushed
8. Tap the composer input → it should NOT zoom on a real iOS device (font-size: 16px verified earlier); in DevTools just confirm font size

- [ ] **Step 5: Reduced motion check**

Toggle DevTools rendering tab → "Emulate CSS prefers-reduced-motion: reduce". Send a message and confirm the segment hint pulse on the toggle is suppressed (no animation), same as existing pulse/dot animations.

- [ ] **Step 6: Coarse pointer check**

In DevTools → "Sensors" tab → enable touch event simulation, or "Rendering" → "Emulate CSS media (pointer: coarse)". Verify:
- Composer mic/send buttons are 44×44 (inspect element)
- Button primitive (default size) has min-h 44px
- Input primitive has min-h 44px

- [ ] **Step 7: Typecheck + tests pass**

```bash
npm run typecheck
npm test
```
Expected: typecheck clean, both MobileViewToggle and ChoiceWidget tests pass.

- [ ] **Step 8: Final commit — only if any tweaks were needed**

If verification surfaced visible bugs, fix them inline and commit as their own focused change. If the matrix passes cleanly, no commit is needed for this task.

```bash
# (only if there were fixes)
git add frontend/...
git commit -m "<describe the fix>"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Implementing task(s) |
|---|---|
| Breakpoints (`--bp-mobile`, `--bp-tablet`) | Task 1 |
| ChatSurface mobile view toggle (state, attr, mount, hint) | Tasks 2, 3 |
| MobileViewToggle component | Tasks 2, 4 (CSS) |
| Layout grid (`.civic-main` cols, padding) | Task 4 |
| Viewport height (100dvh) | Task 1 |
| TopBar (chip text, padding, brand-sub) | Task 5 |
| Composer (touch targets, padding, font-size) | Task 6 |
| DocumentsDrawer + doc-detail | Task 7 |
| Welcome + suggest grid | Task 8 |
| RightPane DocPaper / fields / foot / meta | Task 9 |
| Login + OTP padding | Task 11 |
| KioskShell + KioskLogin | Tasks 11, 12 |
| UI primitives (Button, Input, Textarea, Dialog, Toast) | Task 10 |
| Testing matrix | Task 13 |

All spec sections have at least one task. No gaps.

**Placeholder scan:** No `TBD`, `TODO`, "implement later", or "similar to Task N" references. Each task contains the exact code to write or change.

**Type consistency:** `MobileView` type defined in Task 2 (`MobileViewToggle.tsx`), imported and used in Task 3 (`ChatSurface.tsx`). The `hinted` prop is defined as `boolean | undefined` in the component and passed from `docHinted` state in the parent — consistent. `data-mobile-view` attribute is written in Task 3 and consumed by CSS selectors in Task 4 with matching string literals (`"chat"` / `"doc"`).
