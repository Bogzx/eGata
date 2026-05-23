"use client";

import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/sessionStore";

export function PdfPane() {
  const rightPane = useSessionStore((s) => s.rightPane);
  const transition = useSessionStore((s) => s.transitionRightPane);
  if (rightPane.kind !== "pdf") return null;
  return (
    <div className="flex h-full flex-col p-4">
      <iframe
        src={rightPane.url}
        title="Previzualizare PDF"
        className="flex-1 rounded border bg-white"
      />
      <div className="mt-3 flex justify-end">
        <Button onClick={() => transition({ kind: "delivery" })}>
          Continuă spre trimitere
        </Button>
      </div>
    </div>
  );
}
