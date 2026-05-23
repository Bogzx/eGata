"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { reminderItem, usePrefersReducedMotion, variantsWithReducedMotion } from "@/lib/motion";
import type { Reminder } from "@/lib/types";

const REDIRECT_CONTACT: Record<string, { name: string; url: string; phone?: string }> = {
  ANAF: { name: "ANAF", url: "https://anaf.ro/", phone: "031 403 91 60" },
  CNAS: { name: "CNAS", url: "https://cnas.ro/" },
  DRPCIV: { name: "DRPCIV", url: "https://drpciv.ro/" },
  ONRC: { name: "ONRC", url: "https://onrc.ro/" },
  SPCEP: { name: "SPCEP Cluj", url: "https://primariaclujnapoca.ro/" },
};

type Props = {
  reminder: Reminder;
  onDismissed?: (id: string) => void;
  onStarted?: (id: string) => void;
};

export function ReminderCard({ reminder, onDismissed, onStarted }: Props) {
  const router = useRouter();
  const reduced = usePrefersReducedMotion();
  const variants = variantsWithReducedMotion(reminderItem, reduced);

  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hidden, setHidden] = useState(false);

  if (hidden) return null;

  const isExternal = reminder.kind === "external_redirect";
  const overdue =
    reminder.due_date !== undefined && new Date(reminder.due_date) < new Date();
  const contact = isExternal && reminder.redirect_target
    ? REDIRECT_CONTACT[reminder.redirect_target]
    : null;

  async function handleStart() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.startReminder(reminder.id);
      onStarted?.(reminder.id);
      router.push(`/req/${result.document_id}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Eroare necunoscută";
      setError(msg);
      setBusy(false);
    }
  }

  async function handleDismiss() {
    setBusy(true);
    setError(null);
    try {
      await api.dismissReminder(reminder.id);
      setHidden(true);
      onDismissed?.(reminder.id);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Eroare la respingere";
      setError(msg);
      setBusy(false);
    }
  }

  return (
    <motion.div
      data-testid="reminder-card"
      variants={variants}
      initial="hidden"
      animate="visible"
    >
      <Card className={overdue ? "border-l-4 border-l-destructive" : "border-l-4 border-l-primary"}>
        <CardContent className="space-y-3 p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2">
              <span aria-hidden className="text-xl">
                {isExternal ? "↪" : "⚠"}
              </span>
              <div>
                <p className="text-xs text-muted-foreground">
                  {isExternal
                    ? `Redirecționare către ${reminder.redirect_target ?? "instituție"}`
                    : "Acțiune recomandată"}
                </p>
                <p className="font-medium">{reminder.title}</p>
                {reminder.due_date ? (
                  <p
                    className={
                      overdue
                        ? "mt-1 text-xs text-destructive"
                        : "mt-1 text-xs text-muted-foreground"
                    }
                  >
                    Termen: {new Date(reminder.due_date).toLocaleDateString("ro-RO")}
                    {overdue ? " (depășit)" : ""}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {isExternal ? (
                <Badge variant="outline">{reminder.redirect_target}</Badge>
              ) : null}
              <button
                type="button"
                aria-label="Respinge"
                onClick={handleDismiss}
                disabled={busy}
                className="text-muted-foreground transition hover:text-foreground"
              >
                ✕
              </button>
            </div>
          </div>

          {!isExternal ? (
            <Button size="sm" onClick={handleStart} disabled={busy}>
              {busy ? "Se inițiază…" : "Începe acum"}
            </Button>
          ) : (
            <div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setExpanded((v) => !v)}
                aria-expanded={expanded}
              >
                {expanded ? "Ascunde detalii" : "Vezi detalii"}
              </Button>
              {expanded && contact ? (
                <div className="mt-3 space-y-2 text-sm text-muted-foreground">
                  <p>
                    Această procedură nu este în scope-ul primăriei. O poți rezolva pe
                    site-ul oficial:
                  </p>
                  <p>
                    <a
                      href={contact.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary underline"
                    >
                      {contact.name}
                    </a>
                    {contact.phone ? <> — Tel: {contact.phone}</> : null}
                  </p>
                  <p className="text-xs italic">
                    Pe roadmap: integrare directă, astfel încât să nu mai fie nevoie să
                    ieși din CivicAI.
                  </p>
                </div>
              ) : null}
            </div>
          )}

          {error ? (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </motion.div>
  );
}
