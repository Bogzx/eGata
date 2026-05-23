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
