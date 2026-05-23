"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export function DemoResetButton() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  if (process.env.NEXT_PUBLIC_DEMO_MODE !== "1") return null;

  async function reset() {
    if (busy) return;
    setBusy(true);
    setMsg("Se resetează…");
    try {
      await api.resetDemo();
      setMsg("Reset OK — se reîncarcă");
      setTimeout(() => window.location.reload(), 600);
    } catch (e) {
      const detail = e instanceof Error ? e.message : "necunoscută";
      setMsg(`Eroare: ${detail}`);
      setBusy(false);
    }
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2">
      <button
        type="button"
        onClick={reset}
        disabled={busy}
        aria-label="Resetează datele demo"
        className="rounded-full bg-yellow-400 px-4 py-2 text-sm font-medium text-black shadow-lg transition hover:bg-yellow-300 focus:outline-none focus:ring-2 focus:ring-yellow-600 disabled:opacity-60"
      >
        Reset demo
      </button>
      {msg ? (
        <p className="rounded bg-black/80 px-3 py-1 text-xs text-white">{msg}</p>
      ) : null}
    </div>
  );
}
