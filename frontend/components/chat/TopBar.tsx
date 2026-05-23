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
      aria-label="Acasă · eGata"
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
        <div className="brand-name">eGata</div>
        <div className="brand-sub">Primărie · România</div>
      </div>
    </button>
  );
}

export function TopBar() {
  const citizen = useSessionStore((s) => s.citizen);
  const openDrawer = useSessionStore((s) => s.openDrawer);
  const toggleProfile = useSessionStore((s) => s.toggleProfileMenu);
  const profileMenuOpen = useSessionStore((s) => s.profileMenuOpen);
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
          onClick={reset}
          aria-label="Începe o conversație nouă"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            focusable="false"
          >
            <path d="M3 12a9 9 0 1 0 3-6.7" />
            <path d="M3 4v5h5" />
          </svg>
          <span className="chip-text">Conversație nouă</span>
        </button>
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
          <span className="chip-text">Documentele mele</span>
          {docCount != null && docCount > 0 ? (
            <span className="chip-badge" aria-hidden="true">
              {docCount}
            </span>
          ) : null}
        </button>

        <button
          type="button"
          className="chip chip-user"
          onClick={toggleProfile}
          aria-haspopup="menu"
          aria-expanded={profileMenuOpen}
          aria-label={`Profil ${profileLabel}`}
          data-profile-toggle
        >
          <span className="avatar" aria-hidden="true">
            {initial}
          </span>
          <span className="chip-text">{profileLabel}</span>
          <svg
            className="chip-caret"
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
