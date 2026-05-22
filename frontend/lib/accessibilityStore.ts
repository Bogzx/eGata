"use client";

import { useEffect } from "react";
import { create } from "zustand";

const KEY = "civicai.a11y";

type Persisted = {
  voice_only: boolean;
  simple_language: boolean;
  large_text: boolean;
};

type State = {
  voiceOnly: boolean;
  simpleLanguage: boolean;
  largeText: boolean;
  hydrated: boolean;
  set: (patch: Partial<Omit<State, "set" | "hydrated">>) => void;
  hydrate: () => void;
};

function persist(state: { voiceOnly: boolean; simpleLanguage: boolean; largeText: boolean }) {
  if (typeof window === "undefined") return;
  const payload: Persisted = {
    voice_only: state.voiceOnly,
    simple_language: state.simpleLanguage,
    large_text: state.largeText,
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
  hydrated: false,
  set: (patch) => {
    set(patch);
    const s = get();
    persist({
      voiceOnly: patch.voiceOnly ?? s.voiceOnly,
      simpleLanguage: patch.simpleLanguage ?? s.simpleLanguage,
      largeText: patch.largeText ?? s.largeText,
    });
  },
  hydrate: () => {
    const loaded = load();
    set({
      voiceOnly: loaded.voice_only ?? false,
      simpleLanguage: loaded.simple_language ?? false,
      largeText: loaded.large_text ?? false,
      hydrated: true,
    });
  },
}));

export function useLargeTextClass(): void {
  const largeText = useAccessibilityPrefs((s) => s.largeText);
  const hydrate = useAccessibilityPrefs((s) => s.hydrate);
  const hydrated = useAccessibilityPrefs((s) => s.hydrated);

  useEffect(() => {
    if (!hydrated) hydrate();
  }, [hydrated, hydrate]);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.classList.toggle("large-text", largeText);
  }, [largeText]);
}
