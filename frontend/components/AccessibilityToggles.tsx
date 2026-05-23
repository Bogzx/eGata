"use client";

import { useEffect } from "react";
import { useAccessibilityPrefs } from "@/lib/accessibilityStore";
import { t } from "@/lib/i18n";

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between gap-4 rounded-lg border bg-background p-3.5">
      <span className="text-base font-medium">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={
          checked
            ? "relative h-8 w-14 rounded-full bg-primary transition"
            : "relative h-8 w-14 rounded-full bg-muted transition"
        }
      >
        <span
          aria-hidden
          className={
            checked
              ? "absolute left-0 top-0.5 block h-7 w-7 translate-x-6 rounded-full bg-white shadow transition"
              : "absolute left-0 top-0.5 block h-7 w-7 translate-x-1 rounded-full bg-white shadow transition"
          }
        />
      </button>
    </label>
  );
}

export function AccessibilityToggles() {
  const { voiceOnly, simpleLanguage, largeText, hydrate, hydrated, set } =
    useAccessibilityPrefs();

  useEffect(() => {
    if (!hydrated) hydrate();
  }, [hydrated, hydrate]);

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <Toggle
        label={t("a11y.voice_only")}
        checked={voiceOnly}
        onChange={(v) => set({ voiceOnly: v })}
      />
      <Toggle
        label={t("a11y.simple_language")}
        checked={simpleLanguage}
        onChange={(v) => set({ simpleLanguage: v })}
      />
      <Toggle
        label={t("a11y.large_text")}
        checked={largeText}
        onChange={(v) => set({ largeText: v })}
      />
    </div>
  );
}
