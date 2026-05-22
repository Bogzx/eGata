"use client";

import { useEffect, useState } from "react";

export type KioskInputs = {
  searchParams: string;
  viewportWidth: number;
  hasTouch: boolean;
  idleMs: number;
};

const IDLE_THRESHOLD_MS = 60_000;
const KIOSK_MIN_VIEWPORT_PX = 1000;

export function detectKioskMode(inputs: KioskInputs): boolean {
  const params = new URLSearchParams(inputs.searchParams);
  const mode = params.get("mode");
  if (mode === "kiosk") return true;
  if (mode === "mobile" || mode === "desktop") return false;
  if (!inputs.hasTouch) return false;
  if (inputs.viewportWidth < KIOSK_MIN_VIEWPORT_PX) return false;
  return inputs.idleMs >= IDLE_THRESHOLD_MS;
}

export function useKioskMode(): boolean {
  const [isKiosk, setIsKiosk] = useState(false);

  useEffect(() => {
    let lastActivity = Date.now();

    const sample = () => {
      const next = detectKioskMode({
        searchParams: window.location.search,
        viewportWidth: window.innerWidth,
        hasTouch: window.matchMedia("(pointer: coarse)").matches,
        idleMs: Date.now() - lastActivity,
      });
      setIsKiosk((prev) => (prev === next ? prev : next));
    };

    const reset = () => {
      lastActivity = Date.now();
    };

    sample();
    const interval = window.setInterval(sample, 5000);
    window.addEventListener("pointerdown", reset);
    window.addEventListener("keydown", reset);
    window.addEventListener("touchstart", reset);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("pointerdown", reset);
      window.removeEventListener("keydown", reset);
      window.removeEventListener("touchstart", reset);
    };
  }, []);

  return isKiosk;
}
