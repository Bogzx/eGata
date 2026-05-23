"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  useAccessibilityPrefs,
  useLargeTextClass,
} from "@/lib/accessibilityStore";
import { useKioskMode } from "@/lib/kioskMode";
import { getSession } from "@/lib/session";
import { setNavigate, useSessionStore } from "@/lib/sessionStore";
import type { WidgetSpec } from "@/lib/types";
import { VoiceAgentMicDeniedError } from "@/lib/useVoiceAgentBridge";
import { useVoiceContext } from "@/lib/voiceContext";
import { AnimatedBackground } from "./AnimatedBackground";
import { ChatStream } from "./ChatStream";
import { Composer } from "./Composer";
import { DocumentsDrawer } from "./DocumentsDrawer";
import { MobileViewToggle, type MobileView } from "./MobileViewToggle";
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
  const setMicOn = useSessionStore((s) => s.setMicOn);
  const reset = useSessionStore((s) => s.reset);
  const sessionState = useSessionStore((s) => s.session?.state ?? null);
  const hasMessages = useSessionStore((s) => s.messages.length > 0);

  const voice = useVoiceContext();
  const voiceStartedRef = useRef(false);

  const [mobileView, setMobileView] = useState<MobileView>("chat");
  const [docHinted, setDocHinted] = useState(false);

  // Auth gate.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!getSession()) router.replace("/login");
  }, [router]);

  // Wire store-driven navigation to Next.js router so route-tree state
  // stays in sync after startProcedure / loadDocument / reset.
  useEffect(() => {
    setNavigate((path) => router.push(path));
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

  // Mirror mic state into the store — Composer's mic button visual is
  // driven by this, not voiceStatus, because text-only sessions now also
  // hold the WS open (voiceStatus = "listening") without the mic on.
  useEffect(() => {
    setMicOn(voice.micOn);
  }, [voice.micOn, setMicOn]);

  // Helper: open WS + engage mic atomically. Used both by the explicit mic
  // toggle and by the voice_only auto-start. If the mic is denied after the
  // WS opens, tear the WS back down so we don't leave a dangling session.
  async function enterVoiceMode(): Promise<void> {
    // If the WS is already up (e.g. user previously had voice on and the
    // VoiceProvider kept it alive across navigation), skip start() —
    // calling start twice would race two WS connections on the same
    // conv_id and deadlock on session_lock.
    if (!voice.wsReady) {
      await voice.start({
        documentId: useSessionStore.getState().activeDocId ?? undefined,
        preferences: { simple_language: simpleLanguage, voice_only: voiceOnly },
      });
    }
    try {
      await voice.enableMic();
    } catch (err) {
      // Tear down the WS so text mode (SSE) can acquire session_lock again.
      voice.stop();
      throw err;
    }
  }

  // Auto-start voice for voice_only users once citizen is hydrated.
  useEffect(() => {
    if (!voiceOnly || !citizen || voiceStartedRef.current) return;
    voiceStartedRef.current = true;
    void enterVoiceMode().catch((err) => {
      if (err instanceof VoiceAgentMicDeniedError) {
        appendMessage({
          id: makeMsgId(),
          role: "system",
          text: "Microfonul nu este permis. Folosește textul.",
        });
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceOnly, citizen, activeDocId, simpleLanguage]);

  // Briefly pulse the "Document" segment of the mobile toggle when new
  // doc-side content becomes available while the user is on the Chat view.
  useEffect(() => {
    if (mobileView !== "chat") return;
    if (sessionState !== "filling" && sessionState !== "reviewing") return;
    setDocHinted(true);
    const t = window.setTimeout(() => setDocHinted(false), 1500);
    return () => window.clearTimeout(t);
  }, [mobileView, sessionState]);

  async function startVoice() {
    if (!citizen) return;
    try {
      await enterVoiceMode();
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
    // Full teardown: closes WS + recorder + player so the session_lock is
    // released and SSE text turns can flow again. Voice and text stay on
    // their own transports.
    voice.stop();
  }

  async function onSendText(t: string) {
    // Text stays on SSE (/agent/chat/stream) — no WS is opened just for
    // typing. The only time text goes through the WS bridge is when voice
    // is already active (otherwise SSE would deadlock on session_lock).
    if (voice.micOn) {
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

  async function onWidgetSubmit(spec: WidgetSpec, value: string) {
    // P0-2 fix: when voice is live, route the widget through the WS bridge
    // so set_field's result is injected into the active Gemini Live
    // session's context (the HTTP /widget-result path can't reach Live's
    // in-session history). When voice is off, the HTTP endpoint is the
    // right path — it bypasses Gemini entirely for the trivial case.
    if (voice.micOn) {
      try {
        await voice.submitWidget(spec.widgetId, value);
        return;
      } catch (err) {
        console.warn(
          "[civicai] WS widget submit failed; falling back to HTTP",
          err,
        );
      }
    }
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

  return (
    <div
      className="civic-root"
      data-mode={engaged ? "engaged" : "idle"}
      data-kiosk={isKiosk ? "true" : "false"}
      data-mobile-view={mobileView}
    >
      <a className="skip-link" href="#civic-main">
        Sări la conținut
      </a>
      <h1 className="sr-only">
        CivicAI — asistent digital pentru primărie
      </h1>

      <AnimatedBackground variant={engaged ? "static" : "mesh"} />

      <div className="civic-shell">
        <TopBar />
        {showRight ? (
          <MobileViewToggle
            value={mobileView}
            onChange={setMobileView}
            hinted={docHinted}
          />
        ) : null}
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
