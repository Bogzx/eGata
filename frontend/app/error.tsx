"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <html lang="ro">
      <body className="flex min-h-screen items-center justify-center bg-background">
        <main
          role="alert"
          className="mx-auto max-w-md rounded-2xl border bg-card p-8 text-center shadow-lg"
        >
          <h1 className="mb-3 text-2xl font-semibold">A apărut o eroare</h1>
          <p className="mb-6 text-muted-foreground">
            Ne pare rău — ceva nu a mers cum trebuia. Echipa eGata a fost
            notificată automat.
          </p>
          <button
            type="button"
            onClick={() => reset()}
            className="rounded-xl bg-primary px-6 py-3 font-medium text-primary-foreground transition hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-primary"
          >
            Reîncearcă
          </button>
          {error.digest ? (
            <p className="mt-6 text-xs text-muted-foreground">Cod: {error.digest}</p>
          ) : null}
        </main>
      </body>
    </html>
  );
}
