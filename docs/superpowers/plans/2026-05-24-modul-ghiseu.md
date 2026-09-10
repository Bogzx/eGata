# Modul Ghișeu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the voice-only "Modul Ghișeu" kiosk page (`/ghiseu`) opt-in from a slide toggle on `/login`, implementing all 9 design states with a scripted state machine and a clean seam for the real voice bridge.

**Architecture:** Standalone Next.js route `/ghiseu` with its own component tree under `frontend/components/ghiseu/`, scoped CSS port of `voice-styles.css` (prefixed `.gh-*`), Zustand store with `setTimeout`-driven state machine, login page gets a `ModulGhiseuToggle` whose preference (localStorage `egata.ghiseu`) drives the post-OTP redirect.

**Tech Stack:** Next.js 15 App Router, React 19, TypeScript, Tailwind (for the toggle only), plain CSS module (for `/ghiseu`), Zustand, Vitest + Testing Library, Onest + JetBrains Mono via `next/font`.

**Spec:** `docs/superpowers/specs/2026-05-24-modul-ghiseu-design.md`

**Branch:** `feat/modul-ghiseu` (already created and checked out)

**Commands:** All test/typecheck commands run from `frontend/`. The repo uses npm (lockfile is `package-lock.json`).

---

## File Structure

### New files
| Path | Responsibility |
|---|---|
| `frontend/lib/ghiseuPref.ts` | Read/write `egata.ghiseu` localStorage toggle |
| `frontend/lib/__tests__/ghiseuPref.test.ts` | Test the pref helper |
| `frontend/lib/ghiseuStore.ts` | Zustand store + scripted state machine + bridge stub |
| `frontend/lib/__tests__/ghiseuStore.test.ts` | Test all state transitions |
| `frontend/components/ModulGhiseuToggle.tsx` | Login-page slide switch |
| `frontend/components/__tests__/ModulGhiseuToggle.test.tsx` | Test toggle persists |
| `frontend/components/ghiseu/icons.tsx` | SVG icon set ported from design |
| `frontend/components/ghiseu/AnimatedMesh.tsx` | Canvas blob background |
| `frontend/components/ghiseu/CaptionStrip.tsx` | Tu/eGata caption bubbles |
| `frontend/components/ghiseu/__tests__/CaptionStrip.test.tsx` | Render-by-state |
| `frontend/components/ghiseu/VoiceStage.tsx` | Status title + CaptionStrip + error icon |
| `frontend/components/ghiseu/__tests__/VoiceStage.test.tsx` | Title per state |
| `frontend/components/ghiseu/ControlsDock.tsx` | Mic + Interrupt buttons |
| `frontend/components/ghiseu/__tests__/ControlsDock.test.tsx` | Labels + disabled per state |
| `frontend/components/ghiseu/DocumentReview.tsx` | Doc-paper + 2-col fields + confirm/amend |
| `frontend/components/ghiseu/__tests__/DocumentReview.test.tsx` | Renders fields + fires callbacks |
| `frontend/components/ghiseu/ExportOptions.tsx` | 2 cards (primărie / email) |
| `frontend/components/ghiseu/__tests__/ExportOptions.test.tsx` | Renders + fires `onPick` |
| `frontend/components/ghiseu/DoneScreen.tsx` | Checkmark + ref number + restart |
| `frontend/components/ghiseu/__tests__/DoneScreen.test.tsx` | Renders ref + method copy |
| `frontend/components/ghiseu/GhiseuProfileMenu.tsx` | Accessibility dropdown |
| `frontend/components/ghiseu/__tests__/GhiseuProfileMenu.test.tsx` | Opens, toggles, persists |
| `frontend/components/ghiseu/GhiseuShell.tsx` | Top bar + main + dock + bg |
| `frontend/app/ghiseu/page.tsx` | Route entry, auth gate |
| `frontend/app/ghiseu/ghiseu.css` | Scoped styles port |

### Edited files
| Path | Change |
|---|---|
| `frontend/app/login/page.tsx` | Mount `<ModulGhiseuToggle />` above CTA in `LoginCard` and `KioskLogin` |
| `frontend/app/login/otp/page.tsx` | Redirect via `getGhiseuPref()` after `setSession` |

---

## Task 1: localStorage helper for the toggle preference

**Files:**
- Create: `frontend/lib/ghiseuPref.ts`
- Test: `frontend/lib/__tests__/ghiseuPref.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/lib/__tests__/ghiseuPref.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { getGhiseuPref, setGhiseuPref, GHISEU_PREF_KEY } from "../ghiseuPref";

beforeEach(() => {
  localStorage.clear();
});

describe("ghiseuPref", () => {
  it("returns false when no preference is stored", () => {
    expect(getGhiseuPref()).toBe(false);
  });

  it("returns true after setGhiseuPref(true)", () => {
    setGhiseuPref(true);
    expect(getGhiseuPref()).toBe(true);
    expect(localStorage.getItem(GHISEU_PREF_KEY)).toBe("1");
  });

  it("returns false after setGhiseuPref(false)", () => {
    setGhiseuPref(true);
    setGhiseuPref(false);
    expect(getGhiseuPref()).toBe(false);
    expect(localStorage.getItem(GHISEU_PREF_KEY)).toBe("0");
  });

  it("treats any other stored value as false", () => {
    localStorage.setItem(GHISEU_PREF_KEY, "garbage");
    expect(getGhiseuPref()).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- lib/__tests__/ghiseuPref.test.ts
```

Expected: FAIL — module `../ghiseuPref` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/lib/ghiseuPref.ts`:

```ts
export const GHISEU_PREF_KEY = "egata.ghiseu";

export function getGhiseuPref(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(GHISEU_PREF_KEY) === "1";
  } catch {
    return false;
  }
}

