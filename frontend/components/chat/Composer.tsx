"use client";

import { useId, useState } from "react";
import { useSessionStore } from "@/lib/sessionStore";

type Props = {
  onSendText: (text: string) => Promise<void> | void;
  onStartVoice: () => Promise<void> | void;
  onStopVoice: () => void;
};

export function Composer({ onSendText, onStartVoice, onStopVoice }: Props) {
  const [draft, setDraft] = useState("");
  const sending = useSessionStore((s) => s.sending);
  const voiceStatus = useSessionStore((s) => s.voiceStatus);
  const fieldId = useId();

  const voiceActive =
    voiceStatus === "listening" ||
    voiceStatus === "speaking" ||
    voiceStatus === "connecting";

  async function submit() {
    const t = draft.trim();
    if (!t || sending) return;
    setDraft("");
    await onSendText(t);
  }

  function micClick() {
    if (voiceActive) onStopVoice();
    else void onStartVoice();
  }

  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
      aria-label="Trimite un mesaj asistentului"
    >
      <div className="composer-shell">
        <button
          type="button"
          className="composer-attach"
          aria-label="Atașează fișier"
          tabIndex={-1}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
            focusable="false"
          >
            <path d="M21.4 11.05l-9.19 9.19a5 5 0 01-7.07-7.07l9.19-9.19a3.5 3.5 0 014.95 4.95l-9.2 9.19a2 2 0 11-2.83-2.83l8.49-8.49" />
          </svg>
        </button>

        <label htmlFor={fieldId} className="sr-only">
          Scrie un mesaj pentru asistent
        </label>
        <textarea
          id={fieldId}
          className="composer-input"
          placeholder="Spune-mi ce ai nevoie · sau apasă microfonul"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={1}
          disabled={sending}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit();
            }
          }}
        />

        <button
          type="button"
          className={"composer-mic " + (voiceActive ? "is-on" : "")}
          onClick={micClick}
          aria-pressed={voiceActive}
          aria-label={
            voiceActive ? "Oprește microfonul" : "Pornește microfonul"
          }
          title={voiceActive ? "Oprește microfonul" : "Pornește microfonul"}
        >
          {voiceActive ? (
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
              focusable="false"
            >
              <rect x="6" y="6" width="12" height="12" rx="1.5" />
            </svg>
          ) : (
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
              focusable="false"
            >
              <rect x="9" y="3" width="6" height="12" rx="3" />
              <path d="M5 11a7 7 0 0014 0M12 18v3" />
            </svg>
          )}
        </button>

        <button
          type="submit"
          className="composer-send"
          disabled={sending || draft.trim().length === 0}
          aria-label="Trimite mesajul"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
            focusable="false"
          >
            <path d="M22 2L11 13" />
            <path d="M22 2l-7 20-4-9-9-4z" />
          </svg>
        </button>
      </div>
    </form>
  );
}
