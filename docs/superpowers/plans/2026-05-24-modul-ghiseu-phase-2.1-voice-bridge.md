# Modul Ghișeu Phase 2.1 — Voice Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the scripted `setTimeout` flow in `frontend/lib/ghiseuStore.ts` with real wiring into `useVoiceAgentBridge` so that on `/ghiseu` the user actually talks to the AI, with live transcripts in the `Tu` / `eGata` bubbles and a working `Întrerupe` button.

**Architecture:** Store-driven. `useVoiceAgentBridge` (single-source-of-truth WS hook) is unchanged except for a new `interrupt()` method. `ghiseuStore` manages a parallel UI state machine that maps voice events into kiosk-shaped transitions via callbacks passed to `bridge.start({...})`. `sessionStore` gains a `kioskMode` flag so the existing agent navigation side-effects no-op while the kiosk is mounted.

**Tech Stack:** TypeScript, Zustand, React, Vitest, @testing-library/react. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-24-modul-ghiseu-phase-2.1-voice-bridge-design.md`

---

## File map

| File | Action |
|---|---|
| `frontend/lib/useVoiceAgentBridge.ts` | Modify — add `interrupt(): void` to `VoiceAgentHook` and implementation |
| `frontend/lib/__tests__/useVoiceAgentBridge.test.ts` | Create — focused test for `interrupt()` only |
| `frontend/lib/sessionStore.ts` | Modify — add `kioskMode` + `setKioskMode` + guard in `pushPath` |
| `frontend/lib/__tests__/sessionStore.test.ts` | Modify — add kioskMode test cases |
| `frontend/lib/__tests__/__helpers__/mockVoiceAgentHook.ts` | Create — typed mock of `VoiceAgentHook` for store tests |
| `frontend/lib/ghiseuStore.ts` | Rewrite — drop scripted flow; add caption, event handlers, bridge lifecycle actions |
| `frontend/lib/__tests__/ghiseuStore.test.ts` | Rewrite — drop scripted-flow tests; add event-driven tests |
| `frontend/lib/__tests__/ghiseuStore.bridge.test.ts` | Create — integration test with `MockVoiceAgentHook` |
| `frontend/components/ghiseu/CaptionStrip.tsx` | Modify — read `caption` from `useGhiseuStore`; fall back to TRANSCRIPT[state] |
| `frontend/components/ghiseu/__tests__/CaptionStrip.test.tsx` | Modify — add tests for live caption + fallback |
| `frontend/components/ghiseu/GhiseuShell.tsx` | Modify — consume `useVoiceContext`; add attach, enter-voice, kioskMode, mirror-muted effects |
| `frontend/components/ghiseu/__tests__/GhiseuShell.test.tsx` | Create — mount with mocked voice context; assert lifecycle effects |
| `frontend/components/ghiseu/ControlsDock.tsx` | Unchanged — existing props design works once state/muted reflect voice state |

---

## Task 1: Add `interrupt()` method to `VoiceAgentHook`

**Why first:** smallest, fully independent change; everything else can reference the new method.

**Files:**
- Modify: `frontend/lib/useVoiceAgentBridge.ts`
- Create: `frontend/lib/__tests__/useVoiceAgentBridge.test.ts`

- [ ] **Step 1.1: Write the failing test**

Create `frontend/lib/__tests__/useVoiceAgentBridge.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useVoiceAgentBridge } from "../useVoiceAgentBridge";

// VoiceWs is constructed inside start(); we replace it with a mock so we can
// assert sendInterrupt() is called without booting the real WS.
const sendInterruptSpy = vi.fn();
const closeSpy = vi.fn();

vi.mock("../voiceWs", () => ({
  voiceWsUrl: () => "ws://test",
  VoiceWs: vi.fn().mockImplementation(() => ({
    connect: vi.fn().mockResolvedValue(undefined),
    sendStart: vi.fn(),
    sendInterrupt: sendInterruptSpy,
    close: closeSpy,
    sendText: vi.fn(),
    sendAudio: vi.fn(),
    sendWidgetSubmission: vi.fn(),
  })),
}));

// Auth: start() reads session via getSession(); make it succeed.
vi.mock("../session", () => ({
  getSession: () => ({ access_token: "test-token" }),
}));

// Audio worklet: start() boots a player; stub to a no-op handle.
vi.mock("../audioWorklet", () => ({
  prewarmMicPermission: vi.fn().mockResolvedValue(undefined),
  startPlayer: vi.fn().mockResolvedValue({
    feed: vi.fn(),
    flush: vi.fn(),
    stop: vi.fn(),
  }),
  startMicRecorder: vi.fn(),
}));

beforeEach(() => {
  sendInterruptSpy.mockClear();
  closeSpy.mockClear();
});