export function setGhiseuPref(value: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(GHISEU_PREF_KEY, value ? "1" : "0");
  } catch {
    // private browsing / quota — swallow
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test -- lib/__tests__/ghiseuPref.test.ts
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/ghiseuPref.ts frontend/lib/__tests__/ghiseuPref.test.ts
git commit -m "feat(ghiseu): add localStorage pref helper for Modul Ghișeu toggle"
```

---

## Task 2: Ghișeu store with scripted state machine

**Files:**
- Create: `frontend/lib/ghiseuStore.ts`
- Test: `frontend/lib/__tests__/ghiseuStore.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/lib/__tests__/ghiseuStore.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { useGhiseuStore } from "../ghiseuStore";

beforeEach(() => {
  useGhiseuStore.setState({
    state: "idle",
    muted: true,
    exportMethod: null,
  });
  vi.useFakeTimers();
});

afterEach(() => {
  useGhiseuStore.getState().reset();
  vi.useRealTimers();
});

describe("ghiseuStore initial state", () => {
  it("starts idle, muted, no export method", () => {
    const s = useGhiseuStore.getState();
    expect(s.state).toBe("idle");
    expect(s.muted).toBe(true);
    expect(s.exportMethod).toBeNull();
  });
});

describe("ghiseuStore toggleMute from idle", () => {
  it("unmutes and runs the scripted listening→thinking→speaking→review flow", () => {
    useGhiseuStore.getState().toggleMute();
    expect(useGhiseuStore.getState().muted).toBe(false);
    expect(useGhiseuStore.getState().state).toBe("listening");

    vi.advanceTimersByTime(2800);
    expect(useGhiseuStore.getState().state).toBe("thinking");

    vi.advanceTimersByTime(1500); // +4300 total
    expect(useGhiseuStore.getState().state).toBe("speaking");

    vi.advanceTimersByTime(3100); // +7400 total
    expect(useGhiseuStore.getState().state).toBe("review");
  });
});

describe("ghiseuStore mid-conversation mute", () => {
  it("flips muted without changing state when not in idle", () => {
    useGhiseuStore.setState({ state: "listening", muted: false });
    useGhiseuStore.getState().toggleMute();
    expect(useGhiseuStore.getState().muted).toBe(true);
    expect(useGhiseuStore.getState().state).toBe("listening");
  });
});

describe("ghiseuStore interrupt", () => {
  it("returns to listening and unmutes when called while speaking", () => {
    useGhiseuStore.setState({ state: "speaking", muted: true });
    useGhiseuStore.getState().interrupt();
    expect(useGhiseuStore.getState().state).toBe("listening");
    expect(useGhiseuStore.getState().muted).toBe(false);
  });
});

describe("ghiseuStore confirmDoc + amendDoc", () => {
  it("confirmDoc transitions review → export", () => {
    useGhiseuStore.setState({ state: "review" });
    useGhiseuStore.getState().confirmDoc();
    expect(useGhiseuStore.getState().state).toBe("export");
  });

  it("amendDoc transitions to listening then speaking after 1.8s", () => {
    useGhiseuStore.setState({ state: "review" });
    useGhiseuStore.getState().amendDoc();
    expect(useGhiseuStore.getState().state).toBe("listening");
    vi.advanceTimersByTime(1800);
    expect(useGhiseuStore.getState().state).toBe("speaking");
  });
});

describe("ghiseuStore pickExport", () => {
  it("transitions export → done and stores method", () => {
    useGhiseuStore.setState({ state: "export" });
    useGhiseuStore.getState().pickExport("city");
    expect(useGhiseuStore.getState().state).toBe("done");
    expect(useGhiseuStore.getState().exportMethod).toBe("city");
  });
});

describe("ghiseuStore backToTalk", () => {
  it("returns to listening and unmutes", () => {
    useGhiseuStore.setState({ state: "export", muted: true });
    useGhiseuStore.getState().backToTalk();
    expect(useGhiseuStore.getState().state).toBe("listening");
    expect(useGhiseuStore.getState().muted).toBe(false);
  });
});

describe("ghiseuStore reset", () => {
  it("returns to idle, mutes, clears export method", () => {
    useGhiseuStore.setState({ state: "done", muted: false, exportMethod: "email" });
    useGhiseuStore.getState().reset();
    expect(useGhiseuStore.getState().state).toBe("idle");
    expect(useGhiseuStore.getState().muted).toBe(true);
    expect(useGhiseuStore.getState().exportMethod).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- lib/__tests__/ghiseuStore.test.ts
```

Expected: FAIL — module `../ghiseuStore` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/lib/ghiseuStore.ts`:

```ts
"use client";

import { create } from "zustand";

export type GhiseuState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "review"
  | "export"
  | "done"
  | "error"
  | "mic-denied";

export type ExportMethod = "city" | "email" | null;

type GhiseuStore = {
  state: GhiseuState;
  muted: boolean;
  exportMethod: ExportMethod;
  setState(state: GhiseuState): void;
  toggleMute(): void;
  interrupt(): void;
  confirmDoc(): void;
  amendDoc(): void;
  pickExport(method: Exclude<ExportMethod, null>): void;
  backToTalk(): void;
  reset(): void;
  /**
   * Stub for the real voice bridge integration. v1 is a no-op; the
   * future implementation will subscribe to useVoiceAgentBridge events
   * and call the store transitions instead of the scripted timers below.
   */
  attachVoiceBridge(bridge: unknown): () => void;
};

function scriptedTalkingFlow(set: (patch: Partial<GhiseuStore>) => void): void {
  // listening → thinking → speaking → review (timing matches the design's
  // handleStartTalking in voice-app.jsx).
  set({ state: "listening" });
  setTimeout(() => set({ state: "thinking" }), 2800);
  setTimeout(() => set({ state: "speaking" }), 4300);
  setTimeout(() => set({ state: "review" }), 7400);
}

export const useGhiseuStore = create<GhiseuStore>((set, get) => ({
  state: "idle",
  muted: true,
  exportMethod: null,

  setState: (state) => set({ state }),

  toggleMute: () => {
    const { state, muted } = get();
    if (state === "idle" && muted) {
      set({ muted: false });
      scriptedTalkingFlow(set);
      return;
    }
    set({ muted: !muted });
  },

  interrupt: () => {
    set({ state: "listening", muted: false });
  },

  confirmDoc: () => set({ state: "export" }),

  amendDoc: () => {
    set({ state: "listening" });
    setTimeout(() => set({ state: "speaking" }), 1800);
  },

  pickExport: (method) => set({ state: "done", exportMethod: method }),

  backToTalk: () => set({ state: "listening", muted: false }),

  reset: () => set({ state: "idle", muted: true, exportMethod: null }),

  attachVoiceBridge: () => {
    // v1: no-op. v2 will wire useVoiceAgentBridge events into
    // setState/interrupt/etc., replacing scriptedTalkingFlow.
    return () => {};
  },
}));
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test -- lib/__tests__/ghiseuStore.test.ts
```

Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/ghiseuStore.ts frontend/lib/__tests__/ghiseuStore.test.ts
git commit -m "feat(ghiseu): scripted state machine store with bridge stub"
```

---

## Task 3: ModulGhiseuToggle slide switch for the login page

**Files:**
- Create: `frontend/components/ModulGhiseuToggle.tsx`
- Test: `frontend/components/__tests__/ModulGhiseuToggle.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/components/__tests__/ModulGhiseuToggle.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ModulGhiseuToggle } from "../ModulGhiseuToggle";
import { GHISEU_PREF_KEY } from "@/lib/ghiseuPref";

beforeEach(() => {
  localStorage.clear();
});

describe("ModulGhiseuToggle", () => {
  it("renders the Romanian label and hint", () => {
    render(<ModulGhiseuToggle />);
    expect(screen.getByText(/Modul Ghișeu/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Doar vorbește cu asistentul/i),
    ).toBeInTheDocument();
  });

  it("starts off (aria-checked=false) when no preference is stored", () => {
    render(<ModulGhiseuToggle />);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");
  });

  it("initializes from existing preference", () => {
    localStorage.setItem(GHISEU_PREF_KEY, "1");
    render(<ModulGhiseuToggle />);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });

  it("persists to localStorage when toggled", () => {
    render(<ModulGhiseuToggle />);
    fireEvent.click(screen.getByRole("switch"));
    expect(localStorage.getItem(GHISEU_PREF_KEY)).toBe("1");
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("switch"));
    expect(localStorage.getItem(GHISEU_PREF_KEY)).toBe("0");
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- components/__tests__/ModulGhiseuToggle.test.tsx
```

Expected: FAIL — module `../ModulGhiseuToggle` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/components/ModulGhiseuToggle.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { getGhiseuPref, setGhiseuPref } from "@/lib/ghiseuPref";

export function ModulGhiseuToggle() {
  const [checked, setChecked] = useState(false);

  // Initialize from localStorage after mount so SSR markup matches.
  useEffect(() => {
    setChecked(getGhiseuPref());
  }, []);

  function toggle() {
    const next = !checked;
    setChecked(next);
    setGhiseuPref(next);
  }

  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 rounded-xl border bg-card p-4">
      <span className="flex flex-col gap-1">
        <span className="text-base font-medium text-foreground">
          Modul Ghișeu
        </span>
        <span className="text-sm text-muted-foreground">
          Doar vorbește cu asistentul. Fără ecrane complicate.
        </span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label="Modul Ghișeu"
        onClick={(e) => {
          e.preventDefault();
          toggle();
        }}
        className={
          "relative h-7 w-12 flex-shrink-0 rounded-full transition-colors " +
          (checked ? "bg-primary" : "bg-muted")
        }
      >
        <span
          aria-hidden="true"
          className={
            "absolute top-0.5 left-0.5 h-6 w-6 rounded-full bg-white shadow transition-transform " +
            (checked ? "translate-x-5" : "translate-x-0")
          }
        />
      </button>
    </label>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test -- components/__tests__/ModulGhiseuToggle.test.tsx
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ModulGhiseuToggle.tsx frontend/components/__tests__/ModulGhiseuToggle.test.tsx
git commit -m "feat(ghiseu): ModulGhiseuToggle slide switch for login page"
```

---

## Task 4: Mount the toggle on the login page

**Files:**
- Modify: `frontend/app/login/page.tsx`

- [ ] **Step 1: Edit `LoginCard` to include the toggle above the login button**

Replace the existing `LoginCard` and the import block at the top of `frontend/app/login/page.tsx`. The change adds the `ModulGhiseuToggle` import and mounts it inside `CardContent` above `<LoginButton />`:

```tsx
"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoginButton } from "@/components/LoginButton";
import { ModulGhiseuToggle } from "@/components/ModulGhiseuToggle";
import { MrzScanner } from "@/components/MrzScanner";
import { KioskShell } from "@/components/KioskShell";
import { useKioskMode } from "@/lib/kioskMode";
import { api, ApiError } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { LoginChallenge } from "@/lib/types";
import type { MrzResult } from "@/lib/mrz";

function nav(router: ReturnType<typeof useRouter>, c: LoginChallenge) {
  const params = new URLSearchParams({
    challenge_id: c.challenge_id,
    phone_hint: c.phone_hint,
  });
  router.push(`/login/otp?${params.toString()}`);
}

function LoginCard({ onChallenge }: { onChallenge: (c: LoginChallenge) => void }) {
  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>{t("login.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">{t("login.subtitle")}</p>
        <ModulGhiseuToggle />
        <LoginButton onChallenge={onChallenge} />
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Edit `KioskLogin` to include the toggle above the chooser buttons**

In the same file, modify the `KioskLogin` function's return so the chooser branch shows the toggle above the two big buttons. Replace the existing chooser block:

```tsx
        {path === "chooser" ? (
          <div className="space-y-6">
            <ModulGhiseuToggle />
            <div className="grid gap-4 sm:grid-cols-2">
              <Button
                size="xl"
                className="h-24 text-xl sm:h-32 sm:text-2xl"
                onClick={() => setPath("roeid")}
              >
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
            </div>
          </div>
        ) : null}
```

The rest of `KioskLogin` and `LoginPage` is unchanged.

- [ ] **Step 3: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS, no errors.

- [ ] **Step 4: Run all tests to confirm no regression**

```bash
cd frontend && npm test
```

Expected: all tests still pass (the toggle and pref tests included).

- [ ] **Step 5: Commit**

```bash
git add frontend/app/login/page.tsx
git commit -m "feat(ghiseu): mount Modul Ghișeu toggle on login page"
```

---

## Task 5: OTP page redirects to /ghiseu when the toggle is on

**Files:**
- Modify: `frontend/app/login/otp/page.tsx`

- [ ] **Step 1: Edit the OTP page to read the pref and route accordingly**

Replace the `submit` function in `frontend/app/login/otp/page.tsx` with one that calls `getGhiseuPref()` after `setSession`. Add the import too:

```tsx
"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OtpInput } from "@/components/OtpInput";
import { api, ApiError } from "@/lib/api";
import { setSession } from "@/lib/session";
import { getGhiseuPref } from "@/lib/ghiseuPref";
import { t } from "@/lib/i18n";

function OtpForm() {
  const params = useSearchParams();
  const router = useRouter();
  const challengeId = params.get("challenge_id") ?? "";
  const phoneHint = params.get("phone_hint") ?? "";
  const [error, setError] = useState<string | null>(null);

  async function submit(code: string) {
    setError(null);
    try {
      const session = await api.otp({ challenge_id: challengeId, code });
      setSession(session);
      router.push(getGhiseuPref() ? "/ghiseu" : "/");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setError(t("otp.error"));
      } else {
        setError(t("common.error"));
      }
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>{t("otp.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {t("otp.phone_hint", { phone_hint: phoneHint })}
        </p>
        <OtpInput onComplete={submit} error={error} />
      </CardContent>
    </Card>
  );
}

export default function OtpPage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-4 sm:p-6">
      <Suspense fallback={null}>
        <OtpForm />
      </Suspense>
    </main>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/login/otp/page.tsx
git commit -m "feat(ghiseu): OTP redirects to /ghiseu when toggle is on"
```

---

## Task 6: Port voice-styles.css → app/ghiseu/ghiseu.css

**Files:**
- Create: `frontend/app/ghiseu/ghiseu.css`

The source lives at `C:\Users\2Usi\AppData\Local\Temp\claude-design\cluj-hackathon-audioonly\project\voice-styles.css`. The port is a verbatim copy with three changes:

1. Replace **every** `.vo-` selector prefix with `.gh-` (e.g. `.vo-root` → `.gh-root`, `.vo-status-text` → `.gh-status-text`, `.vo-pm-chip` → `.gh-pm-chip`). Use a global replace.
2. Remove the top-level `:root { --c-dark: ...; --c-mid: ...; ... --font-civic: ...; --font-mono: ...; }` block — these CSS variables are already declared in `app/globals.css` and would conflict if redeclared. Keep the `[data-bg="dark"] { ... }` block intact.
3. Remove the `*, *::before, *::after { box-sizing: border-box; } html, body { ... }` top reset — `globals.css` already sets these and re-applying `overflow: hidden` on `html, body` here would lock scrolling everywhere in the app, not just `/ghiseu`. Instead, set `.gh-root { overflow: hidden; }` (already present in the original).

- [ ] **Step 1: Create the file with the ported styles**

Copy `voice-styles.css` to `frontend/app/ghiseu/ghiseu.css`, then apply the three changes above. The file is ~1000 lines; do the prefix swap with a single editor replace (`.vo-` → `.gh-`). Verify after editing that no `.vo-` remains:

```bash
grep -c "\\.vo-" frontend/app/ghiseu/ghiseu.css
```

Expected: `0`.

- [ ] **Step 2: Typecheck (sanity — no TS impact, but ensures build still compiles)**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/ghiseu/ghiseu.css
git commit -m "feat(ghiseu): scoped CSS port of voice-styles.css"
```

---

## Task 7: Icon set for the Ghișeu page

**Files:**
- Create: `frontend/components/ghiseu/icons.tsx`

- [ ] **Step 1: Write the file**

These are the icons used by the design (`Mic`, `MicOff`, `Refresh`, `Stop`, `Check`, `Edit`, `Mail`, `City`, `Alert`, `MicSlash`, `Logo`). Strokes/fills match the design's `Icon` object verbatim.

Create `frontend/components/ghiseu/icons.tsx`:

```tsx
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function svg(size: number, children: React.ReactNode, props: Omit<IconProps, "size">) {
  const { width = size, height = size, ...rest } = props;
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const MicIcon = ({ size = 20, ...p }: IconProps) =>
  svg(size, <>
    <rect x="9" y="3" width="6" height="12" rx="3" />
    <path d="M5 11a7 7 0 0014 0M12 18v3" />
  </>, p);

export const MicOffIcon = ({ size = 20, ...p }: IconProps) =>
  svg(size, <>
    <line x1="3" y1="3" x2="21" y2="21" />
    <path d="M9 9v3a3 3 0 005.12 2.12M15 9.34V6a3 3 0 00-5.94-.6" />
    <path d="M19 10v2a7 7 0 01-.11 1.23M5 10v2a7 7 0 0012 5" />
    <line x1="12" y1="19" x2="12" y2="22" />
  </>, p);

export const RefreshIcon = ({ size = 18, ...p }: IconProps) =>
  svg(size, <>
    <path d="M3 12a9 9 0 0 1 15.5-6.3L21 8" />
    <path d="M21 3v5h-5" />
    <path d="M21 12a9 9 0 0 1-15.5 6.3L3 16" />
    <path d="M3 21v-5h5" />
  </>, p);

export const StopIcon = ({ size = 20, ...p }: IconProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
    focusable="false"
    {...p}
  >
    <rect x="7" y="5" width="3.5" height="14" rx="1" />
    <rect x="13.5" y="5" width="3.5" height="14" rx="1" />
  </svg>
);

export const CheckIcon = ({ size = 24, ...p }: IconProps) =>
  svg(size, <path d="M5 12l5 5L20 7" />, { ...p, strokeWidth: 2.4 });

export const EditIcon = ({ size = 22, ...p }: IconProps) =>
  svg(size, <>
    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
    <path d="M18.5 2.5a2.12 2.12 0 113 3L12 15l-4 1 1-4 9.5-9.5z" />
  </>, p);

export const MailIcon = ({ size = 24, ...p }: IconProps) =>
  svg(size, <>
    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
    <polyline points="22,6 12,13 2,6" />
  </>, p);

export const CityIcon = ({ size = 24, ...p }: IconProps) =>
  svg(size, <>
    <path d="M3 21h18" />
    <path d="M5 21V8l5-4 5 4v13" />
    <path d="M15 21v-7h4v7" />
    <path d="M9 14h2" />
    <path d="M9 18h2" />
  </>, p);

export const AlertIcon = ({ size = 40, ...p }: IconProps) =>
  svg(size, <>
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="8" x2="12" y2="12" />
    <line x1="12" y1="16" x2="12.01" y2="16" />
  </>, p);

export const MicSlashIcon = ({ size = 40, ...p }: IconProps) =>
  svg(size, <>
    <line x1="3" y1="3" x2="21" y2="21" />
    <path d="M9 9v3a3 3 0 005.12 2.12M15 9.34V6a3 3 0 00-5.94-.6" />
    <path d="M19 10v2a7 7 0 01-.11 1.23M5 10v2a7 7 0 0012 5" />
    <line x1="12" y1="19" x2="12" y2="22" />
  </>, p);

export const LogoIcon = ({ size = 20, ...p }: IconProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="#EEEEEE"
    strokeWidth={2.4}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    focusable="false"
    {...p}
  >
    <path d="M3 11l9-7 9 7" />
    <path d="M5 10v9h14v-9" />
    <path d="M10 19v-5h4v5" />
  </svg>
);
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ghiseu/icons.tsx
git commit -m "feat(ghiseu): SVG icon set"
```

---

## Task 8: Animated mesh background

**Files:**
- Create: `frontend/components/ghiseu/AnimatedMesh.tsx`

No unit test — canvas painting can't be meaningfully asserted in jsdom. Verified visually in the manual pass (Task 18).

- [ ] **Step 1: Write the component**

Create `frontend/components/ghiseu/AnimatedMesh.tsx`:

```tsx
"use client";

import { useEffect, useRef } from "react";

export type MeshPalette = {
  dark: string;
  mid: string;
  light: string;
  bg: string;
};

const GREEN: MeshPalette = {
  dark: "#1F6F5F",
  mid: "#2FA084",
  light: "#6FCF97",
  bg: "#EEEEEE",
};

type Props = {
  palette?: MeshPalette;
  dark?: boolean;
};

export function AnimatedMesh({ palette = GREEN, dark = false }: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const cvs = ref.current;
    if (!cvs) return;
    const ctx = cvs.getContext("2d");
    if (!ctx) return;

    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let w = 0;
    let h = 0;
    let raf = 0;
    let t = 0;

    function resize() {
      if (!cvs || !ctx) return;
      w = cvs.clientWidth;
      h = cvs.clientHeight;
      cvs.width = w * dpr;
      cvs.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(cvs);

    const pal = [palette.dark, palette.mid, palette.light, dark ? "#06120F" : palette.bg];

    function blob(cx: number, cy: number, r: number, color: string, alpha: number) {
      if (!ctx) return;
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
      g.addColorStop(0, color + "ff");
      g.addColorStop(0.55, color + "aa");
      g.addColorStop(1, color + "00");
      ctx.globalAlpha = alpha;
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    const orbs = [
      { c: pal[0], rx: 0.45, ry: 0.55, sx: 0.00045, sy: 0.00037, size: 0.55, a: dark ? 0.55 : 0.85 },
      { c: pal[1], rx: 0.30, ry: 0.40, sx: 0.00062, sy: 0.00051, size: 0.50, a: dark ? 0.50 : 0.80 },
      { c: pal[2], rx: 0.35, ry: 0.30, sx: 0.00073, sy: 0.00043, size: 0.45, a: dark ? 0.42 : 0.75 },
      { c: pal[1], rx: 0.25, ry: 0.50, sx: 0.00038, sy: 0.00060, size: 0.40, a: dark ? 0.40 : 0.70 },
      { c: pal[0], rx: 0.40, ry: 0.45, sx: 0.00029, sy: 0.00047, size: 0.50, a: dark ? 0.35 : 0.55 },
    ];

    function paint() {
      if (!ctx) return;
      ctx.fillStyle = pal[3];
      ctx.fillRect(0, 0, w, h);
      const cx = w / 2;
      const cy = h / 2;
      const R = Math.max(w, h);
      orbs.forEach((o, i) => {
        const px = cx + Math.cos(t * o.sx + i * 1.7) * (w * o.rx);
        const py = cy + Math.sin(t * o.sy + i * 2.3) * (h * o.ry);
        blob(px, py, R * o.size, o.c, o.a);
      });
    }

    if (reduced) {
      paint();
    } else {
      const frame = () => {
        t += 16;
        paint();
        raf = requestAnimationFrame(frame);
      };
      raf = requestAnimationFrame(frame);
    }

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [palette, dark]);

  return (
    <div className="gh-bg" aria-hidden="true">
      <canvas ref={ref} />
      <div className="gh-grain" />
      <div className="gh-vignette" />
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ghiseu/AnimatedMesh.tsx
git commit -m "feat(ghiseu): animated canvas mesh background"
```

---

## Task 9: CaptionStrip — Tu/eGata bubble pair

**Files:**
- Create: `frontend/components/ghiseu/CaptionStrip.tsx`
- Test: `frontend/components/ghiseu/__tests__/CaptionStrip.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/components/ghiseu/__tests__/CaptionStrip.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CaptionStrip } from "../CaptionStrip";

describe("CaptionStrip", () => {
  it("renders nothing in idle and shows only the agent greeting", () => {
    render(<CaptionStrip state="idle" />);
    expect(screen.getByText(/Bună! Spune-mi cu ce te pot ajuta/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Tu$/)).toBeNull();
  });

  it("renders both Tu and eGata bubbles in speaking", () => {
    render(<CaptionStrip state="speaking" />);
    expect(screen.getByText(/Tu/)).toBeInTheDocument();
    expect(screen.getByText(/eGata/)).toBeInTheDocument();
    expect(screen.getByText(/adeverința de venit/i)).toBeInTheDocument();
    expect(screen.getByText(/Am completat datele tale din ROeID/i)).toBeInTheDocument();
  });

  it("renders nothing when state is error", () => {
    const { container } = render(<CaptionStrip state="error" />);
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/CaptionStrip.test.tsx
```

Expected: FAIL — module `../CaptionStrip` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/components/ghiseu/CaptionStrip.tsx`:

```tsx
"use client";

import type { GhiseuState } from "@/lib/ghiseuStore";

type Line = { text: string; final?: boolean } | null;

type Transcript = Record<GhiseuState, { user: Line; agent: Line }>;

const TRANSCRIPT: Transcript = {
  idle: {
    user: null,
    agent: { text: "Bună! Spune-mi cu ce te pot ajuta astăzi.", final: true },
  },
  listening: {
    user: {
      text: "Vreau o adeverință de venit pentru bancă, pe ultimele 6 luni…",
      final: false,
    },
    agent: { text: "Sigur, te ajut cu adeverința de venit.", final: true },
  },
  thinking: {
    user: {
      text: "Vreau o adeverință de venit pentru bancă, pe ultimele 6 luni.",
      final: true,
    },
    agent: null,
  },
  speaking: {
    user: {
      text: "Vreau o adeverință de venit pentru bancă, pe ultimele 6 luni.",
      final: true,
    },
    agent: {
      text:
        "Bine. Am completat datele tale din ROeID. Verifică perioada și instituția destinatară…",
      final: true,
    },
  },
  review: {
    user: { text: "Da, e ok perioada.", final: true },
    agent: {
      text: "Am pregătit cererea. Te rog verifică datele înainte să o trimitem.",
      final: true,
    },
  },
  export: {
    user: { text: "Trimite-o pe email.", final: true },
    agent: { text: "Perfect. Pe ce email să o trimit — ana.popescu@…?", final: true },
  },
  done: {
    user: null,
    agent: {
      text: "Am trimis cererea către Direcția de Taxe. O să primești o copie pe email.",
      final: true,
    },
  },
  error: { user: null, agent: null },
  "mic-denied": { user: null, agent: null },
};

type Props = { state: GhiseuState };

export function CaptionStrip({ state }: Props) {
  const data = TRANSCRIPT[state];
  if (!data.user && !data.agent) return null;
  return (
    <div className="gh-caption" aria-live="polite">
      {data.user ? (
        <div className="gh-cap-line" data-role="user">
          <span className="gh-cap-tag">Tu</span>
          <span className="gh-cap-text">
            {data.user.final ? (
              data.user.text
            ) : (
              <span className="partial">{data.user.text}</span>
            )}
          </span>
        </div>
      ) : null}
      {data.agent ? (
        <div className="gh-cap-line" data-role="agent">
          <span className="gh-cap-tag">eGata</span>
          <span className="gh-cap-text">{data.agent.text}</span>
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/CaptionStrip.test.tsx
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ghiseu/CaptionStrip.tsx frontend/components/ghiseu/__tests__/CaptionStrip.test.tsx
git commit -m "feat(ghiseu): CaptionStrip Tu/eGata bubbles"
```

---

## Task 10: VoiceStage — status title + caption strip + error icon

**Files:**
- Create: `frontend/components/ghiseu/VoiceStage.tsx`
- Test: `frontend/components/ghiseu/__tests__/VoiceStage.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/components/ghiseu/__tests__/VoiceStage.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { VoiceStage } from "../VoiceStage";

describe("VoiceStage", () => {
  it("renders the idle title from the design copy", () => {
    render(<VoiceStage state="idle" />);
    expect(
      screen.getByRole("heading", {
        name: /Bună\. Apasă microfonul pentru ajutor\./i,
      }),
    ).toBeInTheDocument();
  });

  it("renders the listening title", () => {
    render(<VoiceStage state="listening" />);
    expect(screen.getByRole("heading", { name: /Te ascult/i })).toBeInTheDocument();
  });

  it("renders the error title and hint without a caption strip", () => {
    render(<VoiceStage state="error" />);
    expect(
      screen.getByRole("heading", { name: /S-a pierdut conexiunea/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Verificăm legătura/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Tu$/)).toBeNull();
  });

  it("renders the mic-denied title with a slash icon container", () => {
    const { container } = render(<VoiceStage state="mic-denied" />);
    expect(
      screen.getByRole("heading", { name: /Microfonul este blocat/i }),
    ).toBeInTheDocument();
    expect(container.querySelector(".gh-error-icon")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/VoiceStage.test.tsx
```

Expected: FAIL — module `../VoiceStage` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/components/ghiseu/VoiceStage.tsx`:

```tsx
"use client";

import type { GhiseuState } from "@/lib/ghiseuStore";
import { CaptionStrip } from "./CaptionStrip";
import { AlertIcon, MicSlashIcon } from "./icons";

const STATUS_COPY: Record<GhiseuState, { title: string; hint: string }> = {
  idle: { title: "Bună. Apasă microfonul pentru ajutor.", hint: "" },
  listening: {
    title: "Te ascult…",
    hint: "Vorbește natural. Te ascult până faci o pauză.",
  },
  thinking: {
    title: "Mă gândesc…",
    hint: "Verific datele tale și caut cererea potrivită.",
  },
  speaking: {
    title: "Vorbesc…",
    hint: "Apasă „Întrerupe” dacă vrei să spui altceva.",
  },
  review: {
    title: "E corect totul?",
    hint: "Aruncă o privire peste actul completat. Spune-mi sau apasă mai jos.",
  },
  export: {
    title: "Cum trimitem actul?",
    hint:
      "Alege o opțiune. Pot să-l trimit eu sau să-l înregistrez direct la primărie.",
  },
  done: {
    title: "Gata. Cererea a fost trimisă.",
    hint: "Vei primi confirmarea pe email. Mulțumesc!",
  },
  error: {
    title: "S-a pierdut conexiunea",
    hint: "Verificăm legătura cu serverul. Va dura câteva secunde.",
  },
  "mic-denied": {
    title: "Microfonul este blocat",
    hint:
      "Permite accesul la microfon în setările browserului ca să poți vorbi.",
  },
};

type Props = { state: GhiseuState };

export function VoiceStage({ state }: Props) {
  const copy = STATUS_COPY[state];
  const isError = state === "error" || state === "mic-denied";

  if (isError) {
    return (
      <div className="gh-stage">
        <div className="gh-status">
          <h2 className="gh-status-text">{copy.title}</h2>
          <p className="gh-status-hint">{copy.hint}</p>
        </div>
        <div className="gh-viz-wrap">
          <div className="gh-error-icon">
            {state === "mic-denied" ? (
              <MicSlashIcon size={44} />
            ) : (
              <AlertIcon size={44} />
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="gh-stage">
      <div className="gh-status">
        <h2 className="gh-status-text">{copy.title}</h2>
      </div>
      <CaptionStrip state={state} />
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/VoiceStage.test.tsx
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ghiseu/VoiceStage.tsx frontend/components/ghiseu/__tests__/VoiceStage.test.tsx
git commit -m "feat(ghiseu): VoiceStage with per-state status copy"
```

---

## Task 11: ControlsDock — mic + interrupt

**Files:**
- Create: `frontend/components/ghiseu/ControlsDock.tsx`
- Test: `frontend/components/ghiseu/__tests__/ControlsDock.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/components/ghiseu/__tests__/ControlsDock.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ControlsDock } from "../ControlsDock";

const noop = () => {};

describe("ControlsDock — idle / talk states", () => {
  it("shows 'Pornește microfonul' when muted", () => {
    render(
      <ControlsDock
        state="idle"
        muted={true}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Pornește microfonul/i }),
    ).toBeInTheDocument();
  });

  it("shows 'Oprește microfonul' when unmuted", () => {
    render(
      <ControlsDock
        state="listening"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Oprește microfonul/i }),
    ).toBeInTheDocument();
  });

  it("calls onToggleMute when mic is clicked", () => {
    const onToggleMute = vi.fn();
    render(
      <ControlsDock
        state="idle"
        muted={true}
        onToggleMute={onToggleMute}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pornește microfonul/i }));
    expect(onToggleMute).toHaveBeenCalledTimes(1);
  });

  it("disables Întrerupe outside of speaking", () => {
    render(
      <ControlsDock
        state="listening"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(screen.getByRole("button", { name: /Întrerupe/i })).toBeDisabled();
  });

  it("enables Întrerupe in speaking and fires onInterrupt", () => {
    const onInterrupt = vi.fn();
    render(
      <ControlsDock
        state="speaking"
        muted={false}
        onToggleMute={noop}
        onInterrupt={onInterrupt}
        onBackToTalk={noop}
      />,
    );
    const btn = screen.getByRole("button", { name: /Întrerupe/i });
    expect(btn).not.toBeDisabled();
    fireEvent.click(btn);
    expect(onInterrupt).toHaveBeenCalledTimes(1);
  });

  it("emits ripple data attribute only when listening + unmuted", () => {
    const { rerender, container } = render(
      <ControlsDock
        state="listening"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(container.querySelector('[data-emit="true"]')).toBeTruthy();
    rerender(
      <ControlsDock
        state="listening"
        muted={true}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(container.querySelector('[data-emit="true"]')).toBeNull();
  });
});

describe("ControlsDock — review / export ghost button", () => {
  it("renders 'Vorbește din nou' in review and fires onBackToTalk", () => {
    const onBackToTalk = vi.fn();
    render(
      <ControlsDock
        state="review"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={onBackToTalk}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Vorbește din nou/i }));
    expect(onBackToTalk).toHaveBeenCalledTimes(1);
  });

  it("renders 'Întreabă altceva' in export", () => {
    render(
      <ControlsDock
        state="export"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Întreabă altceva/i }),
    ).toBeInTheDocument();
  });

  it("renders nothing in done / error / mic-denied", () => {
    const { container, rerender } = render(
      <ControlsDock
        state="done"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(container.firstChild).toBeNull();
    rerender(
      <ControlsDock
        state="error"
        muted={false}
        onToggleMute={noop}
        onInterrupt={noop}
        onBackToTalk={noop}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/ControlsDock.test.tsx
```

Expected: FAIL — module `../ControlsDock` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/components/ghiseu/ControlsDock.tsx`:

```tsx
"use client";

import type { GhiseuState } from "@/lib/ghiseuStore";
import { MicIcon, MicOffIcon, StopIcon } from "./icons";

type Props = {
  state: GhiseuState;
  muted: boolean;
  onToggleMute: () => void;
  onInterrupt: () => void;
  onBackToTalk: () => void;
};

export function ControlsDock({
  state,
  muted,
  onToggleMute,
  onInterrupt,
  onBackToTalk,
}: Props) {
  if (state === "review") {
    return (
      <div className="gh-controls">
        <button
          type="button"
          className="gh-ctrl"
          data-variant="ghost"
          onClick={onBackToTalk}
        >
          <span className="gh-ctrl-icon">
            <MicIcon size={18} />
          </span>
          Vorbește din nou
        </button>
      </div>
    );
  }

  if (state === "export") {
    return (
      <div className="gh-controls">
        <button
          type="button"
          className="gh-ctrl"
          data-variant="ghost"
          onClick={onBackToTalk}
        >
          <span className="gh-ctrl-icon">
            <MicIcon size={18} />
          </span>
          Întreabă altceva
        </button>
      </div>
    );
  }

  if (state === "done" || state === "error" || state === "mic-denied") {
    return null;
  }

  const emitting = state === "listening" && !muted;
  const canInterrupt = state === "speaking";

  return (
    <div className="gh-controls">
      <button
        type="button"
        className="gh-ctrl"
        data-variant="mic"
        data-on={!muted ? "true" : "false"}
        data-emit={emitting ? "true" : "false"}
        onClick={onToggleMute}
        aria-pressed={!muted}
        title={muted ? "Pornește microfonul" : "Oprește microfonul"}
      >
        <span className="gh-ctrl-icon">
          {muted ? <MicOffIcon size={20} /> : <MicIcon size={20} />}
        </span>
        {muted ? "Pornește microfonul" : "Oprește microfonul"}
      </button>

      <button
        type="button"
        className="gh-ctrl"
        data-variant="end"
        onClick={onInterrupt}
        disabled={!canInterrupt}
        title="Întrerupe agentul"
      >
        <span className="gh-ctrl-icon">
          <StopIcon size={16} />
        </span>
        Întrerupe
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/ControlsDock.test.tsx
```

Expected: PASS, 9 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ghiseu/ControlsDock.tsx frontend/components/ghiseu/__tests__/ControlsDock.test.tsx
git commit -m "feat(ghiseu): ControlsDock with mic + interrupt + ghost variants"
```

---

## Task 12: DocumentReview — doc-paper with confirm/amend

**Files:**
- Create: `frontend/components/ghiseu/DocumentReview.tsx`
- Test: `frontend/components/ghiseu/__tests__/DocumentReview.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/components/ghiseu/__tests__/DocumentReview.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DocumentReview } from "../DocumentReview";

describe("DocumentReview", () => {
  it("renders the review header and the auto-fill fields", () => {
    render(<DocumentReview onConfirm={() => {}} onAmend={() => {}} />);
    expect(
      screen.getByRole("heading", { name: /Iată cererea ta\. E corect totul\?/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Popescu Ana-Maria")).toBeInTheDocument();
    expect(screen.getByText("2940413081265")).toBeInTheDocument();
    expect(screen.getByText("Banca Transilvania — Cluj Centru")).toBeInTheDocument();
  });

  it("calls onConfirm when 'Da, e corect' clicked", () => {
    const onConfirm = vi.fn();
    render(<DocumentReview onConfirm={onConfirm} onAmend={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Da, e corect/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onAmend when 'Mai am o corectură' clicked", () => {
    const onAmend = vi.fn();
    render(<DocumentReview onConfirm={() => {}} onAmend={onAmend} />);
    fireEvent.click(screen.getByRole("button", { name: /Mai am o corectură/i }));
    expect(onAmend).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/DocumentReview.test.tsx
```

Expected: FAIL — module `../DocumentReview` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/components/ghiseu/DocumentReview.tsx`:

```tsx
"use client";

import { CheckIcon, EditIcon } from "./icons";

type Field = { label: string; value: string; auto: boolean };

const FIELDS: Field[] = [
  { label: "Nume și prenume", value: "Popescu Ana-Maria", auto: true },
  { label: "CNP", value: "2940413081265", auto: true },
  {
    label: "Adresa",
    value: "Str. Memorandumului 28, ap. 14, Cluj-Napoca",
    auto: true,
  },
  { label: "Email confirmare", value: "ana.popescu@gmail.com", auto: true },
  { label: "Perioada", value: "Nov 2025 — Apr 2026 (6 luni)", auto: false },
  {
    label: "Instituție destinatară",
    value: "Banca Transilvania — Cluj Centru",
    auto: false,
  },
  { label: "Motiv", value: "Credit ipotecar", auto: false },
  { label: "Limba", value: "Română", auto: false },
];

type Props = {
  onConfirm: () => void;
  onAmend: () => void;
};

export function DocumentReview({ onConfirm, onAmend }: Props) {
  return (
    <div className="gh-review">
      <div className="gh-review-head">
        <h2 className="gh-review-title">Iată cererea ta. E corect totul?</h2>
      </div>

      <div className="doc-paper">
        <div className="doc-header">
          <div className="doc-stamp">
            <div>PRIMĂRIA</div>
            <div>CLUJ-NAPOCA</div>
          </div>
          <div className="doc-paper-titleblock">
            <div className="doc-title">Adeverință de venit</div>
            <div className="doc-paper-sub">
              Cerere către Direcția de Taxe și Impozite
            </div>
          </div>
          <div className="doc-paper-meta">
            <div>
              Cerere nr. <strong>2026-AV-08412</strong>
            </div>
            <div>Data: 24.05.2026</div>
          </div>
        </div>

        <div className="doc-fields-grid">
          {FIELDS.map((f) => (
            <div className="dfg-row" key={f.label}>
              <div className="dfg-label">{f.label}</div>
              <div className="dfg-value">
                <span className="dfg-text">{f.value}</span>
                {f.auto ? <span className="doc-auto">✓ auto</span> : null}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="gh-review-actions">
        <button
          type="button"
          className="gh-review-action"
          data-kind="confirm"
          onClick={onConfirm}
        >
          <span className="ra-icon">
            <CheckIcon size={22} />
          </span>
          <span className="ra-body">
            <span>Da, e corect</span>
            <span className="ra-hint">Continuă spre trimitere</span>
          </span>
        </button>
        <button
          type="button"
          className="gh-review-action"
          data-kind="amend"
          onClick={onAmend}
        >
          <span className="ra-icon">
            <EditIcon size={20} />
          </span>
          <span className="ra-body">
            <span>Mai am o corectură</span>
            <span className="ra-hint">Spune-mi ce să schimb</span>
          </span>
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/DocumentReview.test.tsx
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ghiseu/DocumentReview.tsx frontend/components/ghiseu/__tests__/DocumentReview.test.tsx
git commit -m "feat(ghiseu): DocumentReview with doc-paper + confirm/amend"
```

---

## Task 13: ExportOptions — primărie / email cards

**Files:**
- Create: `frontend/components/ghiseu/ExportOptions.tsx`
- Test: `frontend/components/ghiseu/__tests__/ExportOptions.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/components/ghiseu/__tests__/ExportOptions.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ExportOptions } from "../ExportOptions";

describe("ExportOptions", () => {
  it("renders the header and both cards", () => {
    render(<ExportOptions onPick={() => {}} />);
    expect(
      screen.getByRole("heading", { name: /Cum trimitem actul\?/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Trimite la primărie/i)).toBeInTheDocument();
    expect(screen.getByText(/Trimite pe email/i)).toBeInTheDocument();
  });

  it("marks the primărie card as recommended", () => {
    const { container } = render(<ExportOptions onPick={() => {}} />);
    expect(
      container.querySelector('[data-recommended="true"]'),
    ).toBeTruthy();
  });

  it("fires onPick('city') when 'Trimite la primărie' is clicked", () => {
    const onPick = vi.fn();
    render(<ExportOptions onPick={onPick} />);
    fireEvent.click(screen.getByText(/Trimite la primărie/i).closest("button")!);
    expect(onPick).toHaveBeenCalledWith("city");
  });

  it("fires onPick('email') when 'Trimite pe email' is clicked", () => {
    const onPick = vi.fn();
    render(<ExportOptions onPick={onPick} />);
    fireEvent.click(screen.getByText(/Trimite pe email/i).closest("button")!);
    expect(onPick).toHaveBeenCalledWith("email");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/ExportOptions.test.tsx
```

Expected: FAIL — module `../ExportOptions` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/components/ghiseu/ExportOptions.tsx`:

```tsx
"use client";

import type { ExportMethod } from "@/lib/ghiseuStore";
import { CityIcon, MailIcon } from "./icons";

type Pick = Exclude<ExportMethod, null>;

type Option = {
  id: Pick;
  title: string;
  hint: string;
  icon: React.ReactNode;
  recommended?: boolean;
};

const OPTIONS: Option[] = [
  {
    id: "city",
    title: "Trimite la primărie",
    hint: "Cererea intră în lucru imediat.",
    icon: <CityIcon size={36} />,
    recommended: true,
  },
  {
    id: "email",
    title: "Trimite pe email",
    hint: "Pe ana.popescu@gmail.com.",
    icon: <MailIcon size={36} />,
  },
];

type Props = { onPick: (id: Pick) => void };

export function ExportOptions({ onPick }: Props) {
  return (
    <div className="gh-export">
      <div className="gh-review-head">
        <h2 className="gh-status-text">Cum trimitem actul?</h2>
      </div>
      <div className="gh-export-grid">
        {OPTIONS.map((o) => (
          <button
            key={o.id}
            type="button"
            className="gh-export-card"
            data-recommended={o.recommended ? "true" : "false"}
            onClick={() => onPick(o.id)}
          >
            <div className="ec-icon">{o.icon}</div>
            <div>
              <h3 className="ec-title">{o.title}</h3>
              <p className="ec-hint">{o.hint}</p>
            </div>
            <div className="ec-bottom">
              <span className="ec-go" aria-hidden="true">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M5 12h14" />
                  <path d="M13 5l7 7-7 7" />
                </svg>
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/ExportOptions.test.tsx
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ghiseu/ExportOptions.tsx frontend/components/ghiseu/__tests__/ExportOptions.test.tsx
git commit -m "feat(ghiseu): ExportOptions cards (primărie + email)"
```

---

## Task 14: DoneScreen — checkmark + ref number

**Files:**
- Create: `frontend/components/ghiseu/DoneScreen.tsx`
- Test: `frontend/components/ghiseu/__tests__/DoneScreen.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/components/ghiseu/__tests__/DoneScreen.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DoneScreen } from "../DoneScreen";

describe("DoneScreen", () => {
  it("renders the city-method headline", () => {
    render(<DoneScreen method="city" />);
    expect(
      screen.getByRole("heading", {
        name: /Cererea a fost trimis direct la primărie/i,
      }),
    ).toBeInTheDocument();
  });

  it("renders the email-method headline", () => {
    render(<DoneScreen method="email" />);
    expect(
      screen.getByRole("heading", { name: /trimis pe email/i }),
    ).toBeInTheDocument();
  });

  it("renders the registration number", () => {
    render(<DoneScreen method="city" />);
    expect(screen.getByText(/REG-2026-08412/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/DoneScreen.test.tsx
```

Expected: FAIL — module `../DoneScreen` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/components/ghiseu/DoneScreen.tsx`:

```tsx
"use client";

import type { ExportMethod } from "@/lib/ghiseuStore";
import { CheckIcon, MicIcon } from "./icons";

type Props = { method: Exclude<ExportMethod, null> };

const METHOD_LABEL: Record<Exclude<ExportMethod, null>, string> = {
  city: "trimis direct la primărie",
  email: "trimis pe email",
};

const REF_NO = "REG-2026-08412";

export function DoneScreen({ method }: Props) {
  const methodLabel = METHOD_LABEL[method];
  return (
    <div className="gh-stage">
      <div className="gh-done-check" aria-hidden="true">
        <CheckIcon size={64} />
      </div>
      <div className="gh-status">
        <h2 className="gh-status-text">
          Gata. Cererea a fost {methodLabel}.
        </h2>
        <p className="gh-status-hint">
          Număr de înregistrare:{" "}
          <strong
            style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.04em" }}
          >
            {REF_NO}
          </strong>{" "}
          · Vei primi confirmarea pe email.
        </p>
      </div>
      <button type="button" className="gh-cta">
        <MicIcon size={18} />
        Începe o nouă conversație
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/DoneScreen.test.tsx
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ghiseu/DoneScreen.tsx frontend/components/ghiseu/__tests__/DoneScreen.test.tsx
git commit -m "feat(ghiseu): DoneScreen with ref number"
```

---

## Task 15: GhiseuProfileMenu — accessibility dropdown

**Files:**
- Create: `frontend/components/ghiseu/GhiseuProfileMenu.tsx`
- Test: `frontend/components/ghiseu/__tests__/GhiseuProfileMenu.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/components/ghiseu/__tests__/GhiseuProfileMenu.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GhiseuProfileMenu } from "../GhiseuProfileMenu";
import { useAccessibilityPrefs } from "@/lib/accessibilityStore";

beforeEach(() => {
  localStorage.clear();
  useAccessibilityPrefs.setState({
    voiceOnly: false,
    simpleLanguage: false,
    largeText: false,
    highContrast: false,
    dyslexic: false,
    hydrated: true,
  });
});

describe("GhiseuProfileMenu", () => {
  it("opens the dropdown when the chip is clicked", () => {
    render(<GhiseuProfileMenu />);
    expect(screen.queryByText(/Mod contrast ridicat/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Accesibilitate/i }));
    expect(screen.getByText(/Mod contrast ridicat/i)).toBeInTheDocument();
  });

  it("toggles the highContrast preference in the shared store", () => {
    render(<GhiseuProfileMenu />);
    fireEvent.click(screen.getByRole("button", { name: /Accesibilitate/i }));
    const toggle = screen.getByRole("switch", { name: /Mod contrast ridicat/i });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(useAccessibilityPrefs.getState().highContrast).toBe(true);
  });

  it("reflects an externally set preference (large text)", () => {
    useAccessibilityPrefs.setState({ largeText: true });
    render(<GhiseuProfileMenu />);
    fireEvent.click(screen.getByRole("button", { name: /Accesibilitate/i }));
    expect(
      screen.getByRole("switch", { name: /Mod text mare/i }),
    ).toHaveAttribute("aria-checked", "true");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/GhiseuProfileMenu.test.tsx
```

Expected: FAIL — module `../GhiseuProfileMenu` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/components/ghiseu/GhiseuProfileMenu.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useAccessibilityPrefs } from "@/lib/accessibilityStore";

type ToggleProps = {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (next: boolean) => void;
};

function AccessibilityToggle({ label, hint, checked, onChange }: ToggleProps) {
  return (
    <label className="gh-pm-row">
      <span className="gh-pm-row-text">
        <span className="gh-pm-row-label">{label}</span>
        <span className="gh-pm-row-hint">{hint}</span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={(e) => {
          e.preventDefault();
          onChange(!checked);
        }}
        className={"gh-pm-switch " + (checked ? "is-on" : "")}
      >
        <span className="gh-pm-switch-knob" aria-hidden="true" />
      </button>
    </label>
  );
}

export function GhiseuProfileMenu() {
  const [open, setOpen] = useState(false);
  const largeText = useAccessibilityPrefs((s) => s.largeText);
  const highContrast = useAccessibilityPrefs((s) => s.highContrast);
  const dyslexic = useAccessibilityPrefs((s) => s.dyslexic);
  const setPrefs = useAccessibilityPrefs((s) => s.set);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const btnRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      const target = e.target as Node;
      if (menuRef.current?.contains(target)) return;
      if (btnRef.current?.contains(target)) return;
      setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="gh-pm">
      <button
        ref={btnRef}
        type="button"
        className="gh-pm-chip"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="gh-pm-avatar" aria-hidden="true">
          A
        </span>
        <span className="gh-pm-chip-label">Accesibilitate</span>
        <svg
          className="gh-pm-caret"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open ? (
        <div ref={menuRef} role="menu" className="gh-pm-panel">
          <p className="gh-pm-eyebrow">Accesibilitate</p>
          <div className="gh-pm-list">
            <AccessibilityToggle
              label="Mod contrast ridicat"
              hint="Text negru, fundal alb, contururi groase."
              checked={highContrast}
              onChange={(v) => setPrefs({ highContrast: v })}
            />
            <AccessibilityToggle
              label="Mod text mare"
              hint="Mărește textul corpului paginii."
              checked={largeText}
              onChange={(v) => setPrefs({ largeText: v })}
            />
            <AccessibilityToggle
              label="Mod dislexic"
              hint="Spațiere mai mare între litere și rânduri."
              checked={dyslexic}
              onChange={(v) => setPrefs({ dyslexic: v })}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test -- components/ghiseu/__tests__/GhiseuProfileMenu.test.tsx
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ghiseu/GhiseuProfileMenu.tsx frontend/components/ghiseu/__tests__/GhiseuProfileMenu.test.tsx
git commit -m "feat(ghiseu): GhiseuProfileMenu accessibility dropdown"
```

---

## Task 16: GhiseuShell — top bar + main + controls + bg

**Files:**
- Create: `frontend/components/ghiseu/GhiseuShell.tsx`

No unit test for the shell — the smoke test is in Task 17's auth-gate test (rendering `/ghiseu` triggers the shell) plus the manual pass in Task 18.

- [ ] **Step 1: Write the shell**

Create `frontend/components/ghiseu/GhiseuShell.tsx`:

```tsx
"use client";

import { useAccessibilityClasses } from "@/lib/accessibilityStore";
import { useGhiseuStore } from "@/lib/ghiseuStore";
import { AnimatedMesh } from "./AnimatedMesh";
import { ControlsDock } from "./ControlsDock";
import { DocumentReview } from "./DocumentReview";
import { DoneScreen } from "./DoneScreen";
import { ExportOptions } from "./ExportOptions";
import { GhiseuProfileMenu } from "./GhiseuProfileMenu";
import { LogoIcon, RefreshIcon } from "./icons";
import { VoiceStage } from "./VoiceStage";

export function GhiseuShell() {
  useAccessibilityClasses();

  const state = useGhiseuStore((s) => s.state);
  const muted = useGhiseuStore((s) => s.muted);
  const exportMethod = useGhiseuStore((s) => s.exportMethod);
  const toggleMute = useGhiseuStore((s) => s.toggleMute);
  const interrupt = useGhiseuStore((s) => s.interrupt);
  const confirmDoc = useGhiseuStore((s) => s.confirmDoc);
  const amendDoc = useGhiseuStore((s) => s.amendDoc);
  const pickExport = useGhiseuStore((s) => s.pickExport);
  const backToTalk = useGhiseuStore((s) => s.backToTalk);
  const reset = useGhiseuStore((s) => s.reset);

  let content;
  if (state === "review") {
    content = <DocumentReview onConfirm={confirmDoc} onAmend={amendDoc} />;
  } else if (state === "export") {
    content = <ExportOptions onPick={pickExport} />;
  } else if (state === "done") {
    content = <DoneScreen method={exportMethod ?? "city"} />;
  } else {
    content = <VoiceStage state={state} />;
  }

  return (
    <div className="gh-root" data-bg="light">
      <AnimatedMesh />

      <div className="gh-shell">
        <header className="gh-top">
          <div className="brand">
            <div className="brand-mark">
              <LogoIcon />
            </div>
            <span className="brand-name">eGata</span>
          </div>

          <div className="gh-top-actions">
            <button
              type="button"
              className="gh-reset-btn"
              onClick={reset}
              disabled={state === "idle"}
              aria-label="Ia-o de la capăt"
              title="Ia-o de la capăt"
            >
              <span className="gh-reset-btn-icon" aria-hidden="true">
                <RefreshIcon size={15} />
              </span>
              <span>Ia-o de la capăt</span>
            </button>
            <GhiseuProfileMenu />
          </div>
        </header>

        <main className="gh-main">{content}</main>

        <ControlsDock
          state={state}
          muted={muted}
          onToggleMute={toggleMute}
          onInterrupt={interrupt}
          onBackToTalk={backToTalk}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ghiseu/GhiseuShell.tsx
git commit -m "feat(ghiseu): GhiseuShell composes mesh + top + main + dock"
```

---

## Task 17: /ghiseu route entry with auth gate

**Files:**
- Create: `frontend/app/ghiseu/page.tsx`

- [ ] **Step 1: Write the route entry**

Create `frontend/app/ghiseu/page.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { GhiseuShell } from "@/components/ghiseu/GhiseuShell";
import { getSession } from "@/lib/session";
import "./ghiseu.css";

export default function GhiseuPage() {
  const router = useRouter();

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!getSession()) router.replace("/login");
  }, [router]);

  return <GhiseuShell />;
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/ghiseu/page.tsx
git commit -m "feat(ghiseu): /ghiseu route with auth gate"
```

---

## Task 18: Full-suite verification + manual walkthrough

**Files:**
- (none — this is verification)

- [ ] **Step 1: Run the full test suite**

```bash
cd frontend && npm test
```

Expected: ALL tests pass — every pre-existing test plus the ~31 new tests added by Tasks 1–15. If any pre-existing test now fails, fix the cause before continuing.

- [ ] **Step 2: Typecheck the whole project**

```bash
cd frontend && npm run typecheck
```

Expected: PASS, no TypeScript errors anywhere.

- [ ] **Step 3: Start the dev server and walk the full flow manually**

```bash
cd frontend && npm run dev
```

In a browser, in this exact order:
1. Visit `http://localhost:3000/login` — verify the **Modul Ghișeu** toggle is visible above the login button on both the regular form and the kiosk variant (resize to a wide viewport or append `?mode=kiosk` to the URL).
2. With the toggle OFF, complete the login + OTP flow with a seeded user → confirm you land on `/` (the regular chat surface).
3. Sign out, return to `/login`, turn the **Modul Ghișeu** toggle ON, complete login + OTP → confirm you land on `/ghiseu`.
4. On `/ghiseu` idle: verify the title reads **"Bună. Apasă microfonul pentru ajutor."**, the animated mesh is visible, the **Ia-o de la capăt** button is disabled, the **Accesibilitate** chip is in the top-right.
5. Click **Pornește microfonul** — state advances `listening` (2.8s) → `thinking` (1.5s) → `speaking` (3.1s) → `review`. Confirm the captions appear in each state.
6. While in `listening`, verify the mic button shows the green ripple (two concentric `gh-light` rings expanding).
7. In `speaking`, click **Întrerupe** — state returns to `listening` with mic on.
8. From `review`, click **Da, e corect** — state goes to `export`. Both export cards render; the primărie card has the green-tinted recommended border.
9. Click **Trimite la primărie** — state goes to `done`. Verify the headline reads **"Cererea a fost trimis direct la primărie."** and the ref number `REG-2026-08412` is visible.
10. Click **Ia-o de la capăt** — state returns to idle, the mic re-mutes.
11. Open **Accesibilitate**, toggle **Mod contrast ridicat** — page repaints in high-contrast (black text, white bg, hidden mesh). Toggle **Mod text mare** — copy enlarges. Toggle **Mod dislexic** — letter and word spacing grows.
12. Sign out, log back in WITHOUT the toggle — confirm that the accessibility prefs from step 11 still apply on the main app (they share `useAccessibilityPrefs`).

Stop the dev server when done.

- [ ] **Step 4: Lint**

```bash
cd frontend && npm run lint
```

Expected: no warnings or errors in the new files. Fix anything reported.

- [ ] **Step 5: Final integration commit (only if any fixes were needed in step 1, 2, or 4)**

If steps 1–4 all passed without changes, skip this commit. Otherwise:

```bash
git add -A
git commit -m "chore(ghiseu): final integration fixes"
```

- [ ] **Step 6: Push the branch**

```bash
git push -u origin feat/modul-ghiseu
```

---

## Self-Review

Done as I wrote it; the plan covers every spec section:

- **Modul Ghișeu toggle on /login** — Tasks 3, 4
- **OTP redirect** — Task 5
- **`/ghiseu` route + auth gate** — Task 17
- **All 9 states rendered correctly** — Tasks 10 (VoiceStage), 12 (DocumentReview), 13 (ExportOptions), 14 (DoneScreen), composed in Task 16
- **Scripted state machine + bridge stub** — Task 2
- **CSS port** — Task 6
- **Animated mesh** — Task 8
- **Mic ripple via `data-emit`** — handled in Task 11 (`<button data-emit="true">`); CSS rule already in `ghiseu.css` from Task 6
- **Accessibility menu sharing `useAccessibilityPrefs`** — Task 15
- **Reset pill** — Task 16 (inline in `GhiseuShell`)
- **Romanian copy verbatim** — Tasks 9, 10, 11, 12, 13, 14, 15
- **No regressions on ChatSurface / TopBar / Composer / sessionStore / VoiceProvider** — verified by the full-suite run in Task 18, step 1
- **Manual walkthrough of all states + accessibility** — Task 18, step 3

No placeholders. Type names consistent (`GhiseuState`, `ExportMethod` used identically across `ghiseuStore.ts`, `CaptionStrip`, `VoiceStage`, `ControlsDock`, `DocumentReview`, `ExportOptions`, `DoneScreen`, `GhiseuShell`). Method signatures match across tasks (`toggleMute()`, `interrupt()`, `confirmDoc()`, `amendDoc()`, `pickExport(method)`, `backToTalk()`, `reset()` — defined in Task 2, used in Task 16; the props of every leaf component match how `GhiseuShell` calls them).
