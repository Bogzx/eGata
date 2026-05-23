"use client";

import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/sessionStore";

export function DonePane() {
  const document = useSessionStore((s) => s.document);
  const reset = useSessionStore((s) => s.reset);
  const refNumber =
    document?.ref_number ??
    (document ? document.id.slice(0, 8).toUpperCase() : "—");
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 p-10 text-center">
      <CheckCircle2 className="text-green-600" size={48} aria-hidden />
      <h2 className="text-2xl font-semibold">Gata.</h2>
      <p className="text-sm">
        Numărul tău de referință:{" "}
        <strong className="font-mono">{refNumber}</strong>
      </p>
      <Button onClick={() => reset()}>Conversație nouă</Button>
    </div>
  );
}
