"use client";

import { useEffect, useRef, useState } from "react";
import { useAccessibilityPrefs } from "@/lib/accessibilityStore";

type ToggleProps = {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (next: boolean) => void;
};

function AccessibilityToggle({ label, hint, checked, onChange }: ToggleProps) {
  return (
    <label className="gh-pm-row">
      <span className="gh-pm-row-text">
        <span className="gh-pm-row-label">{label}</span>
        <span className="gh-pm-row-hint">{hint}</span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={(e) => {
          e.preventDefault();
          onChange(!checked);
        }}
        className={"gh-pm-switch " + (checked ? "is-on" : "")}
      >
        <span className="gh-pm-switch-knob" aria-hidden="true" />
      </button>
    </label>
  );
}

export function GhiseuProfileMenu() {
  const [open, setOpen] = useState(false);
  const largeText = useAccessibilityPrefs((s) => s.largeText);
  const highContrast = useAccessibilityPrefs((s) => s.highContrast);
  const dyslexic = useAccessibilityPrefs((s) => s.dyslexic);
  const setPrefs = useAccessibilityPrefs((s) => s.set);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const btnRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      const target = e.target as Node;
      if (menuRef.current?.contains(target)) return;
      if (btnRef.current?.contains(target)) return;
      setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="gh-pm">
      <button
        ref={btnRef}
        type="button"
        className="gh-pm-chip"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="gh-pm-avatar" aria-hidden="true">
          A
        </span>
        <span className="gh-pm-chip-label">Accesibilitate</span>
        <svg
          className="gh-pm-caret"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open ? (
        <div ref={menuRef} role="menu" className="gh-pm-panel">
          <p className="gh-pm-eyebrow">Accesibilitate</p>
          <div className="gh-pm-list">
            <AccessibilityToggle
              label="Mod contrast ridicat"
              hint="Text negru, fundal alb, contururi groase."
              checked={highContrast}
              onChange={(v) => setPrefs({ highContrast: v })}
            />
            <AccessibilityToggle
              label="Mod text mare"
              hint="Mărește textul corpului paginii."
              checked={largeText}
              onChange={(v) => setPrefs({ largeText: v })}
            />
            <AccessibilityToggle
              label="Mod dislexic"
              hint="Spațiere mai mare între litere și rânduri."
              checked={dyslexic}
              onChange={(v) => setPrefs({ dyslexic: v })}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
