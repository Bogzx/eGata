"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  useAccessibilityPrefs,
  useLargeTextClass,
} from "@/lib/accessibilityStore";
import type { AgentToolCall } from "@/lib/gemini-live";
import { useKioskMode } from "@/lib/kioskMode";
import { getSession } from "@/lib/session";
import { useSessionStore } from "@/lib/sessionStore";
import type { WidgetSpec } from "@/lib/types";
import {
  VoiceAgentMicDeniedError,
  useVoiceAgent,
} from "@/lib/useVoiceAgent";
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

function deriveWidgetsFromVoice(toolCalls: AgentToolCall[]): WidgetSpec[] {
  const out: WidgetSpec[] = [];
  for (const tc of toolCalls) {
    if (tc.name !== "propose_widget") continue;
    const a = tc.args;
    const type = a.type as WidgetSpec["type"] | undefined;
    const question = (a.question as string | undefined) ?? "";
    // widgetId is UI-only — the model never sees one, so always generate.
    const widgetId = Math.random().toString(36).slice(2);
    if (type === "choice") {
      out.push({
        type: "choice",
        question,
        options: (a.options as string[] | undefined) ?? [],
        targetField: (a.target_field as string | undefined) ?? "",
        widgetId,
      });
    } else if (type === "confirm") {
      out.push({
        type: "confirm",
        question,
        onConfirmTool: a.on_confirm_tool as string | undefined,
        widgetId,
      });
    } else if (type === "date") {
      out.push({
        type: "date",
        question,
        targetField: (a.target_field as string | undefined) ?? "",
        widgetId,
      });
    }
  }
  return out;
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
  const appendMessage = useSessionStore((s) => s.appendMessage);
  const upsertPendingUser = useSessionStore((s) => s.upsertPendingUser);
  const upsertPendingAgent = useSessionStore((s) => s.upsertPendingAgent);
  const finalizePendingUser = useSessionStore((s) => s.finalizePendingUser);
  const finalizePendingAgent = useSessionStore((s) => s.finalizePendingAgent);
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

  // Per-delta callbacks → live-updating pending bubbles.
  function handleVoiceUserDelta(text: string) {
    upsertPendingUser(text, "voice");
  }

  function handleVoiceAgentDelta(text: string) {
    upsertPendingAgent(text);
  }

  // Finalized turn callbacks — replace pending with a permanent message.
  function handleVoiceUserMessage(text: string) {
    finalizePendingUser();
    appendMessage({
      id: makeMsgId(),
      role: "user",
      text,
      via: "voice",
    });
  }

  function handleVoiceAgentMessage(text: string, toolCalls: AgentToolCall[]) {
    const widgets = deriveWidgetsFromVoice(toolCalls);
    finalizePendingAgent();
    appendMessage({
      id: makeMsgId(),
      role: "agent",
      text,
      widgets: widgets.length ? widgets : undefined,
    });
  }

  // Auto-start voice for voice_only users once citizen is hydrated.
  useEffect(() => {
    if (!voiceOnly || !citizen || voiceStartedRef.current) return;
    voiceStartedRef.current = true;
    void voice
      .start({
        documentId: activeDocId ?? undefined,
        preferences: { simple_language: simpleLanguage, voice_only: voiceOnly },
        onUserDelta: handleVoiceUserDelta,
        onAgentDelta: handleVoiceAgentDelta,
        onUserMessage: handleVoiceUserMessage,
        onAgentMessage: handleVoiceAgentMessage,
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
    // We intentionally omit handleVoice* handlers from deps — they close over
    // appendMessage which is stable via zustand, and we only want one start.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceOnly, citizen, activeDocId, simpleLanguage, voice]);

  async function startVoice() {
    if (!citizen) return;
    try {
      await voice.start({
        documentId: useSessionStore.getState().activeDocId ?? undefined,
        preferences: { simple_language: simpleLanguage, voice_only: voiceOnly },
        onUserDelta: handleVoiceUserDelta,
        onAgentDelta: handleVoiceAgentDelta,
        onUserMessage: handleVoiceUserMessage,
        onAgentMessage: handleVoiceAgentMessage,
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
    // hears it; otherwise hit /agent/chat/stream. Either way the user bubble
    // is appended (voice path appends here, text path via store.sendText).
    if (voice.state === "listening" || voice.state === "speaking") {
      // Discard any stale voice partial — the user has switched to typing.
      finalizePendingUser();
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
  const showRight = engaged && !hideRightPane;

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