describe("useVoiceAgentBridge.interrupt", () => {
  it("throws when called before start (WS not open)", () => {
    const { result } = renderHook(() => useVoiceAgentBridge());
    expect(() => result.current.interrupt()).toThrow(/not started/i);
    expect(sendInterruptSpy).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 1.2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run lib/__tests__/useVoiceAgentBridge.test.ts`

Expected: FAIL with "result.current.interrupt is not a function" (the method doesn't exist yet).

- [ ] **Step 1.3: Add `interrupt` to the `VoiceAgentHook` type**

Modify `frontend/lib/useVoiceAgentBridge.ts`. Find the `VoiceAgentHook` type (around line 49-74). Add after `disableMic`:

```ts
  /** Send an interrupt frame to cut off the agent's current audio response.
   * Backend will emit an `interrupted` event back, which the existing
   * onInterrupted handler turns into state=listening + player flush. */
  interrupt: () => void;
```

- [ ] **Step 1.4: Add the `interrupt` implementation in the hook body**

In the same file, find the block where other methods are defined as `useCallback`. Add after `disableMic` (around line 360):

```ts
  const interrupt: VoiceAgentHook["interrupt"] = useCallback(() => {
    if (!wsRef.current) {
      throw new Error("Voice bridge not started; call start() first.");
    }
    wsRef.current.sendInterrupt();
  }, []);
```

- [ ] **Step 1.5: Add `interrupt` to the returned object**

In the same file, find the `return { ... }` at the bottom of the hook (around line 382-393). Add `interrupt`:

```ts
  return {
    state,
    wsReady,
    micOn,
    start,
    stop,
    enableMic,
    disableMic,
    interrupt,
    sendText,
    submitWidget,
    registerToolHandler,
  };
```

- [ ] **Step 1.6: Run the test to verify it passes**

Run: `cd frontend && npx vitest run lib/__tests__/useVoiceAgentBridge.test.ts`

Expected: PASS — 1 test passing.

- [ ] **Step 1.7: Commit**

```bash
git add frontend/lib/useVoiceAgentBridge.ts frontend/lib/__tests__/useVoiceAgentBridge.test.ts
git commit -m "feat(voice): add interrupt() method to VoiceAgentHook

Exposes the existing voiceWs.sendInterrupt() through the hook surface
so kiosk + chat surfaces can cut off agent audio mid-response. Throws
when called before start() (no WS open)."
```

---

## Task 2: Add `kioskMode` flag to `sessionStore`

**Why second:** independent of voice work; small surface; needed before GhiseuShell can mount safely.

**Files:**
- Modify: `frontend/lib/sessionStore.ts`
- Modify: `frontend/lib/__tests__/sessionStore.test.ts`

- [ ] **Step 2.1: Write the failing tests**

Add to the bottom of `frontend/lib/__tests__/sessionStore.test.ts` (after the existing describe blocks, before EOF):

```ts
describe("sessionStore kioskMode", () => {
  it("defaults to false", () => {
    expect(useSessionStore.getState().kioskMode).toBe(false);
  });

  it("setKioskMode toggles the flag", () => {
    useSessionStore.getState().setKioskMode(true);
    expect(useSessionStore.getState().kioskMode).toBe(true);
    useSessionStore.getState().setKioskMode(false);
    expect(useSessionStore.getState().kioskMode).toBe(false);
  });
});
```

Also extend the existing `beforeEach` reset block (top of file) to include `kioskMode: false`:

```ts
beforeEach(() => {
  useSessionStore.setState({
    citizen: null,
    activeDocId: null,
    document: null,
    procedure: null,
    conversationId: null,
    messages: [],
    voiceStatus: "idle",
    drawerOpen: false,
    profileMenuOpen: false,
    sending: false,
    session: null,
    scenarioPlan: null,
    lookupMatches: [],
    kioskMode: false,
  });
  localStorage.clear();
});
```

- [ ] **Step 2.2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run lib/__tests__/sessionStore.test.ts -t "kioskMode"`

Expected: FAIL — `kioskMode` is not on the state and `setKioskMode` is not a function.

- [ ] **Step 2.3: Add `kioskMode` to the `SessionState` interface**

In `frontend/lib/sessionStore.ts`, find the `export interface SessionState` block (starts around line 80). Add a field near `voiceStatus` / `micOn`:

```ts
  /** True while the kiosk surface (/ghiseu) is mounted. Causes pushPath() to
   * short-circuit so agent-triggered navigation does not pull the user off
   * the kiosk. Cleared on unmount. */
  kioskMode: boolean;
```

And add the setter to the actions section (next to `setVoiceStatus`):

```ts
  setKioskMode(on: boolean): void;
```

- [ ] **Step 2.4: Initialize the field and implement the setter**

Find the `create<SessionState>((set, get) => ({` block. Add `kioskMode: false,` to the initial state alongside other booleans (near `drawerOpen: false,` / `sending: false,`).

Find where `setVoiceStatus` is implemented and add next to it:

```ts
  setKioskMode(on) {
    set({ kioskMode: on });
  },
```

- [ ] **Step 2.5: Add the guard in `pushPath`**

Find the `pushPath` function (around line 75). Modify it:

```ts
function pushPath(path: string) {
  if (typeof window !== "undefined" && window.location.pathname === path) return;
  // Kiosk mode suppresses store-driven navigation so /ghiseu stays put even
  // when the agent fires start_procedure / redirect events.
  if (useSessionStore.getState().kioskMode) return;
  _navigate(path);
}
```

- [ ] **Step 2.6: Run the new tests to verify pass**

Run: `cd frontend && npx vitest run lib/__tests__/sessionStore.test.ts -t "kioskMode"`

Expected: PASS — 2 tests passing.

- [ ] **Step 2.7: Run the full sessionStore test file (regression check)**

Run: `cd frontend && npx vitest run lib/__tests__/sessionStore.test.ts`

Expected: All existing sessionStore tests still pass.

- [ ] **Step 2.8: Add a test that the guard actually short-circuits pushPath**

Add to the kioskMode describe block in `frontend/lib/__tests__/sessionStore.test.ts`. The existing `reset()` action (line 633 of sessionStore.ts) ends with `pushPath("/")`, so it's the trigger:

```ts
  it("pushPath no-ops when kioskMode is true", async () => {
    const { setNavigate } = await import("../sessionStore");
    const navSpy = vi.fn();
    const originalNavigate = (path: string) => {
      if (typeof window !== "undefined" && window.location.pathname !== path) {
        window.history.pushState(null, "", path);
      }
    };
    setNavigate(navSpy);

    try {
      useSessionStore.setState({ kioskMode: true });
      useSessionStore.getState().reset();
      expect(navSpy).not.toHaveBeenCalled();

      useSessionStore.setState({ kioskMode: false });
      useSessionStore.getState().reset();
      expect(navSpy).toHaveBeenCalledWith("/");
    } finally {
      setNavigate(originalNavigate);
    }
  });
```

Also add `import { vi } from "vitest";` to the top of the file if it isn't there already.

- [ ] **Step 2.9: Run the new pushPath-guard test**

Run: `cd frontend && npx vitest run lib/__tests__/sessionStore.test.ts -t "no-ops"`

Expected: PASS.

- [ ] **Step 2.10: Commit**

```bash
git add frontend/lib/sessionStore.ts frontend/lib/__tests__/sessionStore.test.ts
git commit -m "feat(session): add kioskMode flag that suppresses pushPath

When /ghiseu is mounted, setKioskMode(true) prevents the agent's
start_procedure / redirect side-effects from navigating the user
off the kiosk. Cleared on unmount."
```

---

## Task 3: Create `MockVoiceAgentHook` test helper

**Why now:** the next two tasks (ghiseuStore rewrite + bridge integration test) both need a typed mock.

**Files:**
- Create: `frontend/lib/__tests__/__helpers__/mockVoiceAgentHook.ts`

- [ ] **Step 3.1: Create the helper file**

Create `frontend/lib/__tests__/__helpers__/mockVoiceAgentHook.ts`:

```ts
import { vi } from "vitest";
import type {
  VoiceAgentHook,
  VoiceAgentState,
  VoiceAgentStartOpts,
} from "../../useVoiceAgentBridge";

/** Captured callbacks from the most recent start() call. Set after start()
 * is invoked; the test can fire events through these to simulate the bridge. */
export type MockVoiceAgentHandle = {
  hook: VoiceAgentHook;
  capturedOpts: VoiceAgentStartOpts | null;
  setState(state: VoiceAgentState): void;
  setMicOn(on: boolean): void;
  setWsReady(ready: boolean): void;
};

export function createMockVoiceAgentHook(): MockVoiceAgentHandle {
  const handle: MockVoiceAgentHandle = {
    capturedOpts: null,
    setState(state) {
      (handle.hook as { state: VoiceAgentState }).state = state;
    },
    setMicOn(on) {
      (handle.hook as { micOn: boolean }).micOn = on;
    },
    setWsReady(ready) {
      (handle.hook as { wsReady: boolean }).wsReady = ready;
    },
    hook: {
      state: "idle",
      wsReady: false,
      micOn: false,
      start: vi.fn(async (opts: VoiceAgentStartOpts) => {
        handle.capturedOpts = opts;
        handle.setWsReady(true);
        handle.setState("listening");
      }),
      stop: vi.fn(() => {
        handle.setWsReady(false);
        handle.setMicOn(false);
        handle.setState("idle");
        handle.capturedOpts = null;
      }),
      enableMic: vi.fn(async () => {
        handle.setMicOn(true);
      }),
      disableMic: vi.fn(() => {
        handle.setMicOn(false);
      }),
      interrupt: vi.fn(),
      sendText: vi.fn().mockResolvedValue(undefined),
      submitWidget: vi.fn().mockResolvedValue(undefined),
      registerToolHandler: vi.fn(),
    },
  };
  return handle;
}
```

- [ ] **Step 3.2: Smoke-import the helper from a throw-away test**

Quickly verify the file compiles by running:

Run: `cd frontend && npx tsc --noEmit -p tsconfig.json 2>&1 | head -20`

Expected: no errors mentioning `mockVoiceAgentHook.ts`. (If there are project-wide errors unrelated to this file, they pre-exist.)

- [ ] **Step 3.3: Commit**

```bash
git add frontend/lib/__tests__/__helpers__/mockVoiceAgentHook.ts
git commit -m "test(voice): add MockVoiceAgentHook helper for store tests

Typed mock of VoiceAgentHook with vi.fn() spies. start() captures the
opts so tests can fire opts.onUserDelta?.(...) to simulate bridge events
flowing back into the consumer."
```

---

## Task 4: Rewrite `ghiseuStore` — new state shape + event handlers

**Why now:** all of Task 4's changes are local to the store; bridge lifecycle wiring comes in Task 5.

**Files:**
- Modify: `frontend/lib/ghiseuStore.ts` (full rewrite of internals)
- Modify: `frontend/lib/__tests__/ghiseuStore.test.ts` (delete scripted-flow tests; replace with event-driven tests)

- [ ] **Step 4.1: Rewrite `ghiseuStore.ts`**

Replace the entire contents of `frontend/lib/ghiseuStore.ts` with:

```ts
"use client";

import { create } from "zustand";
import type {
  VoiceAgentHook,
  VoiceAgentStartOpts,
} from "./useVoiceAgentBridge";

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

export type Line = { text: string; live: boolean };

type GhiseuStore = {
  state: GhiseuState;
  muted: boolean;
  exportMethod: ExportMethod;
  caption: { user: Line | null; agent: Line | null };

  /** Internal: bridge reference set by attachVoiceBridge. Read by lifecycle
   * actions. Not part of the consumer API. */
  _bridge: VoiceAgentHook | null;

  // ── event handlers (fired by bridge callbacks) ──
  appendUserPartial(text: string): void;
  commitUserMessage(text: string): void;
  appendAgentPartial(text: string): void;
  commitAgentMessage(text: string): void;

  // ── lifecycle ──
  attachVoiceBridge(bridge: VoiceAgentHook): () => void;
  enterVoiceMode(): Promise<void>;
  exitVoiceMode(): void;
  interrupt(): void;
  setMuted(muted: boolean): void;

  // ── existing surface (unchanged signatures) ──
  setState(state: GhiseuState): void;
  toggleMute(): void;
  confirmDoc(): void;
  amendDoc(): void;
  pickExport(method: Exclude<ExportMethod, null>): void;
  backToTalk(): void;
  reset(): void;
};

let thinkingTimer: ReturnType<typeof setTimeout> | null = null;

function clearThinkingTimer(): void {
  if (thinkingTimer !== null) {
    clearTimeout(thinkingTimer);
    thinkingTimer = null;
  }
}

export const useGhiseuStore = create<GhiseuStore>((set, get) => ({
  state: "idle",
  muted: true,
  exportMethod: null,
  caption: { user: null, agent: null },
  _bridge: null,

  // ── event handlers ──

  appendUserPartial: (text) => {
    set({
      caption: { ...get().caption, user: { text, live: true } },
    });
  },

  commitUserMessage: (text) => {
    set({
      caption: { ...get().caption, user: { text, live: false } },
    });
    // Schedule "thinking" — canceled by appendAgentPartial if agent
    // starts replying within 300ms.
    clearThinkingTimer();
    thinkingTimer = setTimeout(() => {
      set({ state: "thinking" });
      thinkingTimer = null;
    }, 300);
  },

  appendAgentPartial: (text) => {
    clearThinkingTimer();
    set({
      state: "speaking",
      caption: { ...get().caption, agent: { text, live: true } },
    });
  },

  commitAgentMessage: (text) => {
    set({
      state: "listening",
      caption: { ...get().caption, agent: { text, live: false } },
    });
  },

  // ── lifecycle ──

  attachVoiceBridge: (bridge) => {
    set({ _bridge: bridge });
    return () => {
      const current = get()._bridge;
      if (current) current.stop();
      set({ _bridge: null });
    };
  },

  enterVoiceMode: async () => {
    const bridge = get()._bridge;
    if (!bridge) {
      throw new Error("attachVoiceBridge() must be called before enterVoiceMode()");
    }
    // Evict any leftover session from a previous surface (e.g., ChatSurface).
    if (bridge.wsReady) bridge.stop();

    const opts: VoiceAgentStartOpts = {
      onUserDelta: (t) => get().appendUserPartial(t),
      onUserMessage: (t) => get().commitUserMessage(t),
      onAgentDelta: (t) => get().appendAgentPartial(t),
      onAgentMessage: (t) => get().commitAgentMessage(t),
    };

    // Run start() and enableMic() in parallel so the WS handshake (~1-2s)
    // overlaps with the mic boot (~200-500ms). Mirrors ChatSurface.enterVoiceMode.
    const startP = bridge.start(opts);
    const micP = bridge.enableMic();

    try {
      await Promise.all([startP, micP]);
      set({ state: "listening", muted: false });
    } catch (err) {
      if (err instanceof Error && err.name === "VoiceAgentMicDeniedError") {
        set({ state: "mic-denied" });
      } else {
        set({ state: "error" });
      }
      throw err;
    }
  },

  exitVoiceMode: () => {
    const bridge = get()._bridge;
    if (bridge) bridge.stop();
  },

  interrupt: () => {
    const bridge = get()._bridge;
    if (bridge) bridge.interrupt();
    // Optimistic: backend will echo "interrupted" → onInterrupted → state=listening,
    // but we set immediately so the UI snaps back without ~50ms latency.
    set({ state: "listening" });
  },

  setMuted: (muted) => set({ muted }),

  // ── existing surface ──

  setState: (state) => set({ state }),

  toggleMute: () => {
    const { state, _bridge: bridge } = get();
    // Post-reset idle: clicking mic re-engages voice mode entirely
    // (WS may be closed).
    if (state === "idle") {
      void get().enterVoiceMode().catch(() => {
        /* enterVoiceMode already sets error/mic-denied state */
      });
      return;
    }
    if (!bridge) return;
    if (bridge.micOn) {
      bridge.disableMic();
    } else {
      void bridge.enableMic().catch(() => {
        set({ state: "mic-denied" });
      });
    }
  },

  confirmDoc: () => {
    set({ state: "export" });
  },

  amendDoc: () => {
    set({ state: "listening" });
  },

  pickExport: (method) => {
    set({ state: "done", exportMethod: method });
  },

  backToTalk: () => {
    set({ state: "listening", muted: false });
  },

  reset: () => {
    clearThinkingTimer();
    get().exitVoiceMode();
    set({
      state: "idle",
      muted: true,
      exportMethod: null,
      caption: { user: null, agent: null },
    });
  },
}));
```

- [ ] **Step 4.2: Rewrite `frontend/lib/__tests__/ghiseuStore.test.ts`**

Replace the entire contents with:

```ts
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { useGhiseuStore } from "../ghiseuStore";

beforeEach(() => {
  useGhiseuStore.setState({
    state: "idle",
    muted: true,
    exportMethod: null,
    caption: { user: null, agent: null },
    _bridge: null,
  });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("ghiseuStore initial state", () => {
  it("starts idle, muted, no export method, empty caption", () => {
    const s = useGhiseuStore.getState();
    expect(s.state).toBe("idle");
    expect(s.muted).toBe(true);
    expect(s.exportMethod).toBeNull();
    expect(s.caption).toEqual({ user: null, agent: null });
  });
});

describe("ghiseuStore caption event handlers", () => {
  it("appendUserPartial sets caption.user with live:true", () => {
    useGhiseuStore.getState().appendUserPartial("salut");
    const c = useGhiseuStore.getState().caption;
    expect(c.user).toEqual({ text: "salut", live: true });
    expect(c.agent).toBeNull();
  });

  it("commitUserMessage sets caption.user with live:false and schedules thinking-transition", () => {
    useGhiseuStore.setState({ state: "listening" });
    useGhiseuStore.getState().commitUserMessage("salut, vreau o adeverință");
    expect(useGhiseuStore.getState().caption.user).toEqual({
      text: "salut, vreau o adeverință",
      live: false,
    });
    expect(useGhiseuStore.getState().state).toBe("listening"); // not yet
    vi.advanceTimersByTime(300);
    expect(useGhiseuStore.getState().state).toBe("thinking");
  });

  it("appendAgentPartial cancels the thinking-transition and goes straight to speaking", () => {
    useGhiseuStore.setState({ state: "listening" });
    useGhiseuStore.getState().commitUserMessage("salut");
    vi.advanceTimersByTime(100); // halfway through the 300ms window
    useGhiseuStore.getState().appendAgentPartial("buna");
    expect(useGhiseuStore.getState().state).toBe("speaking");
    vi.advanceTimersByTime(500); // advance past the original 300ms
    expect(useGhiseuStore.getState().state).toBe("speaking"); // unchanged
  });

  it("commitAgentMessage returns state to listening and marks agent line non-live", () => {
    useGhiseuStore.setState({ state: "speaking" });
    useGhiseuStore.getState().commitAgentMessage("am inteles");
    expect(useGhiseuStore.getState().state).toBe("listening");
    expect(useGhiseuStore.getState().caption.agent).toEqual({
      text: "am inteles",
      live: false,
    });
  });

  it("user and agent captions live independently (no cross-bleed)", () => {
    useGhiseuStore.getState().appendUserPartial("user a");
    useGhiseuStore.getState().appendAgentPartial("agent a");
    const c = useGhiseuStore.getState().caption;
    expect(c.user?.text).toBe("user a");
    expect(c.agent?.text).toBe("agent a");
  });
});

describe("ghiseuStore confirmDoc + amendDoc + pickExport + backToTalk", () => {
  it("confirmDoc transitions review → export", () => {
    useGhiseuStore.setState({ state: "review" });
    useGhiseuStore.getState().confirmDoc();
    expect(useGhiseuStore.getState().state).toBe("export");
  });

  it("amendDoc transitions review → listening", () => {
    useGhiseuStore.setState({ state: "review" });
    useGhiseuStore.getState().amendDoc();
    expect(useGhiseuStore.getState().state).toBe("listening");
  });

  it("pickExport transitions export → done and stores method", () => {
    useGhiseuStore.setState({ state: "export" });
    useGhiseuStore.getState().pickExport("city");
    expect(useGhiseuStore.getState().state).toBe("done");
    expect(useGhiseuStore.getState().exportMethod).toBe("city");
  });

  it("backToTalk returns to listening and unmutes", () => {
    useGhiseuStore.setState({ state: "export", muted: true });
    useGhiseuStore.getState().backToTalk();
    expect(useGhiseuStore.getState().state).toBe("listening");
    expect(useGhiseuStore.getState().muted).toBe(false);
  });
});

describe("ghiseuStore reset", () => {
  it("returns to idle, mutes, clears export method and caption", () => {
    useGhiseuStore.setState({
      state: "done",
      muted: false,
      exportMethod: "email",
      caption: { user: { text: "x", live: false }, agent: { text: "y", live: false } },
    });
    useGhiseuStore.getState().reset();
    const s = useGhiseuStore.getState();
    expect(s.state).toBe("idle");
    expect(s.muted).toBe(true);
    expect(s.exportMethod).toBeNull();
    expect(s.caption).toEqual({ user: null, agent: null });
  });

  it("reset() cancels a pending thinking-transition", () => {
    useGhiseuStore.setState({ state: "listening" });
    useGhiseuStore.getState().commitUserMessage("hello");
    vi.advanceTimersByTime(100);
    useGhiseuStore.getState().reset();
    vi.advanceTimersByTime(1000);
    expect(useGhiseuStore.getState().state).toBe("idle"); // never transitioned to thinking
  });
});
```

- [ ] **Step 4.3: Run the rewritten store tests**

Run: `cd frontend && npx vitest run lib/__tests__/ghiseuStore.test.ts`

Expected: All tests pass (caption handlers, scripted-flow tests are gone, idle/reset/transitions covered).

- [ ] **Step 4.4: Commit**

```bash
git add frontend/lib/ghiseuStore.ts frontend/lib/__tests__/ghiseuStore.test.ts
git commit -m "refactor(ghiseu): replace scripted setTimeout flow with event-driven store

Drops scriptedTalkingFlow + activeTimers. Adds:
- caption: { user, agent } field with Line { text, live } shape
- appendUserPartial / commitUserMessage / appendAgentPartial / commitAgentMessage
  handlers that the voice bridge will invoke
- 300ms thinking-debounce that gets canceled when agent starts replying

Bridge-lifecycle actions (attachVoiceBridge, enterVoiceMode, interrupt, etc.)
are wired but only exercised by the integration test in the next commit."
```

---

## Task 5: Integration tests for ghiseuStore + bridge

**Why now:** the store's bridge lifecycle methods are in place; this task proves they actually wire up the bridge callbacks correctly.

**Files:**
- Create: `frontend/lib/__tests__/ghiseuStore.bridge.test.ts`

- [ ] **Step 5.1: Write the failing tests**

Create `frontend/lib/__tests__/ghiseuStore.bridge.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useGhiseuStore } from "../ghiseuStore";
import { createMockVoiceAgentHook } from "./__helpers__/mockVoiceAgentHook";

beforeEach(() => {
  useGhiseuStore.setState({
    state: "idle",
    muted: true,
    exportMethod: null,
    caption: { user: null, agent: null },
    _bridge: null,
  });
});

describe("ghiseuStore.attachVoiceBridge", () => {
  it("stores the bridge reference and returns a cleanup that stops + nulls", () => {
    const mock = createMockVoiceAgentHook();
    const cleanup = useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    expect(useGhiseuStore.getState()._bridge).toBe(mock.hook);

    cleanup();
    expect(mock.hook.stop).toHaveBeenCalledTimes(1);
    expect(useGhiseuStore.getState()._bridge).toBeNull();
  });
});

describe("ghiseuStore.enterVoiceMode", () => {
  it("throws when no bridge attached", async () => {
    await expect(useGhiseuStore.getState().enterVoiceMode()).rejects.toThrow(
      /attachVoiceBridge/,
    );
  });

  it("calls bridge.start with the four event callbacks and bridge.enableMic", async () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);

    await useGhiseuStore.getState().enterVoiceMode();

    expect(mock.hook.start).toHaveBeenCalledTimes(1);
    expect(mock.hook.enableMic).toHaveBeenCalledTimes(1);
    expect(mock.capturedOpts).not.toBeNull();
    expect(mock.capturedOpts?.onUserDelta).toBeTypeOf("function");
    expect(mock.capturedOpts?.onUserMessage).toBeTypeOf("function");
    expect(mock.capturedOpts?.onAgentDelta).toBeTypeOf("function");
    expect(mock.capturedOpts?.onAgentMessage).toBeTypeOf("function");
    expect(useGhiseuStore.getState().state).toBe("listening");
    expect(useGhiseuStore.getState().muted).toBe(false);
  });

  it("calls bridge.stop first if bridge.wsReady was true (evicts leftover session)", async () => {
    const mock = createMockVoiceAgentHook();
    mock.setWsReady(true);
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);

    await useGhiseuStore.getState().enterVoiceMode();

    expect(mock.hook.stop).toHaveBeenCalled();
    // stop must have been called before start
    const stopOrder = (mock.hook.stop as ReturnType<typeof vi.fn>).mock.invocationCallOrder[0];
    const startOrder = (mock.hook.start as ReturnType<typeof vi.fn>).mock.invocationCallOrder[0];
    expect(stopOrder).toBeLessThan(startOrder);
  });

  it("transitions to mic-denied when enableMic throws VoiceAgentMicDeniedError", async () => {
    const mock = createMockVoiceAgentHook();
    const err = new Error("denied");
    err.name = "VoiceAgentMicDeniedError";
    (mock.hook.enableMic as ReturnType<typeof vi.fn>).mockRejectedValueOnce(err);
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);

    await expect(useGhiseuStore.getState().enterVoiceMode()).rejects.toThrow();
    expect(useGhiseuStore.getState().state).toBe("mic-denied");
  });

  it("transitions to error when start rejects", async () => {
    const mock = createMockVoiceAgentHook();
    (mock.hook.start as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("ws boom"),
    );
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);

    await expect(useGhiseuStore.getState().enterVoiceMode()).rejects.toThrow(/ws boom/);
    expect(useGhiseuStore.getState().state).toBe("error");
  });
});

describe("ghiseuStore captured callbacks update store state", () => {
  it("onUserDelta updates caption.user.text", async () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    await useGhiseuStore.getState().enterVoiceMode();

    mock.capturedOpts?.onUserDelta?.("partial user text");
    expect(useGhiseuStore.getState().caption.user).toEqual({
      text: "partial user text",
      live: true,
    });
  });

  it("onAgentDelta updates caption.agent and flips state to speaking", async () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    await useGhiseuStore.getState().enterVoiceMode();

    mock.capturedOpts?.onAgentDelta?.("agent reply");
    expect(useGhiseuStore.getState().caption.agent).toEqual({
      text: "agent reply",
      live: true,
    });
    expect(useGhiseuStore.getState().state).toBe("speaking");
  });
});

describe("ghiseuStore.interrupt", () => {
  it("calls bridge.interrupt and sets state to listening", () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    useGhiseuStore.setState({ state: "speaking" });

    useGhiseuStore.getState().interrupt();

    expect(mock.hook.interrupt).toHaveBeenCalledTimes(1);
    expect(useGhiseuStore.getState().state).toBe("listening");
  });

  it("is a no-op on the bridge when nothing is attached", () => {
    useGhiseuStore.setState({ state: "speaking" });
    expect(() => useGhiseuStore.getState().interrupt()).not.toThrow();
    expect(useGhiseuStore.getState().state).toBe("listening");
  });
});

describe("ghiseuStore.reset stops the bridge", () => {
  it("reset() calls bridge.stop via exitVoiceMode", async () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    await useGhiseuStore.getState().enterVoiceMode();

    useGhiseuStore.getState().reset();
    expect(mock.hook.stop).toHaveBeenCalledTimes(1);
    expect(useGhiseuStore.getState().state).toBe("idle");
    expect(useGhiseuStore.getState().caption).toEqual({ user: null, agent: null });
  });
});

describe("ghiseuStore.toggleMute", () => {
  it("calls enableMic when bridge.micOn is false", async () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    await useGhiseuStore.getState().enterVoiceMode();
    mock.setMicOn(false);
    (mock.hook.enableMic as ReturnType<typeof vi.fn>).mockClear();

    useGhiseuStore.setState({ state: "listening" });
    useGhiseuStore.getState().toggleMute();

    expect(mock.hook.enableMic).toHaveBeenCalledTimes(1);
  });

  it("calls disableMic when bridge.micOn is true", async () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    await useGhiseuStore.getState().enterVoiceMode();
    mock.setMicOn(true);

    useGhiseuStore.setState({ state: "listening" });
    useGhiseuStore.getState().toggleMute();

    expect(mock.hook.disableMic).toHaveBeenCalledTimes(1);
  });

  it("from idle, calls enterVoiceMode (which calls start + enableMic)", () => {
    const mock = createMockVoiceAgentHook();
    useGhiseuStore.getState().attachVoiceBridge(mock.hook);
    useGhiseuStore.setState({ state: "idle" });

    useGhiseuStore.getState().toggleMute();

    // enterVoiceMode is async; we just confirm start was kicked off.
    expect(mock.hook.start).toHaveBeenCalled();
  });
});
```

- [ ] **Step 5.2: Run the bridge integration tests**

Run: `cd frontend && npx vitest run lib/__tests__/ghiseuStore.bridge.test.ts`

Expected: All tests pass.

- [ ] **Step 5.3: Commit**

```bash
git add frontend/lib/__tests__/ghiseuStore.bridge.test.ts
git commit -m "test(ghiseu): bridge integration tests for ghiseuStore

Covers attach + enterVoiceMode (parallel start/enableMic), captured
callbacks flowing back into caption state, mic-denied/error transitions,
interrupt + reset cleanup, and toggleMute's three branches (idle re-enter,
enable, disable)."
```

---

## Task 6: Update `CaptionStrip` to read live caption from the store

**Why now:** the store has the caption field populated; the UI needs to render it.

**Files:**
- Modify: `frontend/components/ghiseu/CaptionStrip.tsx`
- Modify: `frontend/components/ghiseu/__tests__/CaptionStrip.test.tsx`

- [ ] **Step 6.1: Update `CaptionStrip.tsx`**

Replace `frontend/components/ghiseu/CaptionStrip.tsx` with:

```tsx
"use client";

import { type GhiseuState, useGhiseuStore } from "@/lib/ghiseuStore";

type Line = { text: string; final?: boolean } | null;

type Transcript = Record<GhiseuState, { user: Line; agent: Line }>;

// Design-copy fallback shown when no live caption exists yet (e.g., the
// agent's greeting placeholder before the user has spoken).
const TRANSCRIPT: Transcript = {
  idle: {
    user: null,
    agent: { text: "Bună! Spune-mi cu ce te pot ajuta astăzi.", final: true },
  },
  listening: {
    user: null,
    agent: { text: "Te ascult.", final: true },
  },
  thinking: { user: null, agent: null },
  speaking: { user: null, agent: null },
  review: {
    user: null,
    agent: {
      text: "Am pregătit cererea. Verifică datele înainte să o trimitem.",
      final: true,
    },
  },
  export: { user: null, agent: null },
  done: { user: null, agent: null },
  error: { user: null, agent: null },
  "mic-denied": { user: null, agent: null },
};

type Props = { state: GhiseuState };

export function CaptionStrip({ state }: Props) {
  const liveCaption = useGhiseuStore((s) => s.caption);
  const fallback = TRANSCRIPT[state];

  const user: Line = liveCaption.user
    ? { text: liveCaption.user.text, final: !liveCaption.user.live }
    : fallback.user;
  const agent: Line = liveCaption.agent
    ? { text: liveCaption.agent.text, final: !liveCaption.agent.live }
    : fallback.agent;

  if (!user && !agent) return null;
  return (
    <div className="gh-caption" aria-live="polite">
      {user ? (
        <div className="gh-cap-line" data-role="user">
          <span className="gh-cap-tag">Tu</span>
          <span className="gh-cap-text">
            {user.final ? (
              user.text
            ) : (
              <span className="partial">{user.text}</span>
            )}
          </span>
        </div>
      ) : null}
      {agent ? (
        <div className="gh-cap-line" data-role="agent">
          <span className="gh-cap-tag">eGata</span>
          <span className="gh-cap-text">{agent.text}</span>
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 6.2: Update `CaptionStrip.test.tsx`**

Replace `frontend/components/ghiseu/__tests__/CaptionStrip.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { CaptionStrip } from "../CaptionStrip";
import { useGhiseuStore } from "@/lib/ghiseuStore";

beforeEach(() => {
  useGhiseuStore.setState({
    state: "idle",
    muted: true,
    exportMethod: null,
    caption: { user: null, agent: null },
    _bridge: null,
  });
});

describe("CaptionStrip fallback (no live caption)", () => {
  it("renders the agent greeting in idle", () => {
    render(<CaptionStrip state="idle" />);
    expect(
      screen.getByText(/Bună! Spune-mi cu ce te pot ajuta/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Tu$/)).toBeNull();
  });

  it("renders nothing in error", () => {
    const { container } = render(<CaptionStrip state="error" />);
    expect(container.firstChild).toBeNull();
  });
});

describe("CaptionStrip live caption (from store)", () => {
  it("renders the live user partial with the partial wrapper", () => {
    useGhiseuStore.setState({
      caption: {
        user: { text: "vreau o adeverin", live: true },
        agent: null,
      },
    });
    render(<CaptionStrip state="listening" />);
    expect(screen.getByText(/^Tu$/)).toBeInTheDocument();
    const userText = screen.getByText(/vreau o adeverin/);
    expect(userText.tagName).toBe("SPAN");
    expect(userText.className).toContain("partial");
  });

  it("renders both Tu and eGata bubbles when both captions present", () => {
    useGhiseuStore.setState({
      caption: {
        user: { text: "vreau o adeverință", live: false },
        agent: { text: "te ajut imediat", live: true },
      },
    });
    render(<CaptionStrip state="speaking" />);
    expect(screen.getByText(/vreau o adeverință/)).toBeInTheDocument();
    expect(screen.getByText(/te ajut imediat/)).toBeInTheDocument();
  });

  it("live caption overrides fallback when set", () => {
    useGhiseuStore.setState({
      caption: {
        user: null,
        agent: { text: "salut concret", live: false },
      },
    });
    render(<CaptionStrip state="idle" />);
    expect(screen.getByText(/salut concret/)).toBeInTheDocument();
    expect(screen.queryByText(/Bună! Spune-mi/i)).toBeNull();
  });
});
```

- [ ] **Step 6.3: Run the CaptionStrip tests**

Run: `cd frontend && npx vitest run components/ghiseu/__tests__/CaptionStrip.test.tsx`

Expected: All tests pass.

- [ ] **Step 6.4: Commit**

```bash
git add frontend/components/ghiseu/CaptionStrip.tsx frontend/components/ghiseu/__tests__/CaptionStrip.test.tsx
git commit -m "feat(ghiseu): CaptionStrip renders live caption from store

Reads caption.user / caption.agent from useGhiseuStore. Falls back to
the design-copy TRANSCRIPT[state] map when either is null (mainly the
agent greeting in idle). Live captions show the partial wrapper while
live: true."
```

---

## Task 7: Wire `GhiseuShell` to the voice context with lifecycle effects

**Why now:** the store and components are ready; GhiseuShell just needs to attach + auto-enter.

**Files:**
- Modify: `frontend/components/ghiseu/GhiseuShell.tsx`
- Create: `frontend/components/ghiseu/__tests__/GhiseuShell.test.tsx`

- [ ] **Step 7.1: Write the failing test**

Create `frontend/components/ghiseu/__tests__/GhiseuShell.test.tsx`:

```tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render } from "@testing-library/react";
import { GhiseuShell } from "../GhiseuShell";
import { useGhiseuStore } from "@/lib/ghiseuStore";
import { useSessionStore } from "@/lib/sessionStore";
import { createMockVoiceAgentHook, type MockVoiceAgentHandle } from "@/lib/__tests__/__helpers__/mockVoiceAgentHook";

// Replace useVoiceContext with a settable test double.
let currentMock: MockVoiceAgentHandle;
vi.mock("@/lib/voiceContext", () => ({
  useVoiceContext: () => currentMock.hook,
}));

beforeEach(() => {
  currentMock = createMockVoiceAgentHook();
  useGhiseuStore.setState({
    state: "idle",
    muted: true,
    exportMethod: null,
    caption: { user: null, agent: null },
    _bridge: null,
  });
  useSessionStore.setState({ kioskMode: false, citizen: { id: "c1", name: "Test", roeid_attributes: {} } as never });
});

describe("GhiseuShell lifecycle", () => {
  it("attaches the voice bridge on mount", () => {
    render(<GhiseuShell />);
    expect(useGhiseuStore.getState()._bridge).toBe(currentMock.hook);
  });

  it("sets kioskMode=true on mount and clears it on unmount", () => {
    const { unmount } = render(<GhiseuShell />);
    expect(useSessionStore.getState().kioskMode).toBe(true);
    unmount();
    expect(useSessionStore.getState().kioskMode).toBe(false);
  });

  it("on unmount, stops the bridge via attach-cleanup", () => {
    const { unmount } = render(<GhiseuShell />);
    unmount();
    expect(currentMock.hook.stop).toHaveBeenCalled();
    expect(useGhiseuStore.getState()._bridge).toBeNull();
  });

  it("auto-calls enterVoiceMode when a citizen is hydrated", async () => {
    render(<GhiseuShell />);
    // enterVoiceMode is async; allow the effect to flush.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(currentMock.hook.start).toHaveBeenCalledTimes(1);
    expect(currentMock.hook.enableMic).toHaveBeenCalledTimes(1);
  });

  it("does NOT call enterVoiceMode when citizen is null", async () => {
    useSessionStore.setState({ citizen: null });
    render(<GhiseuShell />);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(currentMock.hook.start).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 7.2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run components/ghiseu/__tests__/GhiseuShell.test.tsx`

Expected: FAIL — GhiseuShell does not currently attach the bridge, set kioskMode, or call enterVoiceMode.

- [ ] **Step 7.3: Wire GhiseuShell**

Replace `frontend/components/ghiseu/GhiseuShell.tsx`:

```tsx
"use client";

import { useEffect, useRef } from "react";
import { useAccessibilityClasses } from "@/lib/accessibilityStore";
import { useGhiseuStore } from "@/lib/ghiseuStore";
import { useSessionStore } from "@/lib/sessionStore";
import { useVoiceContext } from "@/lib/voiceContext";
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

  const voice = useVoiceContext();
  const citizen = useSessionStore((s) => s.citizen);
  const setKioskMode = useSessionStore((s) => s.setKioskMode);

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
  const attachVoiceBridge = useGhiseuStore((s) => s.attachVoiceBridge);
  const enterVoiceMode = useGhiseuStore((s) => s.enterVoiceMode);
  const setMuted = useGhiseuStore((s) => s.setMuted);

  // Effect A: attach bridge + flip kioskMode on mount; reverse on unmount.
  useEffect(() => {
    setKioskMode(true);
    const cleanup = attachVoiceBridge(voice);
    return () => {
      cleanup();
      setKioskMode(false);
    };
  }, [voice, attachVoiceBridge, setKioskMode]);

  // Effect B: auto-enter voice mode once a citizen is hydrated, but only
  // once per mount. Guard with a ref so re-renders don't re-fire.
  const enteredRef = useRef(false);
  useEffect(() => {
    if (!citizen || enteredRef.current) return;
    enteredRef.current = true;
    void enterVoiceMode().catch(() => {
      // enterVoiceMode already sets error / mic-denied state on the store.
    });
  }, [citizen, enterVoiceMode]);

  // Effect C: mirror voice.micOn into store.muted so the UI's ripple +
  // mic button label stay in sync with the actual hardware state.
  useEffect(() => {
    setMuted(!voice.micOn);
  }, [voice.micOn, setMuted]);

  let content;
  if (state === "review") {
    content = <DocumentReview onConfirm={confirmDoc} onAmend={amendDoc} />;
  } else if (state === "export") {
    content = <ExportOptions onPick={pickExport} />;
  } else if (state === "done") {
    content = <DoneScreen method={exportMethod ?? "city"} onRestart={reset} />;
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

- [ ] **Step 7.4: Run the GhiseuShell test to verify pass**

Run: `cd frontend && npx vitest run components/ghiseu/__tests__/GhiseuShell.test.tsx`

Expected: All tests pass.

- [ ] **Step 7.5: Commit**

```bash
git add frontend/components/ghiseu/GhiseuShell.tsx frontend/components/ghiseu/__tests__/GhiseuShell.test.tsx
git commit -m "feat(ghiseu): wire GhiseuShell to voice context with lifecycle effects

Three effects:
- attach the voice bridge + set kioskMode=true on mount; reverse on unmount
- auto-call enterVoiceMode once citizen is hydrated (guarded to fire once)
- mirror voice.micOn into ghiseuStore.muted so UI ripple stays in sync"
```

---

## Task 8: Full-suite regression check

**Why now:** several files touched; surface-level checks alone are not enough.

- [ ] **Step 8.1: Run the entire frontend test suite**

Run: `cd frontend && npx vitest run`

Expected: All tests pass. If any pre-existing test fails, investigate before proceeding — it likely depends on the old ghiseuStore scripted-flow or sessionStore shape.

- [ ] **Step 8.2: Type-check the frontend**

Run: `cd frontend && npx tsc --noEmit -p tsconfig.json`

Expected: zero new errors. (Compare to the count before Task 1.)

- [ ] **Step 8.3: Lint check (if a lint script exists)**

Run: `cd frontend && npm run lint 2>/dev/null || echo "no lint script"`

Expected: zero new violations.

---

## Task 9: Manual smoke test

**Why last:** automated tests cover behaviors in isolation; this verifies the actual end-to-end voice flow against the real backend.

- [ ] **Step 9.1: Start the backend** (in a separate terminal)

Run: `cd backend && uv run uvicorn app.main:app --reload --port 8000`

Expected: server listens on port 8000. Confirm `/health` returns 200.

- [ ] **Step 9.2: Start the frontend dev server** (in a separate terminal)

Run: `cd frontend && npm run dev`

Expected: Next.js listens on port 3000.

- [ ] **Step 9.3: Manual flow — kiosk happy path**

In the browser:
1. Go to `http://localhost:3000/login`
2. Toggle "Modul Ghișeu" ON
3. Enter the seeded phone + complete OTP
4. Verify the URL is `/ghiseu`
5. Verify the green mic ripple is visible (auto-engage worked)
6. Speak: "vreau o adeverință de venit"
7. Verify the `Tu:` bubble shows your speech text (live updating)
8. After you stop speaking, verify a brief `thinking` state may flash, then the agent's reply streams into the `eGata:` bubble with audio
9. Click `Întrerupe` while the agent is mid-sentence
10. Verify audio stops within ~100ms and the UI returns to `listening`
11. Click `Ia-o de la capăt`
12. Verify UI returns to `idle` with the unlit mic
13. Click the mic again
14. Verify voice mode re-engages

- [ ] **Step 9.4: Manual flow — kiosk does not navigate**

Continuing from step 9.3 step 14:
1. Tell the agent: "începe procedura pentru adeverință de venit"
2. Agent should call `start_procedure` server-side
3. Verify the browser URL **stays at `/ghiseu`** (does NOT navigate to `/r/<id>`)

- [ ] **Step 9.5: Manual flow — regular chat unaffected**

1. In a new tab, navigate to `http://localhost:3000/`
2. Verify the chat surface loads normally
3. Enter voice mode by clicking the mic
4. Verify voice still works in `/` (no regression from the kiosk's WS ownership)

- [ ] **Step 9.6: If all manual checks pass, mark the phase complete**

Update the parent roadmap `docs/superpowers/plans/2026-05-24-modul-ghiseu-phase-2-integration.md` — under "Phase 2.1" change the header to add `(✓ complete YYYY-MM-DD)`.

Commit:
```bash
git add docs/superpowers/plans/2026-05-24-modul-ghiseu-phase-2-integration.md
git commit -m "docs(ghiseu): mark Phase 2.1 complete in roadmap"
```

---

## Spec coverage table

| Spec section | Implementing task(s) |
|---|---|
| D1 — Bridge ownership: surface-owned start/stop | Tasks 4, 5, 7 |
| D2 — Caption data source: callback-driven | Tasks 4, 5 (capturedOpts test), 6 |
| D3 — Kiosk navigation suppression (single-line `pushPath` guard) | Task 2 |
| D4 — `interrupt()` on `VoiceAgentHook` | Task 1 |
| D5 — Reset is unmount-equivalent; auto-engage only on first mount | Tasks 4 (reset clears caption), 7 (enteredRef guards re-entry) |
| D6 — Thinking debounce (300ms) | Task 4 (`commitUserMessage`, test) |
| Store shape: `caption`, `_bridge`, event handlers, lifecycle, setMuted, toggleMute idle branch | Task 4 |
| sessionStore additions: `kioskMode`, `setKioskMode`, guard in `pushPath` | Task 2 |
| `useVoiceAgentBridge.interrupt()` | Task 1 |
| Component touch list (CaptionStrip, GhiseuShell, ControlsDock, VoiceStage) | Tasks 6, 7 (ControlsDock + VoiceStage unchanged — already work) |
| Acceptance criteria | Task 9 |
| Test list (ghiseuStore unit + bridge integration, sessionStore kioskMode, useVoiceAgentBridge.interrupt, CaptionStrip, GhiseuShell) | Tasks 1, 2, 4, 5, 6, 7 |
