import type { Document, Procedure, RightPaneState } from "./types";

export function isFilled(v: unknown): boolean {
  return v !== undefined && v !== null && String(v).length > 0;
}

export function allRequiredFilled(
  procedure: Procedure,
  fields: Record<string, unknown>,
): boolean {
  return (
    procedure.fields.filter((f) => f.required && !isFilled(fields[f.name]))
      .length === 0
  );
}

/**
 * When loading or refetching a document, compute the right-pane substate that
 * best reflects the document's current shape. Pure function — testable.
 */
export function computeInitialRightPaneFrom(
  doc: Document,
  procedure: Procedure,
): RightPaneState {
  if (doc.status === "finalized" && doc.ref_number) {
    return { kind: "done", refNumber: doc.ref_number };
  }
  if (doc.pdf_url) {
    return { kind: "pdf", url: doc.pdf_url };
  }
  if (allRequiredFilled(procedure, doc.fields)) {
    return { kind: "review" };
  }
  const anyFilled = Object.keys(doc.fields).some((k) => isFilled(doc.fields[k]));
  return anyFilled
    ? { kind: "filling" }
    : { kind: "guide", procedureId: doc.procedure_id };
}
