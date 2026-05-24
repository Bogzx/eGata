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

  // event handlers (fired by bridge callbacks)
  appendUserPartial(text: string): void;
  commitUserMessage(text: string): void;
  appendAgentPartial(text: string): void;
  commitAgentMessage(text: string): void;

  // lifecycle
  attachVoiceBridge(bridge: VoiceAgentHook): () => void;
  enterVoiceMode(): Promise<void>;
  exitVoiceMode(): void;
  interrupt(): void;
  setMuted(muted: boolean): void;

  // existing surface
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

  appendUserPartial: (text) => {
    set({
      caption: { ...get().caption, user: { text, live: true } },
    });
  },

  commitUserMessage: (text) => {
    set({
      caption: { ...get().caption, user: { text, live: false } },
    });
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
    if (bridge.wsReady) bridge.stop();

    const opts: VoiceAgentStartOpts = {
      onUserDelta: (t) => get().appendUserPartial(t),
      onUserMessage: (t) => get().commitUserMessage(t),
      onAgentDelta: (t) => get().appendAgentPartial(t),
      onAgentMessage: (t) => get().commitAgentMessage(t),
    };

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
    set({ state: "listening" });
  },

  setMuted: (muted) => set({ muted }),

  setState: (state) => set({ state }),

  toggleMute: () => {
    const { state, muted, _bridge: bridge } = get();
    if (state === "idle") {
      void get().enterVoiceMode().catch(() => {
        /* enterVoiceMode already sets error/mic-denied state */
      });
      return;
    }
    if (!bridge) return;
    // Use the store's `muted` (mirrored from voice.micOn by GhiseuShell)
    // as the truth source — `bridge.micOn` is a stale snapshot from the
    // render when attachVoiceBridge ran.
    if (!muted) {
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
