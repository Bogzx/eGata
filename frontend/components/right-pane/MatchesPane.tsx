"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useSessionStore } from "@/lib/sessionStore";
import type { ResolvedActeNecesareItem } from "@/lib/types";
import { DocPane } from "./DocPane";
import { PdfPreviewDialog } from "./PdfPreviewDialog";

type ActCategory =
  | "primarie-completable"
  | "primarie-fizic"
  | "user-personal"
  | "extern-institutie";

function categorizeAct(a: ResolvedActeNecesareItem): ActCategory {
  if (a.linked_procedure_id) return "primarie-completable";
  if (a.institutie_nume) return "extern-institutie";
  if (a.emitent === "user") return "user-personal";
  return "primarie-fizic";
}

const CATEGORY_META: Record<
  ActCategory,
  { icon: string; shortLabel: string; longLabel: string; tint: string }
> = {
  "primarie-completable": {
    icon: "🏛️",
    shortLabel: "Primărie",
    longLabel: "Emis de Primăria Cluj-Napoca",
    tint: "rgba(47, 160, 132, 0.18)",
  },
  "primarie-fizic": {
    icon: "🏛️",
    shortLabel: "Primărie",
    longLabel: "De la Primăria Cluj-Napoca",
    tint: "rgba(47, 160, 132, 0.18)",
  },
  "user-personal": {
    icon: "👤",
    shortLabel: "Personal",
    longLabel: "Acte personale",
    tint: "rgba(120, 120, 120, 0.18)",
  },
  "extern-institutie": {
    icon: "📥",
    shortLabel: "Extern",
    longLabel: "De la altă instituție",
    tint: "rgba(255, 165, 0, 0.18)",
  },
};

function ActItem({
  act,
  onPreview,
}: {
  act: ResolvedActeNecesareItem;
  onPreview: (procedureId: string, title: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const category = categorizeAct(act);
  const meta = CATEGORY_META[category];

  return (
    <li>
      <motion.div
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setExpanded((v) => !v);
          }
        }}
        className="cursor-pointer rounded-lg border p-3 outline-none focus-visible:ring-2"
        style={{
          borderColor: "var(--c-line)",
          background: "var(--c-bg)",
        }}
        initial={false}
        whileHover={{
          backgroundColor: "rgba(47, 160, 132, 0.06)",
          borderColor: "rgba(47, 160, 132, 0.45)",
          y: -1,
          boxShadow: "0 4px 14px rgba(0, 0, 0, 0.08)",
        }}
        transition={{ duration: 0.15 }}
      >
        <div className="flex items-center gap-2">
          <p className="font-medium flex-1">
            {act.denumire}
            {act.obligatoriu === false ? (
              <span className="ml-1 text-xs" style={{ color: "var(--c-ink-soft)" }}>
                (opțional)
              </span>
            ) : null}
          </p>
          <span
            className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium"
            style={{ background: meta.tint, color: "var(--c-dark)" }}
          >
            {meta.icon} {meta.shortLabel}
          </span>
          <motion.span
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            style={{ color: "var(--c-ink-soft)" }}
            aria-hidden
          >
            <ChevronDown size={16} />
          </motion.span>
        </div>

        <AnimatePresence initial={false}>
          {expanded ? (
            <motion.div
              key="details"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              style={{ overflow: "hidden" }}
            >
              <div className="pt-3">
                <span
                  className="inline-block rounded px-2 py-0.5 text-xs font-medium"
                  style={{ background: meta.tint, color: "var(--c-dark)" }}
                >
                  {meta.icon} {meta.longLabel}
                </span>

                {category === "primarie-completable" ? (
                  <div className="mt-2">
                    <button
                      type="button"
                      className="civic-btn civic-btn-ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        onPreview(act.linked_procedure_id!, act.denumire);
                      }}
                    >
                      👁️ Vezi documentul
                    </button>
                  </div>
                ) : category === "primarie-fizic" ? (
                  <p className="mt-2 text-xs" style={{ color: "var(--c-ink-soft)" }}>
                    📍 Ghișeul CIC, str. Moților nr. 3, parter, Cluj-Napoca
                  </p>
                ) : category === "user-personal" ? (
                  <p className="mt-2 text-xs" style={{ color: "var(--c-ink-soft)" }}>
                    Adu o <strong>copie</strong>
                    {act.format ? ` (format: ${act.format})` : ""} cu tine la ghișeu.
                  </p>
                ) : (
                  <p className="mt-2 text-xs" style={{ color: "var(--c-ink-soft)" }}>
                    Mergi la <strong>{act.institutie_nume}</strong>
                    {act.format ? ` și cere ${act.format}` : ""}.
                  </p>
                )}

                {act.observatie ? (
                  <p
                    className="mt-2 text-xs italic"
                    style={{ color: "var(--c-ink-soft)" }}
                  >
                    {act.observatie}
                  </p>
                ) : null}
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </motion.div>
    </li>
  );
}

export function MatchesPane() {
  const matches = useSessionStore((s) => s.lookupMatches);
  const [preview, setPreview] = useState<{ procedureId: string; title: string } | null>(null);

  const top = matches[0];
  if (!top) {
    return (
      <DocPane eyebrow="Proceduri găsite" title="Caut potrivire…">
        <p className="text-sm" style={{ color: "var(--c-ink-soft)" }}>
          Asistentul caută cea mai potrivită procedură pentru tine.
        </p>
      </DocPane>
    );
  }

  return (
    <>
      <DocPane title={top.title} titleEmphasis>
        <article className="space-y-5">
          {top.acte_necesare && top.acte_necesare.length > 0 ? (
            <ul className="space-y-2 text-sm">
              {top.acte_necesare.map((a, i) => (
                <ActItem
                  key={`${a.denumire}-${i}`}
                  act={a}
                  onPreview={(pid, title) => setPreview({ procedureId: pid, title })}
                />
              ))}
            </ul>
          ) : (
            <p className="text-sm" style={{ color: "var(--c-ink-soft)" }}>
              Nu sunt acte fizice obligatorii pentru această procedură.
            </p>
          )}
        </article>
      </DocPane>
      <PdfPreviewDialog
        procedureId={preview?.procedureId ?? null}
        title={preview?.title ?? ""}
        onClose={() => setPreview(null)}
      />
    </>
  );
}
