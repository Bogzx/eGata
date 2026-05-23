"use client";

import { useState } from "react";
import { Check, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";

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

  return (
    <article className="mx-auto max-w-2xl space-y-5 p-6">
      <header>
        <p className="text-xs uppercase tracking-wider text-muted-foreground">
          Verifică datele
        </p>
        <h2 className="mt-1 text-2xl font-semibold">{procedure.title}</h2>
      </header>

      <ul className="space-y-2">
        {procedure.fields.map((f) => {
          const v = document.fields[f.name];
          const filled = v !== undefined && v !== null && String(v).length > 0;
          const isEditing = editing === f.name;
          return (
            <li
              key={f.name}
              className="grid grid-cols-[1fr_auto] items-center gap-3 rounded-lg border bg-card p-3 text-sm"
            >
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">
                  {f.label}
                </p>
                {isEditing ? (
                  <Input
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void commitEdit(f.name);
                    }}
                    autoFocus
                  />
                ) : (
                  <p className={filled ? "" : "text-muted-foreground"}>
                    {filled ? String(v) : "—"}
                  </p>
                )}
              </div>
              {isEditing ? (
                <Button
                  size="icon"
                  onClick={() => void commitEdit(f.name)}
                  aria-label="Salvează"
                >
                  <Check size={14} />
                </Button>
              ) : (
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => {
                    setEditing(f.name);
                    setDraft(filled ? String(v) : "");
                  }}
                  aria-label={`Editează ${f.label}`}
                >
                  <Pencil size={14} />
                </Button>
              )}
            </li>
          );
        })}
      </ul>

      <Button
        onClick={() => void generatePdf()}
        disabled={generating}
        size="lg"
      >
        {generating ? "Se generează..." : "Generează PDF"}
      </Button>
    </article>
  );
}
