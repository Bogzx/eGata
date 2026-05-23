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
  useVoiceAgentBridge as useVoiceAgent,
} from "@/lib/useVoiceAgentBridge";
import { AnimatedBackground } from "./AnimatedBackground";
import { ChatStream } from "./ChatStream";
import { Composer } from "./Composer";
import { DocumentsDrawer } from "./DocumentsDrawer";
import { ProfileMenu } from "./ProfileMenu";
import { RightPane } from "./RightPane";
import { TopBar } from "./TopBar";

function makeMsgId(): string {
  return Math.random().toString(36).slice(2, 11);
}

type Props = {
  activeDocId: string | null;
  activeScenarioId?: string | null;
};

export function ChatSurface({ activeDocId, activeScenarioId = null }: Props) {
  useLargeTextClass();
  const router = useRouter();
  const isKiosk = useKioskMode();
  const voiceOnly = useAccessibilityPrefs((s) => s.voiceOnly);
  const simpleLanguage = useAccessibilityPrefs((s) => s.simpleLanguage);

  const citizen = useSessionStore((s) => s.citizen);
  const hydrateCitizen = useSessionStore((s) => s.hydrateCitizen);
  const loadDocument = useSessionStore((s) => s.loadDocument);
  const openScenarioPlan = useSessionStore((s) => s.openScenarioPlan);
  const sendText = useSessionStore((s) => s.sendText);
  const submitWidget = useSessionStore((s) => s.submitWidget);
  const appendMessage = useSessionStore((s) => s.appendMessage);
  const setVoiceStatus = useSessionStore((s) => s.setVoiceStatus);
  const reset = useSessionStore((s) => s.reset);
  const sessionState = useSessionStore((s) => s.session?.state ?? null);
  const hasMessages = useSessionStore((s) => s.messages.length > 0);

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

  // Hydrate the active doc or scenario plan from the URL.
  useEffect(() => {
    if (activeScenarioId) {
      void openScenarioPlan(activeScenarioId).catch(() => {});
      return;
    }
    if (!activeDocId) {
      reset();
      return;
    }
    void loadDocument(activeDocId).catch(() => {});
  }, [activeDocId, activeScenarioId, loadDocument, openScenarioPlan, reset]);

  // Browser back/forward sync.
  useEffect(() => {
    function onPop() {
      const path = window.location.pathname;
      if (path === "/") reset();
      else if (path.startsWith("/r/")) {
        const id = path.slice(3);
        void loadDocument(id);
      } else if (path.startsWith("/p/")) {
        const id = path.slice(3);
        void openScenarioPlan(id);
      }
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [reset, loadDocument, openScenarioPlan]);

  // Mirror voice agent state into the store so the composer mic can react.
  useEffect(() => {
    setVoiceStatus(voice.state);
  }, [voice.state, setVoiceStatus]);

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
    // hears it. Otherwise hit /agent/chat/stream via the store.
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

  function onWidgetSubmit(spec: WidgetSpec, value: string) {
    // Widget submissions go through the dedicated endpoint that resolves
    // the pending widget server-side and calls set_field directly when a
    // target_field is bound. No more LLM guessing.
    void submitWidget(spec, value);
  }

  if (!citizen) {
    return <p className="p-6 text-muted-foreground">Se încarcă...</p>;
  }

  const hasConversation = hasMessages;
  const engaged =
    (sessionState !== null && sessionState !== "exploring") ||
    hasConversation ||
    activeDocId !== null;
  const hideRightPane = voiceOnly;
  // Show the right pane once we are past the welcome state.
  const showRight =
    !hideRightPane &&
    (activeDocId !== null ||
      (sessionState !== null && sessionState !== "exploring"));

  const voiceActive =
    voice.state === "listening" ||
    voice.state === "speaking" ||
    voice.state === "connecting";

  function toggleVoice() {
    if (voiceActive) stopVoice();
    else void startVoice();
  }

  return (
    <div
      className="civic-root"
      data-mode={engaged ? "engaged" : "idle"}
      data-kiosk={isKiosk ? "true" : "false"}
    >
      <a className="skip-link" href="#civic-main">
        Sări la conținut
      </a>
      <h1 className="sr-only">
        CivicAI — asistent digital pentru primărie
      </h1>

      <AnimatedBackground variant={engaged ? "static" : "mesh"} />

      <div className="civic-shell">
        <TopBar voiceOn={voiceActive} onToggleVoice={toggleVoice} />
        <ProfileMenu />
        <main
          id="civic-main"
          className={"civic-main " + (showRight ? "is-engaged" : "is-idle")}
        >
          <section
            className={"civic-left " + (engaged ? "engaged" : "idle")}
            aria-label="Chat cu asistentul CivicAI"
          >
            {engaged ? (
              <ChatStream onWidgetSubmit={onWidgetSubmit} />
            ) : (
              <RightPane />
            )}
            <Composer
              onSendText={onSendText}
              onStartVoice={startVoice}
              onStopVoice={stopVoice}
            />
          </section>

          {showRight ? (
            <aside className="civic-right" aria-label="Previzualizare document">
              <RightPane />
            </aside>
          ) : null}
        </main>
      </div>

      <DocumentsDrawer />
    </div>
  );
}
