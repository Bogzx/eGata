"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  useAccessibilityPrefs,
  useLargeTextClass,
} from "@/lib/accessibilityStore";
import { useKioskMode } from "@/lib/kioskMode";
import { getSession } from "@/lib/session";
import { useSessionStore } from "@/lib/sessionStore";
import type { WidgetSpec } from "@/lib/types";
import {
  VoiceAgentMicDeniedError,
  useVoiceAgent,
} from "@/lib/useVoiceAgent";
import { ChatPane } from "./ChatPane";
import { DocumentsDrawer } from "./DocumentsDrawer";
import { ProfileMenu } from "./ProfileMenu";
import { RightPane } from "./RightPane";
import { TopBar } from "./TopBar";

function makeMsgId(): string {
  return Math.random().toString(36).slice(2, 11);
}

type Props = {
  activeDocId: string | null;
};

export function ChatSurface({ activeDocId }: Props) {
  useLargeTextClass();
  const router = useRouter();
  const isKiosk = useKioskMode();
  const voiceOnly = useAccessibilityPrefs((s) => s.voiceOnly);
  const simpleLanguage = useAccessibilityPrefs((s) => s.simpleLanguage);

  const citizen = useSessionStore((s) => s.citizen);
  const hydrateCitizen = useSessionStore((s) => s.hydrateCitizen);
  const loadDocument = useSessionStore((s) => s.loadDocument);
  const sendText = useSessionStore((s) => s.sendText);
  const appendMessage = useSessionStore((s) => s.appendMessage);
  const setVoiceStatus = useSessionStore((s) => s.setVoiceStatus);
  const applyToolResult = useSessionStore((s) => s.applyToolResult);
  const reset = useSessionStore((s) => s.reset);
  const rightPaneKind = useSessionStore((s) => s.rightPane.kind);

  const voice = useVoiceAgent();
  const voiceStartedRef = useRef(false);

  // Auth gate.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!getSession()) router.replace("/login");
  }, [router]);

  // Hydrate citizen once.
  useEffect(() => {
    if (citizen) return;
    void hydrateCitizen().catch(() => {});
  }, [citizen, hydrateCitizen]);

  // Hydrate the active doc if the URL has /r/<id>.
  useEffect(() => {
    if (!activeDocId) {
      reset();
      return;
    }
    void loadDocument(activeDocId).catch(() => {});
  }, [activeDocId, loadDocument, reset]);

  // Browser back/forward sync.
  useEffect(() => {
    function onPop() {
      const path = window.location.pathname;
      if (path === "/") reset();
      else if (path.startsWith("/r/")) {
        const id = path.slice(3);
        void loadDocument(id);
      }
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [reset, loadDocument]);

  // Mirror voice agent state into the store so the composer mic can react.
  useEffect(() => {
    setVoiceStatus(voice.state);
  }, [voice.state, setVoiceStatus]);

  // Wire transcripts → chat messages.
  const lastUserT = voice.lastTranscript;
  const lastAgentT = voice.lastAgentMessage;
  const prevUserT = useRef("");
  const prevAgentT = useRef("");
  useEffect(() => {
    if (lastUserT && lastUserT !== prevUserT.current) {
      appendMessage({
        id: makeMsgId(),
        role: "user",
        text: lastUserT,
        via: "voice",
      });
      prevUserT.current = lastUserT;
    }
  }, [lastUserT, appendMessage]);
  useEffect(() => {
    if (lastAgentT && lastAgentT !== prevAgentT.current) {
      appendMessage({
        id: makeMsgId(),
        role: "agent",
        text: lastAgentT,
      });
      prevAgentT.current = lastAgentT;
    }
  }, [lastAgentT, appendMessage]);

  // Tool dispatch path during voice — forward results into the store.
  useEffect(() => {
    voice.registerToolHandler(async (name, args) => {
      const merged = args as Record<string, unknown> & { _result?: unknown };
      const realArgs: Record<string, unknown> = { ...merged };
      const result = merged._result;
      delete realArgs._result;
      await applyToolResult(name, realArgs, result);
      return {};
    });
  }, [voice, applyToolResult]);

  // Auto-start voice for voice_only users once citizen is hydrated.
  useEffect(() => {
    if (!voiceOnly || !citizen || voiceStartedRef.current) return;
    voiceStartedRef.current = true;
    void voice
      .start({
        documentId: activeDocId ?? undefined,
        preferences: { simple_language: simpleLanguage, voice_only: voiceOnly },
      })
      .catch((err) => {
        if (err instanceof VoiceAgentMicDeniedError) {
          appendMessage({
            id: makeMsgId(),
            role: "system",
            text: "Microfonul nu este permis. Folosește textul.",
          });
        }
      });
  }, [voiceOnly, citizen, activeDocId, simpleLanguage, voice, appendMessage]);

  async function startVoice() {
    if (!citizen) return;
    try {
      await voice.start({
        documentId: useSessionStore.getState().activeDocId ?? undefined,
        preferences: { simple_language: simpleLanguage, voice_only: voiceOnly },
      });
    } catch (err) {
      if (err instanceof VoiceAgentMicDeniedError) {
        appendMessage({
          id: makeMsgId(),
          role: "system",
          text: "Microfonul nu este permis. Folosește textul.",
        });
      }
    }
  }

  function stopVoice() {
    voice.stop();
  }

  async function onSendText(t: string) {
    // If a voice WS is active, push text into the live session so the agent
    // hears it; otherwise hit /agent/chat. Either way, the message bubble is
    // appended (voice path appends via WS callback, text path via store).
    if (voice.state === "listening" || voice.state === "speaking") {
      await voice.sendText(t);
      appendMessage({
        id: makeMsgId(),
        role: "user",
        text: t,
        via: "text",
      });
      return;
    }
    await sendText(t);
  }

  function onWidgetSubmit(_spec: WidgetSpec, value: string) {
    void onSendText(value);
  }

  if (!citizen) {
    return <p className="p-6 text-muted-foreground">Se încarcă...</p>;
  }

  const engaged = rightPaneKind !== "welcome";
  const hideRightPane = voiceOnly;

  const gridClass = hideRightPane
    ? "grid h-full min-h-0 grid-cols-1 overflow-hidden"
    : engaged
      ? "grid h-full min-h-0 grid-cols-1 overflow-hidden md:grid-cols-[40%_60%]"
      : "grid h-full min-h-0 grid-cols-1 overflow-hidden";

  return (
    <div
      data-mode={engaged ? "engaged" : "idle"}
      data-kiosk={isKiosk ? "true" : "false"}
      className="flex h-screen w-screen flex-col bg-background text-foreground"
    >
      <TopBar />
      <ProfileMenu />
      <DocumentsDrawer />
      <main className={gridClass}>
        <ChatPane
          onWidgetSubmit={onWidgetSubmit}
          onSendText={onSendText}
          onStartVoice={startVoice}
          onStopVoice={stopVoice}
        />
        {engaged && !hideRightPane ? (
          <aside className="overflow-y-auto border-l" aria-label="Document">
            <RightPane />
          </aside>
        ) : null}
      </main>
    </div>
  );
}
