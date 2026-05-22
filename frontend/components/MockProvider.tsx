"use client";

import { useEffect, useState } from "react";

export function MockProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(process.env.NEXT_PUBLIC_USE_MOCKS !== "1");

  useEffect(() => {
    if (process.env.NEXT_PUBLIC_USE_MOCKS !== "1") return;
    let cancelled = false;
    void (async () => {
      const { worker } = await import("@/mocks/browser");
      await worker.start({ onUnhandledRequest: "warn", quiet: true });
      if (!cancelled) setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!ready) return null;
  return <>{children}</>;
}
