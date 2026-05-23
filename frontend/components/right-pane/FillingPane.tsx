"use client";

import { useSessionStore } from "@/lib/sessionStore";
import { DocPane } from "./DocPane";
import { DocPaper, type DocPaperField } from "./DocPaper";

export function FillingPane() {
  const procedure = useSessionStore((s) => s.procedure);
  const document = useSessionStore((s) => s.document);
  const rightPane = useSessionStore((s) => s.rightPane);
  const activeField =
    rightPane.kind === "filling" ? rightPane.activeField : undefined;

  if (!procedure || !document) return null;

  const fields: DocPaperField[] = procedure.fields.map((f) => {
    const v = document.fields[f.name];
    const filled = v !== undefined && v !== null && String(v).length > 0;
    return {
      label: f.label + (activeField === f.name ? "  ←" : ""),
      value: filled ? String(v) : "",
      auto: f.source === "roeid" || f.source === "citizen",
    };
  });

  const createdAt = new Date(document.created_at).toLocaleDateString("ro-RO");

  return (
    <DocPane
      eyebrow="Cerere în lucru"
      title={procedure.title}
      refNumber={document.ref_number ?? document.id.slice(0, 8).toUpperCase()}
    >
      <DocPaper
        title={procedure.title}
        refNumber={document.ref_number ?? undefined}
        date={createdAt}
        fields={fields}
        showSignatures
      />
    </DocPane>
  );
}
