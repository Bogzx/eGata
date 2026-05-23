"use client";

import type { GhiseuState } from "@/lib/ghiseuStore";
import { MicIcon, MicOffIcon, StopIcon } from "./icons";

type Props = {
  state: GhiseuState;
  muted: boolean;
  onToggleMute: () => void;
  onInterrupt: () => void;
  onBackToTalk: () => void;
};

export function ControlsDock({
  state,
  muted,
  onToggleMute,
  onInterrupt,
  onBackToTalk,
}: Props) {
  if (state === "review") {
    return (
      <div className="gh-controls">
        <button
          type="button"
          className="gh-ctrl"
          data-variant="ghost"
          onClick={onBackToTalk}
        >
          <span className="gh-ctrl-icon">
            <MicIcon size={18} />
          </span>
          Vorbește din nou
        </button>
      </div>
    );
  }

  if (state === "export") {
    return (
      <div className="gh-controls">
        <button
          type="button"
          className="gh-ctrl"
          data-variant="ghost"
          onClick={onBackToTalk}
        >
          <span className="gh-ctrl-icon">
            <MicIcon size={18} />
          </span>
          Întreabă altceva
        </button>
      </div>
    );
  }

  if (state === "done" || state === "error" || state === "mic-denied") {
    return null;
  }

  const emitting = state === "listening" && !muted;
  const canInterrupt = state === "speaking";

  return (
    <div className="gh-controls">
      <button
        type="button"
        className="gh-ctrl"
        data-variant="mic"
        data-on={!muted ? "true" : "false"}
        data-emit={emitting ? "true" : "false"}
        onClick={onToggleMute}
        aria-pressed={!muted}
        title={muted ? "Pornește microfonul" : "Oprește microfonul"}
      >
        <span className="gh-ctrl-icon">
          {muted ? <MicOffIcon size={20} /> : <MicIcon size={20} />}
        </span>
        {muted ? "Pornește microfonul" : "Oprește microfonul"}
      </button>

      <button
        type="button"
        className="gh-ctrl"
        data-variant="end"
        onClick={onInterrupt}
        disabled={!canInterrupt}
        title="Întrerupe agentul"
      >
        <span className="gh-ctrl-icon">
          <StopIcon size={16} />
        </span>
        Întrerupe
      </button>
    </div>
  );
}
