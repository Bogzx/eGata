"use client";

import { useEffect, useState } from "react";
import type { Variants } from "framer-motion";

export function variantsWithReducedMotion<T extends Variants>(
  variants: T,
  reducedMotion: boolean,
): T {
  if (!reducedMotion) return variants;
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(variants)) {
    if (value && typeof value === "object") {
      out[key] = { ...(value as object), transition: { duration: 0 } };
    } else {
      out[key] = value;
    }
  }
  return out as T;
}

export const reminderListContainer: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.05 },
  },
};

export const reminderItem: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: "easeOut" },
  },
};

export const pageTransition: Variants = {
  initial: { opacity: 0, y: 8 },
  enter: { opacity: 1, y: 0, transition: { duration: 0.25 } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.15 } },
};

export const fieldHighlightPulse: Variants = {
  pulse: {
    boxShadow: [
      "0 0 0 0 rgba(59, 130, 246, 0)",
      "0 0 0 6px rgba(59, 130, 246, 0.35)",
      "0 0 0 0 rgba(59, 130, 246, 0)",
    ],
    transition: { duration: 0.9, times: [0, 0.4, 1] },
  },
};

export const modeSwitch: Variants = {
  hidden: { opacity: 0, x: -8 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.2 } },
  exit: { opacity: 0, x: 8, transition: { duration: 0.15 } },
};

export const messageFadeIn: Variants = {
  hidden: { opacity: 0, y: 6 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.2 } },
};

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}
