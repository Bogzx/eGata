"use client";

import { useCallback, useMemo } from "react";
import type { VoicePreferences } from "./types";

export type VoiceAgentState = "idle" | "connecting" | "listening" | "speaking" | "error";

export type ToolCallHandler = (
  name: string,
  args: Record<string, unknown>,
) => Promise<Record<string, unknown>>;

export type VoiceAgentHook = {
  state: VoiceAgentState;
  start: (opts: {
    documentId?: string;
    preferences?: VoicePreferences;
    onAgentMessage?: (text: string) => void;
    onTranscript?: (text: string) => void;
  }) => Promise<void>;
  stop: () => void;
  sendText: (text: string) => Promise<void>;
  registerToolHandler: (handler: ToolCallHandler) => void;
  lastTranscript: string;
  lastAgentMessage: string;
};

export function useVoiceAgent(): VoiceAgentHook {
  const start = useCallback(async () => {
    throw new Error("Voice not yet implemented (Plan 3 wires Gemini Live).");
  }, []);

  const stop = useCallback(() => {
    // no-op stub
  }, []);

  const sendText = useCallback(async (_text: string) => {
    // no-op stub; Plan 3 forwards text to the Gemini Live session.
  }, []);

  const registerToolHandler = useCallback((_handler: ToolCallHandler) => {
    // no-op stub
  }, []);

  return useMemo(
    () => ({
      state: "idle" as VoiceAgentState,
      start,
      stop,
      sendText,
      registerToolHandler,
      lastTranscript: "",
      lastAgentMessage: "",
    }),
    [start, stop, sendText, registerToolHandler],
  );
}
