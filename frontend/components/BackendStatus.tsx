"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/api";

const REPO_URL = "https://github.com/Bogzx/eGata";

/** True when `${base}/health` answers 2xx within `timeoutMs`. A dead host,
 * a CORS-less error page (what a removed deployment serves) and a timeout
 * all count as down. */
export async function probeBackend(
  base: string,
  timeoutMs = 5000,
  fetchImpl: typeof fetch = fetch,
): Promise<boolean> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetchImpl(`${base}/health`, {
      signal: ctrl.signal,
      cache: "no-store",
    });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/** Down only if a second probe, `retryDelayMs` after a failed first one,
 * fails too: a backend that sleeps when idle or is mid-deploy can miss the
 * first while it starts. */
export async function backendIsDown(
  base: string,
  retryDelayMs = 3000,
  probe: (base: string) => Promise<boolean> = probeBackend,
): Promise<boolean> {
  if (await probe(base)) return false;
  await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
  return !(await probe(base));
}

/** Says so, once, when the backend this build points at cannot be reached.
 * Without it a visitor to a deployment whose API is gone only ever sees
 * "A apărut o eroare" on login. Skipped under MSW mocks, which have no
 * /health. */
export function BackendStatus({ retryDelayMs = 3000 }: { retryDelayMs?: number }) {
  const [down, setDown] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (process.env.NEXT_PUBLIC_USE_MOCKS === "1") return;
    let alive = true;
    void backendIsDown(API_BASE_URL, retryDelayMs).then((isDown) => {
      if (alive) setDown(isDown);
    });
    return () => {
      alive = false;
    };
  }, [retryDelayMs]);

  if (!down || dismissed) return null;
  return (
    <div
      role="alert"
      className="fixed inset-x-0 top-0 z-[90] flex items-start gap-3 bg-amber-100 px-4 py-3 text-sm text-amber-950 shadow-md"
    >
      <p className="flex-1">
        <strong>Serverul demo nu răspunde</strong>, așa că autentificarea și chatul nu
        merg aici. Aplicația completă rulează local cu <code>docker compose up</code>,
        fără chei API: vezi{" "}
        <a className="underline" href={REPO_URL} target="_blank" rel="noreferrer">
          github.com/Bogzx/eGata
        </a>
        .{" "}
        <span lang="en">
          The demo server is offline; the full app runs locally with{" "}
          <code>docker compose up</code>, no API keys needed.
        </span>
      </p>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        aria-label="Închide mesajul"
        className="rounded px-2 text-lg leading-none hover:bg-amber-200"
      >
        ×
      </button>
    </div>
  );
}
