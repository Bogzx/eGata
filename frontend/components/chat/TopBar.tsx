"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useKioskMode } from "@/lib/kioskMode";
import { useSessionStore } from "@/lib/sessionStore";
import type { Document } from "@/lib/types";

function Logo({ onHome }: { onHome: () => void }) {
  return (
    <button
      type="button"
      className="brand"
      onClick={onHome}
      aria-label="Acasă · CivicAI"
    >
      <div className="brand-mark" aria-hidden="true">
        <svg
          viewBox="0 0 24 24"
          width="18"
          height="18"
          fill="none"
          stroke="#EEEEEE"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          focusable="false"
        >
          <path d="M3 11l9-7 9 7" />
          <path d="M5 10v9h14v-9" />
          <path d="M10 19v-5h4v5" />
        </svg>
      </div>
      <div className="brand-text">
        <div className="brand-name">CivicAI</div>
        <div className="brand-sub">Primărie · România</div>
      </div>
    </button>
  );
}

type Props = {
  voiceOn?: boolean;
  onToggleVoice?: () => void;
};

export function TopBar({ voiceOn = false, onToggleVoice }: Props) {
  const citizen = useSessionStore((s) => s.citizen);
  const openDrawer = useSessionStore((s) => s.openDrawer);
  const toggleProfile = useSessionStore((s) => s.toggleProfileMenu);
  const reset = useSessionStore((s) => s.reset);
  const isKiosk = useKioskMode();

  const [docCount, setDocCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listDocuments()
      .then((d: Document[]) => {
        if (!cancelled) setDocCount(d.length);
      })
      .catch(() => {
        if (!cancelled) setDocCount(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const profileLabel = isKiosk
    ? "Accesibilitate"
    : (citizen?.prenume ?? "Profil");
  const initial = citizen?.prenume?.[0]?.toUpperCase() ?? "?";

  return (
    <header className="topbar" role="banner">
      <Logo onHome={reset} />
      <nav className="topbar-actions" aria-label="Bara de instrumente">
        <button
          type="button"
          className="chip"
          onClick={openDrawer}
          aria-label={
            docCount != null
              ? `Deschide Documentele mele, ${docCount} documente`
              : "Documentele mele"
          }
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
            focusable="false"
          >
            <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
          </svg>
          <span>Documentele mele</span>
          {docCount != null && docCount > 0 ? (
            <span className="chip-badge" aria-hidden="true">
              {docCount}
            </span>
          ) : null}
        </button>

        {onToggleVoice ? (
          <button
            type="button"
            className={"chip chip-icon " + (voiceOn ? "is-active" : "")}
            onClick={onToggleVoice}
            aria-pressed={voiceOn}
            aria-label={
              voiceOn
                ? "Oprește asistentul vocal"
                : "Pornește asistentul vocal"
            }
          >
            <svg
              width="14"
              height="14"
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
          </button>
        ) : null}

        <button
          type="button"
          className="chip chip-user"
          onClick={toggleProfile}
          aria-haspopup="menu"
          aria-label={`Profil ${profileLabel}`}
        >
          <span className="avatar" aria-hidden="true">
            {initial}
          </span>
          <span>{profileLabel}</span>
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
            focusable="false"
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
      </nav>
    </header>
  );
}
