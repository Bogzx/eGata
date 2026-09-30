"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";
import type {
  Document,
  LedgerEntry,
  Procedure,
  Reminder,
} from "@/lib/types";
import { verifyLedger, type LedgerCheck } from "@/lib/ledgerVerify";
import { DocPaper, type DocPaperField } from "@/components/right-pane/DocPaper";

const ICON_BY_CATEGORY: Record<string, string> = {
  acte: "🪪",
  domiciliu: "🏠",
  fiscal: "🧾",
  venit: "📄",
  copii: "👶",
  vehicul: "🚗",
  sanatate: "🩺",
  nastere: "📜",
};

function iconFor(category: string): string {
  for (const [k, v] of Object.entries(ICON_BY_CATEGORY)) {
    if (category.includes(k)) return v;
  }
  return "📋";
}

function statusKind(d: Document): "ok" | "wip" {
  return d.status === "finalized" ? "ok" : "wip";
}

function statusLabel(d: Document): string {
  return d.status === "finalized" ? "Trimisă" : "În lucru";
}

function formatDate(s: string): string {
  try {
    return new Date(s).toLocaleDateString("ro-RO");
  } catch {
    return s;
  }
}

function shortHash(s: string): string {
  if (!s) return "";
  return s.slice(0, 4) + "…" + s.slice(-4);
}

const EVENT_LABELS: Record<LedgerEntry["event_type"], string> = {
  doc_created: "Document creat",
  completed_draft: "Schiță finalizată",
  pdf_generated: "PDF generat",
  delivered: "Trimis la primărie",
  redirected: "Redirecționat",
  reminder_created: "Amintire setată",
};

