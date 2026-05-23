"use client";

import { useEffect, useState, FormEvent } from "react";

const STORAGE_KEY = "civicai.access";
// Read from env so the password isn't hardcoded in the shipped JS bundle.
// When unset, the gate is bypassed entirely — keeps local dev frictionless.
// Note: NEXT_PUBLIC_* envs end up in the bundle anyway; this isn't real
// security, just an obscurity layer for the demo URL. Real auth is the
// JWT issued by /auth/otp.
const PASSWORD =
  (typeof process !== "undefined" &&
    process.env.NEXT_PUBLIC_ACCESS_PASSWORD) ||
  "";

export function AccessGate({ children }: { children: React.ReactNode }) {
  const [unlocked, setUnlocked] = useState<boolean | null>(null);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    // No password configured? Skip the gate.
    if (!PASSWORD) {
      setUnlocked(true);
      return;
    }
    setUnlocked(window.localStorage.getItem(STORAGE_KEY) === "1");
  }, []);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (input === PASSWORD) {
      window.localStorage.setItem(STORAGE_KEY, "1");
      setUnlocked(true);
      setError(null);
      setInput("");
    } else {
      setError("Parolă incorectă");
    }
  }

  if (unlocked === null) return null;
  if (unlocked) return <>{children}</>;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="access-gate-title"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
    >
      <div className="w-full max-w-sm rounded-2xl border bg-card p-6 shadow-xl">
        <h2 id="access-gate-title" className="text-lg font-semibold">
          Acces protejat
        </h2>
        <p className="mt-1 mb-4 text-sm text-muted-foreground">
          Introdu parola pentru a continua.
        </p>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="password"
            autoFocus
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              if (error) setError(null);
            }}
            aria-label="Parolă"
            aria-invalid={error ? "true" : "false"}
            placeholder="Parolă"
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          {error ? (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-primary"
          >
            Intră
          </button>
        </form>
      </div>
    </div>
  );
}
