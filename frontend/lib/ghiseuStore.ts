"use client";

import { create } from "zustand";
import { api, ApiError } from "./api";
import { useSessionStore } from "./sessionStore";
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
  | "submitting"
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
  pickExport(method: Exclude<ExportMethod, null>): Promise<void>;
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

/** Voice-driven states are the only ones whose transitions are owned by
 * agent events. UI-flow states (review/export/submitting/done) and failure
 * states (error/mic-denied) must NOT be transitioned out of by an
 * incoming agent delta — otherwise an accidental utterance on the done
 * screen would yank the user back to the voice ripple. */
function isVoiceDrivenState(state: GhiseuState): boolean {
  return (
    state === "idle" ||
    state === "listening" ||
    state === "thinking" ||
    state === "speaking"
  );
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
    // Don't schedule the thinking-flash when the UI is in a non-voice
    // state (review/export/submitting/done/error/mic-denied). Otherwise
    // an accidental utterance after the done screen lands would flip
    // the kiosk back to the voice ripple.
    if (!isVoiceDrivenState(get().state)) return;
    thinkingTimer = setTimeout(() => {
      if (!isVoiceDrivenState(get().state)) return;
      set({ state: "thinking" });
      thinkingTimer = null;
    }, 300);
  },

  appendAgentPartial: (text) => {
    clearThinkingTimer();
    const current = get().state;
    if (!isVoiceDrivenState(current)) {
      // Update the caption (in case some surface wants to show it), but
      // do NOT transition state — the done/review/export screen stays.
      set({ caption: { ...get().caption, agent: { text, live: true } } });
      return;
    }
    set({
      state: "speaking",
      caption: { ...get().caption, agent: { text, live: true } },
    });
  },

  commitAgentMessage: (text) => {
    const current = get().state;
    if (!isVoiceDrivenState(current)) {
      set({ caption: { ...get().caption, agent: { text, live: false } } });
      return;
    }
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
      // Don't clobber a UI-flow state (review/export/done) that the
      // sessionStore.session.state mirror or the user's clicks may have set
      // while we were waiting on the WS handshake. Only update mic-driven
      // state when we're in a voice-driven state or fresh-idle.
      const current = get().state;
      const voiceDriven =
        current === "idle" ||
        current === "listening" ||
        current === "thinking" ||
        current === "speaking";
      set(voiceDriven ? { state: "listening", muted: false } : { muted: false });
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
    // Stay on the review screen. The user speaks corrections; the agent
    // fires set_field; sessionStore.document.fields updates; the field
    // grid re-renders in place. No state transition needed.
    clearThinkingTimer();
  },

  pickExport: async (method) => {
    const docId = useSessionStore.getState().activeDocId;
    if (!docId) {
      // Defensive: shouldn't happen — review screen requires an active doc.
      set({ state: "error", exportMethod: method });
      return;
    }
    set({ state: "submitting", exportMethod: method });
    try {
      const res = await api.submitDocument(docId, { method });
      // Refresh the document so DoneScreen picks up ref_number via the
      // sessionStore subscription. The submit endpoint returns the ref
      // directly, but the canonical surface for ref_number is doc.ref_number.
      try {
        const fresh = await api.getDocument(docId);
        useSessionStore.setState({ document: fresh });
      } catch {
        // Fallback: patch the existing document object in place with the
        // ref we already have from the submit response.
        const current = useSessionStore.getState().document;
        if (current) {
          useSessionStore.setState({
            document: { ...current, ref_number: res.ref_number },
          });
        }
      }
      set({ state: "done" });
    } catch (err) {
      // 409 = already delivered. Treat as success — the user has already
      // landed on the done screen for this doc previously.
      if (
        err instanceof ApiError &&
        err.status === 409 &&
        typeof err.body === "object" &&
        err.body !== null
      ) {
        const body = err.body as { ref_number?: string };
        const current = useSessionStore.getState().document;
        if (current && body.ref_number) {
          useSessionStore.setState({
            document: { ...current, ref_number: body.ref_number },
          });
        }
        set({ state: "done" });
        return;
      }
      set({ state: "error" });
    }
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
