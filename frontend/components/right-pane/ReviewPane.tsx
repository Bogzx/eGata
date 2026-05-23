"use client";

import { useState } from "react";
import { Check, Pencil } from "lucide-react";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";
import { DocPane } from "./DocPane";

export function ReviewPane() {
  const procedure = useSessionStore((s) => s.procedure);
  const document = useSessionStore((s) => s.document);
  const transition = useSessionStore((s) => s.transitionRightPane);
  const sendText = useSessionStore((s) => s.sendText);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [generating, setGenerating] = useState(false);

  if (!procedure || !document) return null;

  async function commitEdit(name: string) {
    const doc = useSessionStore.getState().document;
    if (!doc) return;
    const updated = await api.patchDocumentFields(doc.id, { [name]: draft });
    useSessionStore.setState({ document: updated });
    setEditing(null);
    setDraft("");
  }

  async function generatePdf() {
    const doc = useSessionStore.getState().document;
    if (!doc) return;
    setGenerating(true);
    try {
      const r = await api.generatePdf(doc.id);
      const fresh = await api.getDocument(doc.id);
      useSessionStore.setState({ document: fresh });
      transition({ kind: "pdf", url: fresh.pdf_url ?? r.pdf_url });
      void sendText("Am generat PDF-ul, vezi în dreapta.");
    } finally {
      setGenerating(false);
    }
  }

  const refNumber =
    document.ref_number ?? document.id.slice(0, 8).toUpperCase();

  return (
    <DocPane
      eyebrow="Verifică datele"
      title={procedure.title}
      refNumber={refNumber}
      actions={
        <>
          <button
            type="button"
            className="civic-btn civic-btn-ghost"
            onClick={() =>
              transition({ kind: "filling", activeField: undefined })
            }
          >
            Înapoi la editare
          </button>
          <button
            type="button"
            className="civic-btn civic-btn-primary"
            onClick={() => void generatePdf()}
            disabled={generating}
          >
            {generating ? "Se generează…" : "Generează PDF"}
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
            <div>
              Cerere nr. <strong>{refNumber}</strong>
            </div>
            <div>
              Data:{" "}
              {new Date(document.created_at).toLocaleDateString("ro-RO")}
            </div>
          </div>
        </div>
        <div className="doc-title">{procedure.title}</div>

        <table className="doc-fields">
          <tbody>
            {procedure.fields.map((f) => {
              const v = document.fields[f.name];
              const filled =
                v !== undefined && v !== null && String(v).length > 0;
              const isEditing = editing === f.name;
              return (
                <tr key={f.name}>
                  <td className="doc-label">
                    {f.label}
                    {f.required ? <span aria-hidden> *</span> : null}
                  </td>
                  <td className="doc-value">
                    {isEditing ? (
                      <div className="flex items-center gap-2">
                        <Input
                          value={draft}
                          onChange={(e) => setDraft(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") void commitEdit(f.name);
                            if (e.key === "Escape") {
                              setEditing(null);
                              setDraft("");
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
                    ) : (
                      <span className="flex items-center justify-between gap-2">
                        <span>
                          {filled ? (
                            String(v)
                          ) : (
                            <span className="doc-empty">…</span>
                          )}
                          {(f.source === "roeid" || f.source === "citizen") &&
                          filled ? (
                            <span className="doc-auto">✓ auto</span>
                          ) : null}
                        </span>
                        <button
                          type="button"
                          className="icon-btn"
                          onClick={() => {
                            setEditing(f.name);
                            setDraft(filled ? String(v) : "");
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
