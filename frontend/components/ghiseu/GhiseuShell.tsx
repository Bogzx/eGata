"use client";

import { useAccessibilityClasses } from "@/lib/accessibilityStore";
import { useGhiseuStore } from "@/lib/ghiseuStore";
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
