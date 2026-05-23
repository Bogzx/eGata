"use client";

import { FormPreview } from "@/components/FormPreview";
import { useSessionStore } from "@/lib/sessionStore";

export function FillingPane() {
  const procedure = useSessionStore((s) => s.procedure);
  const document = useSessionStore((s) => s.document);
  const rightPane = useSessionStore((s) => s.rightPane);
  const activeField =
    rightPane.kind === "filling" ? rightPane.activeField : undefined;

  if (!procedure || !document) return null;

  return (
    <div className="h-full overflow-auto p-4">
      <FormPreview
        procedure={procedure}
        values={document.fields}
        activeField={activeField}
      />
    </div>
  );
}
