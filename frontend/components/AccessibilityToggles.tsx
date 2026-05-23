"use client";

import { useEffect } from "react";
import { useAccessibilityPrefs } from "@/lib/accessibilityStore";

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between gap-4 rounded-lg border bg-background p-3.5">
      <span className="flex flex-col">
        <span className="text-base font-medium">{label}</span>
        {hint ? (
          <span className="mt-0.5 text-xs text-muted-foreground">{hint}</span>
        ) : null}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={
          checked
            ? "relative h-8 w-14 shrink-0 rounded-full bg-primary transition"
            : "relative h-8 w-14 shrink-0 rounded-full bg-muted transition"
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
  const {
    largeText,
    highContrast,
    dyslexic,
    hydrate,
    hydrated,
    set,
  } = useAccessibilityPrefs();

  useEffect(() => {
    if (!hydrated) hydrate();
  }, [hydrated, hydrate]);

  return (
    <div className="flex flex-col gap-2.5">
      <Toggle
        label="Mod contrast ridicat"
        checked={highContrast}
        onChange={(v) => set({ highContrast: v })}
      />
      <Toggle
        label="Mod text mare"
        checked={largeText}
        onChange={(v) => set({ largeText: v })}
      />
      <Toggle
        label="Mod dislexic"
        checked={dyslexic}
        onChange={(v) => set({ dyslexic: v })}
      />
    </div>
  );
}
