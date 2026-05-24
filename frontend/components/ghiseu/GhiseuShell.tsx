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
  const hydrateCitizen = useSessionStore((s) => s.hydrateCitizen);
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

  // Hydrate citizen once. Without this the kiosk sits in idle forever
  // because Effect B is gated on citizen being non-null.
  useEffect(() => {
    if (citizen) return;
    void hydrateCitizen().catch(() => {});
  }, [citizen, hydrateCitizen]);

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
