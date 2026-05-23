"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";
import type { Document, Procedure, Reminder } from "@/lib/types";

export function DocumentsDrawer() {
  const open = useSessionStore((s) => s.drawerOpen);
  const close = useSessionStore((s) => s.closeDrawer);
  const loadDocument = useSessionStore((s) => s.loadDocument);

  const [documents, setDocuments] = useState<Document[]>([]);
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);

  useEffect(() => {
    if (!open) return;
    void Promise.all([
      api.listDocuments().catch(() => [] as Document[]),
      api.listProcedures().catch(() => [] as Procedure[]),
      api.listReminders().catch(() => [] as Reminder[]),
    ]).then(([d, p, r]) => {
      setDocuments(d);
      setProcedures(p);
      setReminders(r);
    });
  }, [open]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);

  const titleOf = (id: string) =>
    procedures.find((p) => p.id === id)?.title ?? id;
  const pending = reminders.filter((r) => r.status === "pending");

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-40 bg-black/30"
            onClick={close}
            aria-hidden
          />
          <motion.aside
            initial={{ x: -380 }}
            animate={{ x: 0 }}
            exit={{ x: -380 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="fixed inset-y-0 left-0 z-50 flex w-[380px] max-w-[90vw] flex-col border-r bg-background shadow-xl"
            role="dialog"
            aria-label="Documentele mele"
          >
            <header className="flex items-center justify-between border-b px-4 py-3">
              <h2 className="text-lg font-semibold">Documentele mele</h2>
              <Button
                variant="ghost"
                size="icon"
                onClick={close}
                aria-label="Închide"
              >
                <X size={18} />
              </Button>
            </header>

            <div className="flex-1 overflow-y-auto p-3">
              {pending.length > 0 ? (
                <section className="mb-4">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Pentru tine acum
                  </p>
                  <ul className="space-y-2">
                    {pending.map((r) => (
                      <li key={r.id}>
                        <Card>
                          <CardContent className="space-y-2 p-3">
                            <p className="text-sm font-medium">{r.title}</p>
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                onClick={async () => {
                                  const out = await api.startReminder(r.id);
                                  await loadDocument(out.document_id);
                                }}
                              >
                                Începe
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={async () => {
                                  await api.dismissReminder(r.id);
                                  setReminders((rs) =>
                                    rs.filter((x) => x.id !== r.id),
                                  );
                                }}
                              >
                                Renunță
                              </Button>
                            </div>
                          </CardContent>
                        </Card>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Documentele mele
              </p>
              {documents.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Niciun document încă.
                </p>
              ) : (
                <ul className="space-y-2">
                  {documents.map((d) => (
                    <li key={d.id}>
                      <button
                        type="button"
                        onClick={() => void loadDocument(d.id)}
                        className="w-full rounded-lg border bg-card p-3 text-left text-sm transition hover:bg-accent/40 focus:outline-none focus:ring-2"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium">
                              {titleOf(d.procedure_id)}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {new Date(d.created_at).toLocaleDateString("ro-RO")}
                            </p>
                            {d.ref_number ? (
                              <p className="font-mono text-xs text-muted-foreground">
                                {d.ref_number}
                              </p>
                            ) : null}
                          </div>
                          {d.status === "finalized" ? (
                            <Badge>Trimisă</Badge>
                          ) : (
                            <Badge variant="secondary">În lucru</Badge>
                          )}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}
