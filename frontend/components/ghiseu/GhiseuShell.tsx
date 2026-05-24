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
import { EditIcon, LogoIcon, RefreshIcon } from "./icons";
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

  // Auto-enter voice mode is DISABLED by design: the kiosk lands on an
  // idle screen with the mic visibly off. User clicks the mic button
  // ("Pornește microfonul") to engage — that routes through
  // ghiseuStore.toggleMute → enterVoiceMode. Keeps the page silent until
  // the user explicitly invites the agent in, which is the right behavior
  // for a kiosk that may be facing a desk where someone is mid-conversation.
  // (enteredRef is unused now; left in place because Effect A's cleanup
  // still resets it as a defensive measure if we ever re-introduce auto-enter.)
  void enteredRef; // silence unused-ref warning

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

  // Demo-mode entry: drop a sample completed Certificat fiscal into the
  // session store and jump straight to the review screen. Lets demo
  // judges see the filled-document UI without driving the whole voice
  // flow. Resets cleanly via the existing "Ia-o de la capăt" button.
  function loadDemoDocument() {
    useSessionStore.setState({
      activeDocId: "demo-doc-0001",
      document: {
        id: "demo-doc-0001",
        citizen_id: "demo-citizen",
        procedure_id: "certificat-fiscal",
        status: "draft",
        fields: {
          nume_complet: "Maria Ionescu",
          cnp: "2851014123456",
          ci_seria: "CJ",
          ci_numar: "458912",
          localitate: "Cluj-Napoca",
          strada: "Avram Iancu",
          numar: "5",
          bloc: "B2",
          scara: "1",
          etaj: "3",
          apartament: "12",
          email: "maria.ionescu@example.com",
          scop: "Credit ipotecar — Banca Transilvania",
          data_cerere: "2026-05-24",
        },
      } as never,
      procedure: {
        id: "certificat-fiscal",
        title: "Certificat fiscal",
        description: "Demo",
        scope: "primarie",
        category: "fiscalitate-locala",
        synonyms: [],
        sample_queries: [],
        acte_necesare: [],
        template: "certificat-fiscal.tex",
        next_steps: [],
        fields: [
          { name: "nume_complet", label: "Nume complet", source: "profile", required: true },
          { name: "cnp", label: "CNP", source: "profile", required: true },
          { name: "ci_seria", label: "Seria CI", source: "id_scan|profile", required: true },
          { name: "ci_numar", label: "Număr CI", source: "id_scan|profile", required: true },
          { name: "localitate", label: "Localitatea de domiciliu", source: "ask", required: true },
          { name: "strada", label: "Strada", source: "ask", required: true },
          { name: "numar", label: "Numărul", source: "ask", required: true },
          { name: "bloc", label: "Blocul", source: "ask", required: false },
          { name: "scara", label: "Scara", source: "ask", required: false },
          { name: "etaj", label: "Etajul", source: "ask", required: false },
          { name: "apartament", label: "Apartamentul", source: "ask", required: false },
          { name: "email", label: "Email", source: "profile", required: false },
          { name: "scop", label: "Scopul", source: "ask", required: true },
          { name: "data_cerere", label: "Data cererii", source: "ask", required: true },
        ],
      } as never,
    });
    setKioskState("review");
  }

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
              onClick={loadDemoDocument}
              aria-label="Document demo"
              title="Document demo"
            >
              <span className="gh-reset-btn-icon" aria-hidden="true">
                <EditIcon size={15} />
              </span>
              <span>Document demo</span>
            </button>
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
