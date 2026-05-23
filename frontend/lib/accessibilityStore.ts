"use client";

import { useEffect } from "react";
import { create } from "zustand";
import { api } from "./api";
import { getSession } from "./session";

const KEY = "egata.a11y";

type Persisted = {
  voice_only: boolean;
  simple_language: boolean;
  large_text: boolean;
  high_contrast: boolean;
  dyslexic: boolean;
};

type State = {
  // Backend-functional prefs (kept so voice + simple-language flows still work
  // when toggled via persona seed or backend; no longer surfaced in the UI).
  voiceOnly: boolean;
  simpleLanguage: boolean;
  // User-facing accessibility toggles, surfaced in ProfileMenu.
  largeText: boolean;
  highContrast: boolean;
  dyslexic: boolean;
  hydrated: boolean;
  set: (patch: Partial<Omit<State, "set" | "hydrated">>) => void;
  hydrate: () => void;
};

function persist(state: {
  voiceOnly: boolean;
  simpleLanguage: boolean;
  largeText: boolean;
  highContrast: boolean;
  dyslexic: boolean;
}) {
  if (typeof window === "undefined") return;
  const payload: Persisted = {
    voice_only: state.voiceOnly,
    simple_language: state.simpleLanguage,
    large_text: state.largeText,
    high_contrast: state.highContrast,
    dyslexic: state.dyslexic,
  };
  window.localStorage.setItem(KEY, JSON.stringify(payload));
}

function load(): Partial<Persisted> {
  if (typeof window === "undefined") return {};
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Partial<Persisted>;
  } catch {
    return {};
  }
}

export const useAccessibilityPrefs = create<State>((set, get) => ({
  voiceOnly: false,
  simpleLanguage: false,
  largeText: false,
  highContrast: false,
  dyslexic: false,
  hydrated: false,
  set: (patch) => {
    set(patch);
    const s = get();
    persist({
      voiceOnly: patch.voiceOnly ?? s.voiceOnly,
      simpleLanguage: patch.simpleLanguage ?? s.simpleLanguage,
      largeText: patch.largeText ?? s.largeText,
      highContrast: patch.highContrast ?? s.highContrast,
      dyslexic: patch.dyslexic ?? s.dyslexic,
    });
    // Backend only knows about voice_only, simple_language, large_text.
    // The new local-only prefs (high_contrast, dyslexic) are not synced.
    if (typeof window !== "undefined" && getSession()) {
      const accessibility: Record<string, boolean> = {};
      if (patch.voiceOnly !== undefined) accessibility.voice_only = patch.voiceOnly;
      if (patch.simpleLanguage !== undefined)
        accessibility.simple_language = patch.simpleLanguage;
      if (patch.largeText !== undefined) accessibility.large_text = patch.largeText;
      if (Object.keys(accessibility).length > 0) {
        void api.patchCitizenAttributes({ accessibility }).catch(() => {
          // best-effort sync; localStorage remains source of truth on failure
        });
      }
    }
  },
  hydrate: () => {
    const loaded = load();
    set({
      voiceOnly: loaded.voice_only ?? false,
      simpleLanguage: loaded.simple_language ?? false,
      largeText: loaded.large_text ?? false,
      highContrast: loaded.high_contrast ?? false,
      dyslexic: loaded.dyslexic ?? false,
      hydrated: true,
    });
  },
}));

/**
 * Reflect all user-facing accessibility prefs as classes on <html> so global
 * CSS can react. Hydrates the store on first mount.
 */
export function useAccessibilityClasses(): void {
  const largeText = useAccessibilityPrefs((s) => s.largeText);
  const highContrast = useAccessibilityPrefs((s) => s.highContrast);
  const dyslexic = useAccessibilityPrefs((s) => s.dyslexic);
  const hydrate = useAccessibilityPrefs((s) => s.hydrate);
  const hydrated = useAccessibilityPrefs((s) => s.hydrated);

  useEffect(() => {
    if (!hydrated) hydrate();
  }, [hydrated, hydrate]);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const el = document.documentElement;
    el.classList.toggle("large-text", largeText);
    el.classList.toggle("high-contrast", highContrast);
    el.classList.toggle("dyslexic", dyslexic);
  }, [largeText, highContrast, dyslexic]);
}

/** Backwards-compatible alias used by ChatSurface / KioskShell. */
export const useLargeTextClass = useAccessibilityClasses;
