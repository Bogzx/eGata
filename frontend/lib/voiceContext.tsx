"use client";

import { createContext, useContext, useEffect, type ReactNode } from "react";
import { prewarmMicPermission } from "./audioWorklet";
import { useVoiceAgentBridge, type VoiceAgentHook } from "./useVoiceAgentBridge";

// Why this file exists: ChatSurface was calling useVoiceAgentBridge directly,
// which meant the voice WS lived inside ChatSurface's lifetime. When the
// agent fires start_procedure → document_opened → sessionStore.loadDocument →
// pushPath('/r/<id>'), Next.js unmounts the / page and ChatSurface with it.
// The hook's cleanup effect (`useEffect(() => () => stop(), [stop])`) then
// closes the WS — mic dies mid-conversation.
//
// The fix: mount the hook ONCE inside a context provider at root-layout
// level (above the Next.js route boundary). ChatSurface consumes it via
// `useVoiceContext()`. Navigation between / and /r/[id] never unmounts the
// provider, so the WS, recorder, and player live across phase transitions.

const VoiceContext = createContext<VoiceAgentHook | null>(null);

export function VoiceProvider({ children }: { children: ReactNode }) {
  const voice = useVoiceAgentBridge();
  // Prewarm the mic permission as soon as the authenticated app mounts.
  // Without this the first mic click pays for both the permission prompt
  // and the hardware/worklet init at the same time, which stalls the UI
  // for ~500ms+ on a cold permission. We acquire the stream and release
  // the tracks immediately so the mic isn't actually open.
  useEffect(() => {
    void prewarmMicPermission();
  }, []);
  return (
    <VoiceContext.Provider value={voice}>{children}</VoiceContext.Provider>
  );
}

export function useVoiceContext(): VoiceAgentHook {
  const ctx = useContext(VoiceContext);
  if (!ctx) {
    throw new Error(
      "useVoiceContext must be used inside <VoiceProvider> (root layout wraps it).",
    );
  }
  return ctx;
}
