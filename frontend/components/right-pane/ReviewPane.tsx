"use client";

import { useState } from "react";
import { Check, Pencil } from "lucide-react";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";
import { DocPane } from "./DocPane";

/** The backend's reason for refusing an edit (422 invalid value, 409 already
 * finalized), falling back to a generic line. */
function editErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    const detail = (e.body as { detail?: unknown } | null)?.detail;
    if (detail && typeof detail === "object") {
      const d = detail as { errors?: unknown; message?: unknown };
      if (Array.isArray(d.errors) && typeof d.errors[0] === "string") return d.errors[0];
      if (typeof d.message === "string") return d.message;
    }
    if (typeof detail === "string") return detail;
  }
  return "Nu am putut salva modificarea.";
}

export function ReviewPane() {
  const procedure = useSessionStore((s) => s.procedure);
  const document = useSessionStore((s) => s.document);
  const sendText = useSessionStore((s) => s.sendText);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  if (!procedure || !document) return null;

  async function commitEdit(name: string) {
    const doc = useSessionStore.getState().document;
    if (!doc) return;
    try {
      const updated = await api.patchDocumentFields(doc.id, { [name]: draft });
      useSessionStore.setState({ document: updated });
      setEditing(null);
      setDraft("");
      setEditError(null);
    } catch (e) {
      // Keep the editor open so the citizen can correct the value.
      setEditError(editErrorMessage(e));
    }
  }

  async function requestDelivery(delivery: "save" | "send" | "print") {
    setSubmitting(true);
    try {
      const label =
        delivery === "save" ? "Salvează" : delivery === "send" ? "Trimite-mi pe SMS" : "Printează";
      await sendText(`Te rog generează PDF-ul și finalizează documentul cu ${label}.`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <DocPane
      eyebrow=""
      title={procedure.title}
      titleEmphasis
      actions={
        <>
          <button
            type="button"
            className="civic-btn civic-btn-ghost"
            onClick={() => void requestDelivery("save")}
            disabled={submitting}
          >
            Salvează
          </button>
          <button
            type="button"
            className="civic-btn civic-btn-primary"
            onClick={() => void requestDelivery("send")}
            disabled={submitting}
          >
            {submitting ? "Se finalizează…" : "Trimite pe SMS"}
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <path d="M5 12h14M13 5l7 7-7 7" />
            </svg>
          </button>
        </>
      }
    >
      <div className="doc-paper">
        <div className="doc-header">
          <div className="doc-stamp">
            PRIMĂRIA
            <br />
            CLUJ-NAPOCA
          </div>
          <div className="doc-paper-meta">
            <div>Data: {new Date(document.created_at).toLocaleDateString("ro-RO")}</div>
          </div>
        </div>
        <div className="doc-title">{procedure.title}</div>

        <table className="doc-fields">
          <tbody>
            {procedure.fields.map((f) => {
              const v = document.fields[f.name];
              const filled = v !== undefined && v !== null && String(v).length > 0;
              const isEditing = editing === f.name;
              return (
                <tr key={f.name}>
                  <td className="doc-label">
                    {f.label}
                    {f.required ? <span aria-hidden> *</span> : null}
                  </td>
                  <td className="doc-value">
                    {isEditing ? (
                      <>
                        <div className="flex items-center gap-2">
                          <Input
                            value={draft}
                            onChange={(e) => setDraft(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") void commitEdit(f.name);
                              if (e.key === "Escape") {
                                setEditing(null);
                                setDraft("");
                                setEditError(null);
                              }
                            }}
                            autoFocus
                            className="h-7"
                          />
                          <button
                            type="button"
                            className="icon-btn"
                            onClick={() => void commitEdit(f.name)}
                            aria-label="Salvează"
                          >
                            <Check size={14} />
                          </button>
                        </div>
                        {editError ? (
                          <p role="alert" className="mt-1 text-xs text-red-700">
                            {editError}
                          </p>
                        ) : null}
                      </>
                    ) : (
                      <span className="flex items-center justify-between gap-2">
                        <span>
                          {filled ? String(v) : <span className="doc-empty">…</span>}
                          {(f.source === "roeid" || f.source === "citizen") && filled ? (
                            <span className="doc-auto">✓ auto</span>
                          ) : null}
                        </span>
                        <button
                          type="button"
                          className="icon-btn"
                          onClick={() => {
                            setEditing(f.name);
                            setDraft(filled ? String(v) : "");
                            setEditError(null);
                          }}
                          aria-label={`Editează ${f.label}`}
                        >
                          <Pencil size={14} />
                        </button>
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </DocPane>
  );
}
