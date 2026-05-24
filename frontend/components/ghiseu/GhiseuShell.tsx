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
  const setKioskState = useGhiseuStore((s) => s.setState);

  // enteredRef gates the auto-enter so it only fires once per mount. Reset
  // in A's cleanup so React StrictMode's synthetic remount can re-enter
  // after the bridge gets torn down between setup-cleanup-setup cycles.
  // NOT reset on catch — failure means user must click mic to retry,
  // otherwise we'd loop on persistent failures.
  const enteredRef = useRef(false);

  // Effect A: attach bridge + flip kioskMode on mount; reverse on unmount.
  // Empty deps: `voice` is a new object each render (the hook returns a fresh
  // wrapper) so including it would re-attach every render and infinite-loop
  // when the cleanup stop() triggers another state change → render → cleanup.
  // The methods on `voice` are stable (useCallback'd inside the hook), so
  // capturing the first render's `voice` in the closure is correct.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    setKioskMode(true);
    const cleanup = attachVoiceBridge(voice);
    return () => {
      cleanup();
      setKioskMode(false);
      enteredRef.current = false;
    };
  }, []);

  // Hydrate citizen once. Without this the kiosk sits in idle forever
  // because Effect B is gated on citizen being non-null.
  useEffect(() => {
    if (citizen) return;
    void hydrateCitizen().catch(() => {});
  }, [citizen, hydrateCitizen]);

  // Effect B: auto-enter voice mode once a citizen is hydrated. Guarded
  // BOTH by enteredRef (per-mount one-shot) AND by voice.wsReady/state
  // (singleton bridge — never double-start). voice.state in deps so
  // post-handshake re-render satisfies the guard.
  useEffect(() => {
    if (!citizen || enteredRef.current) return;
    if (voice.wsReady || voice.state === "connecting") return;
    enteredRef.current = true;
    void enterVoiceMode().catch(() => {
      // already logged + state set on the store; do NOT reset enteredRef
    });
  }, [citizen, voice.wsReady, voice.state, enterVoiceMode]);

  // Effect C: mirror voice.micOn into store.muted so the UI's ripple +
  // mic button label stay in sync with the actual hardware state.
  useEffect(() => {
    setMuted(!voice.micOn);
  }, [voice.micOn, setMuted]);

  // Effect E: mirror sessionStore.session.state -> ghiseu state for
  // "reviewing" / "delivered" transitions. The backend flips session.state
  // when the agent fills the last required field (-> reviewing) or after
  // a successful deliver (-> delivered). Skip when ghiseu state is already
  // in a user-facing error/permission state.
  const sessionStateValue = useSessionStore((s) => s.session?.state ?? null);
  useEffect(() => {
    if (sessionStateValue !== "reviewing" && sessionStateValue !== "delivered") {
      return;
    }
    const ghiseuState = useGhiseuStore.getState().state;
    if (ghiseuState === "error" || ghiseuState === "mic-denied") return;
    if (sessionStateValue === "reviewing" && ghiseuState !== "review") {
      setKioskState("review");
    } else if (sessionStateValue === "delivered" && ghiseuState !== "done") {
      setKioskState("done");
    }
  }, [sessionStateValue, setKioskState]);

  // Effect D: mirror voice.state -> ghiseu state for "speaking" detection.
  // The bridge's voice.state goes to "speaking" on the first onAgentDelta;
  // some backend configs only emit audio (no transcript deltas), in which
  // case appendAgentPartial never fires and our state machine stays at
  // "listening". This mirror is a fallback so the Întrerupe button still
  // activates when the agent is actively talking.
  useEffect(() => {
    if (voice.state !== "speaking" && voice.state !== "listening") return;
    // Don't overwrite UI-flow states (review/export/done/error/mic-denied)
    // that are set by user clicks, not by voice transitions.
    const ghiseuState = useGhiseuStore.getState().state;
    if (
      ghiseuState === "review" ||
      ghiseuState === "export" ||
      ghiseuState === "done" ||
      ghiseuState === "error" ||
      ghiseuState === "mic-denied"
    ) {
      return;
    }
    if (voice.state === "speaking") setKioskState("speaking");
    if (voice.state === "listening" && ghiseuState === "speaking")
      setKioskState("listening");
  }, [voice.state, setKioskState]);

  let content;
  if (state === "review") {
    content = <DocumentReview onConfirm={confirmDoc} onAmend={amendDoc} />;
  } else if (state === "export" || state === "submitting") {
    content = (
      <ExportOptions
        onPick={pickExport}
        submitting={state === "submitting"}
        submittingMethod={state === "submitting" ? exportMethod : null}
      />
    );
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
