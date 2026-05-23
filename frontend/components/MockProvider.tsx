"use client";

import { useEffect, useState } from "react";

let mswStartPromise: Promise<unknown> | null = null;

export function MockProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(process.env.NEXT_PUBLIC_USE_MOCKS !== "1");

  useEffect(() => {
    if (process.env.NEXT_PUBLIC_USE_MOCKS !== "1") return;
    let cancelled = false;
    if (!mswStartPromise) {
      mswStartPromise = (async () => {
        const { worker } = await import("@/mocks/browser");
        await worker.start({ onUnhandledRequest: "warn", quiet: true });
      })();
    }
    void mswStartPromise.then(() => {
      if (!cancelled) setReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!ready) return null;
  return <>{children}</>;
}
