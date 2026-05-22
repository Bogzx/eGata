"use client";

import type { LedgerEntry, LedgerResponse } from "@/lib/types";
import { t } from "@/lib/i18n";

const EVENT_LABEL: Record<LedgerEntry["event_type"], string> = {
  doc_created: "Document creat",
  completed_draft: "Ciornă completată",
  pdf_generated: "PDF generat",
  delivered: "Trimis la primărie",
  redirected: "Redirecționat",
  reminder_created: "Reminder creat",
};

type Props = {
  ledger: LedgerResponse;
};

export function AuditTimeline({ ledger }: Props) {
  return (
    <section aria-labelledby="audit-heading" className="space-y-4">
      <h2 id="audit-heading" className="text-xl font-semibold">
        {t("doc.audit_title")}
      </h2>

      <ol className="relative space-y-4 border-l-2 border-muted pl-6">
        {ledger.entries.map((e) => (
          <li key={e.id} className="relative">
            <span
              aria-hidden
              className="absolute -left-[1.55rem] top-1 h-3 w-3 rounded-full bg-primary"
            />
            <p className="font-medium">{EVENT_LABEL[e.event_type]}</p>
            <p className="text-xs text-muted-foreground">
              {new Date(e.created_at).toLocaleString("ro-RO")}
            </p>
            <p className="break-all font-mono text-[10px] text-muted-foreground/80">
              row_hash: {e.row_hash}
            </p>
          </li>
        ))}
      </ol>

      <p
        role="status"
        className={
          ledger.verified
            ? "text-sm font-medium text-green-700"
            : "text-sm font-medium text-destructive"
        }
      >
        {ledger.verified
          ? `✓ ${t("doc.audit_verified")}`
          : `⚠ ${t("doc.audit_unverified")}`}
      </p>
    </section>
  );
}