export function DocumentsDrawer() {
  const open = useSessionStore((s) => s.drawerOpen);
  const close = useSessionStore((s) => s.closeDrawer);
  const loadDocument = useSessionStore((s) => s.loadDocument);

  const [documents, setDocuments] = useState<Document[]>([]);
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);

  // Detail panel state
  const [viewingDoc, setViewingDoc] = useState<Document | null>(null);
  const [viewingDocOpen, setViewingDocOpen] = useState(false);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [ledgerCheck, setLedgerCheck] = useState<LedgerCheck | null>(null);
  const [serverVerified, setServerVerified] = useState<boolean | null>(null);
  const closeTimer = useRef<number | null>(null);

  const drawerCloseBtnRef = useRef<HTMLButtonElement | null>(null);
  const detailCloseBtnRef = useRef<HTMLButtonElement | null>(null);

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

  function openDocDetail(d: Document) {
    if (closeTimer.current) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
    setViewingDoc(d);
    setLedger([]);
    setLedgerCheck(null);
    setServerVerified(null);
    void api
      .getDocumentLedger(d.id)
      .then((r) => {
        setLedger(r.entries);
        setServerVerified(r.verified);
        // Don't take the server's flag on trust: re-derive every hash here.
        return verifyLedger(r.entries, r).then(setLedgerCheck);
      })
      .catch(() => setLedger([]));
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        setViewingDocOpen(true);
        window.setTimeout(
          () => detailCloseBtnRef.current?.focus(),
          380,
        );
      }),
    );
  }

  function closeDocDetail() {
    setViewingDocOpen(false);
    closeTimer.current = window.setTimeout(() => {
      setViewingDoc(null);
      setLedger([]);
    }, 380);
  }

  useEffect(() => {
    if (!open) {
      setViewingDocOpen(false);
      setViewingDoc(null);
      setLedger([]);
    } else {
      window.setTimeout(() => drawerCloseBtnRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      if (viewingDoc) {
        closeDocDetail();
        return;
      }
      if (open) close();
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close, viewingDoc]);

  // Make the chat shell behind us inert while the drawer is open.
  useEffect(() => {
    const shell = document.querySelector<HTMLElement>(".civic-shell");
    if (!shell) return;
    if (open) shell.setAttribute("inert", "");
    else shell.removeAttribute("inert");
    return () => shell.removeAttribute("inert");
  }, [open]);

  if (!open) return null;

  const titleOf = (id: string) =>
    procedures.find((p) => p.id === id)?.title ?? id;
  const categoryOf = (id: string) =>
    procedures.find((p) => p.id === id)?.category ?? "";
  const pending = reminders.filter((r) => r.status === "pending");

  return (
    <div
      className="drawer-back"
      onClick={close}
      role="presentation"
    >
      {viewingDoc ? (
        <DocDetail
          doc={viewingDoc}
          procedure={procedures.find((p) => p.id === viewingDoc.procedure_id)}
          isOpen={viewingDocOpen}
          ledger={ledger}
          ledgerCheck={ledgerCheck}
          serverVerified={serverVerified}
          closeBtnRef={detailCloseBtnRef}
          onClose={closeDocDetail}
          onUse={() => {
            void loadDocument(viewingDoc.id);
            close();
          }}
        />
      ) : null}

      <section
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="drawer-head">
          <h2 id="drawer-title">Documentele mele</h2>
          <button
            ref={drawerCloseBtnRef}
            type="button"
            className="icon-btn"
            onClick={close}
            aria-label="Închide Documentele mele"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
              focusable="false"
            >
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </header>

        <ul className="drawer-body" role="list">
          {pending.length > 0 ? (
            <>
              <li>
                <p className="drawer-section-label">Pentru tine acum</p>
              </li>
              {pending.map((r) => (
                <li key={`reminder-${r.id}`}>
                  <div
                    className={`reminder-card ${
                      r.due_date && new Date(r.due_date) < new Date()
                        ? "kind-warning"
                        : ""
                    }`}
                  >
                    <p className="reminder-title">{r.title}</p>
                    {r.due_date ? (
                      <p className="text-xs text-muted-foreground">
                        Termen: {formatDate(r.due_date)}
                      </p>
                    ) : null}
                    <div className="reminder-actions">
                      <button
                        type="button"
                        className="civic-btn civic-btn-primary"
                        onClick={async () => {
                          const out = await api.startReminder(r.id);
                          await loadDocument(out.document_id);
                          close();
                        }}
                      >
                        Începe
                      </button>
                      <button
                        type="button"
                        className="civic-btn civic-btn-ghost"
                        onClick={async () => {
                          await api.dismissReminder(r.id);
                          setReminders((rs) =>
                            rs.filter((x) => x.id !== r.id),
                          );
                        }}
                      >
                        Renunță
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </>
          ) : null}

          <li>
            <p className="drawer-section-label">Documentele mele</p>
          </li>

          {documents.length === 0 ? (
            <li>
              <p className="text-sm text-muted-foreground p-3">
                Niciun document încă.
              </p>
            </li>
          ) : (
            documents.map((d) => {
              const isActive = viewingDoc?.id === d.id && viewingDocOpen;
              const title = titleOf(d.procedure_id);
              const cat = categoryOf(d.procedure_id);
              const refNum =
                d.ref_number ?? d.id.slice(0, 8).toUpperCase();
              return (
                <li key={d.id}>
                  <button
                    type="button"
                    className={"doc-row " + (isActive ? "is-active" : "")}
                    aria-pressed={isActive}
                    aria-label={`${title}, număr ${refNum}, ${statusLabel(d)}. ${isActive ? "Închide" : "Deschide"} previzualizarea.`}
                    onClick={() =>
                      isActive ? closeDocDetail() : openDocDetail(d)
                    }
                  >
                    <span className="doc-icon" aria-hidden="true">
                      {iconFor(cat)}
                    </span>
                    <span className="doc-meta">
                      <span className="doc-name">{title}</span>
                      <span className="doc-num">{refNum}</span>
                    </span>
                    <span
                      className={`doc-status k-${statusKind(d)}`}
                      aria-hidden="true"
                    >
                      {statusLabel(d)}
                    </span>
                    <svg
                      className="doc-row-arrow"
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      aria-hidden="true"
                      focusable="false"
                    >
                      <path d="M9 6l6 6-6 6" />
                    </svg>
                  </button>
                </li>
              );
            })
          )}
        </ul>
      </section>
    </div>
  );
}

type DocDetailProps = {
  doc: Document;
  procedure: Procedure | undefined;
  isOpen: boolean;
  ledger: LedgerEntry[];
  ledgerCheck: LedgerCheck | null;
  serverVerified: boolean | null;
  closeBtnRef: React.MutableRefObject<HTMLButtonElement | null>;
  onClose: () => void;
  onUse: () => void;
};

function DocDetail({
  doc,
  procedure,
  isOpen,
  ledger,
  ledgerCheck,
  serverVerified,
  closeBtnRef,
  onClose,
  onUse,
}: DocDetailProps) {
  const refNum = doc.ref_number ?? doc.id.slice(0, 8).toUpperCase();
  const title = procedure?.title ?? "Document";
  const status = statusLabel(doc);
  const kind = statusKind(doc);

  const fields: DocPaperField[] = procedure
    ? procedure.fields.map((f) => {
        const v = doc.fields[f.name];
        return {
          label: f.label,
          value: v !== undefined && v !== null ? String(v) : "",
          auto: f.source === "roeid" || f.source === "citizen",
        };
      })
    : [];

  const fallbackHistory: LedgerEntry[] =
    ledger.length > 0
      ? ledger
      : [
          {
            id: 0,
            event_type: "doc_created",
            payload_hash: "",
            prev_hash: "",
            // No ledger loaded — show the event, never a made-up hash.
            row_hash: "",
            created_at: doc.created_at,
          },
        ];

  return (
    <section
      className={"doc-detail " + (isOpen ? "is-open" : "")}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={(e) => e.stopPropagation()}
    >
      <header className="doc-detail-head">
        <button
          ref={closeBtnRef}
          type="button"
          className="icon-btn"
          onClick={onClose}
          aria-label="Închide previzualizarea documentului"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
            focusable="false"
          >
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <div className="doc-detail-titles">
          <div className="doc-detail-eyebrow">{refNum}</div>
          <h2 className="doc-detail-h">{title}</h2>
        </div>
        <div
          className={`doc-status k-${kind}`}
          aria-label={`Stare: ${status}`}
        >
          {status}
        </div>
      </header>

      <div className="doc-detail-body">
        <div className="doc-detail-meta">
          <div>
            <div className="dm-label">Emis</div>
            <div className="dm-value">{formatDate(doc.created_at)}</div>
          </div>
          <div>
            <div className="dm-label">
              {doc.status === "finalized" ? "Trimis" : "Stare"}
            </div>
            <div className="dm-value">
              {doc.delivered_at ? formatDate(doc.delivered_at) : status}
            </div>
          </div>
          <div>
            <div className="dm-label">Verificat</div>
            <div className="dm-value">
              <span className="check" aria-hidden="true">
                ✓
              </span>
              ROeID
            </div>
          </div>
        </div>

        <DocPaper
          detail
          stamp={"PRIMĂRIA\nCLUJ-NAPOCA"}
          refNumber={refNum}
          date={formatDate(doc.created_at)}
          title={title}
          fields={fields}
          final={doc.status === "finalized"}
        />

        <div className="doc-detail-history">
          <div className="dh-title">Istoric · audit ledger</div>
          <ol className="dh-list">
            {fallbackHistory.map((e, i) => (
              <li key={e.id ?? i}>
                <span
                  className={
                    "dh-dot " +
                    (i === fallbackHistory.length - 1
                      ? "dh-dot-current"
                      : "")
                  }
                />
                <div>
                  <div className="dh-event">
                    {EVENT_LABELS[e.event_type] ?? e.event_type}
                  </div>
                  <div className="dh-meta">
                    {formatDate(e.created_at)}
                    {e.row_hash ? (
                      <>
                        {" · hash "}
                        <code>{shortHash(e.row_hash)}</code>
                      </>
                    ) : null}
                  </div>
                </div>
              </li>
            ))}
          </ol>
          <LedgerStatus check={ledgerCheck} serverVerified={serverVerified} />
        </div>
      </div>

      <div className="doc-detail-actions">
        <button
          type="button"
          className="civic-btn civic-btn-secondary"
          onClick={onUse}
        >
          Deschide în chat
        </button>
        {doc.pdf_url ? (
          <a
            className="civic-btn civic-btn-secondary"
            href={doc.pdf_url}
            target="_blank"
            rel="noreferrer"
          >
            Descarcă PDF
          </a>
        ) : null}
      </div>
    </section>
  );
}


/** What the citizen can trust about this document's history: the browser's
 * own re-derivation of the chain first, the server's flag only as a fallback. */
function LedgerStatus({
  check,
  serverVerified,
}: {
  check: LedgerCheck | null;
  serverVerified: boolean | null;
}) {
  if (check === null) return null;
  if (check.status === "verified") {
    return (
      <div role="status" className="dh-meta mt-2 space-y-1">
        <div className="font-medium text-green-700">
          ✓ Verificat în browserul tău: {check.rows} pași, lanț intact.
        </div>
        {check.signatures.status === "valid" ? (
          <div title={check.signatures.keyIds.join(", ")}>
            ✓ Fiecare pas e semnat digital de primărie (cheia{" "}
            <code>{check.signatures.keyIds.map((k) => k.slice(-8)).join(", ")}</code>).
          </div>
        ) : check.signatures.status === "partial" ? (
          <div>{check.signatures.unsigned} pași nu sunt încă semnați.</div>
        ) : (
          <div>Browserul nu poate verifica semnăturile Ed25519.</div>
        )}
        {check.pdfSha256 ? (
          <div title={check.pdfSha256}>
            Amprenta PDF (SHA-256): <code>{shortHash(check.pdfSha256)}</code>
          </div>
        ) : null}
        <div title={check.head}>
          Dovadă de păstrat (hash final): <code>{shortHash(check.head)}</code>
        </div>
      </div>
    );
  }
  if (check.status === "broken") {
    return (
      <div role="alert" className="dh-meta mt-2 font-medium text-destructive">
        ⚠ Jurnalul NU se verifică: {check.reason}
      </div>
    );
  }
  return (
    <div role="status" className="dh-meta mt-2">
      {serverVerified
        ? "✓ Verificat de server"
        : serverVerified === false
          ? "⚠ Jurnal neverificat"
          : null}
      <span className="block opacity-70">{check.reason}</span>
    </div>
  );
}
