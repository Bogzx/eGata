"use client";

import { useState } from "react";
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

function ActItem({
  act,
  onPreview,
}: {
  act: ResolvedActeNecesareItem;
  onPreview: (procedureId: string, title: string) => void;
}) {
  const category = categorizeAct(act);

  return (
    <li
      className="rounded-lg border p-3"
      style={{ borderColor: "var(--c-line)", background: "var(--c-bg)" }}
    >
      <p className="font-medium">
        {act.denumire}
        {act.obligatoriu === false ? (
          <span className="ml-1 text-xs" style={{ color: "var(--c-ink-soft)" }}>
            (opțional)
          </span>
        ) : null}
      </p>

      {/* Per-category details */}
      {category === "primarie-completable" ? (
        <>
          <span
            className="mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium"
            style={{
              background: "rgba(47, 160, 132, 0.18)",
              color: "var(--c-dark)",
            }}
          >
            🏛️ Emis de Primăria Cluj-Napoca
          </span>
          <div className="mt-2">
            <button
              type="button"
              className="civic-btn civic-btn-ghost"
              onClick={() => onPreview(act.linked_procedure_id!, act.denumire)}
            >
              👁️ Vezi documentul
            </button>
          </div>
        </>
      ) : category === "primarie-fizic" ? (
        <>
          <span
            className="mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium"
            style={{
              background: "rgba(47, 160, 132, 0.18)",
              color: "var(--c-dark)",
            }}
          >
            🏛️ De la Primăria Cluj-Napoca
          </span>
          <p
            className="mt-1 text-xs"
            style={{ color: "var(--c-ink-soft)" }}
          >
            📍 Ghișeul CIC, str. Moților nr. 3, parter, Cluj-Napoca
          </p>
        </>
      ) : category === "user-personal" ? (
        <>
          <span
            className="mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium"
            style={{
              background: "rgba(120, 120, 120, 0.18)",
              color: "var(--c-dark)",
            }}
          >
            👤 Acte personale
          </span>
          <p className="mt-1 text-xs" style={{ color: "var(--c-ink-soft)" }}>
            Adu o <strong>copie</strong>
            {act.format ? ` (format: ${act.format})` : ""} cu tine la ghișeu.
          </p>
        </>
      ) : (
        // extern-institutie
        <>
          <span
            className="mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium"
            style={{
              background: "rgba(255, 165, 0, 0.18)",
              color: "var(--c-dark)",
            }}
          >
            📥 De la altă instituție
          </span>
          <p className="mt-1 text-xs" style={{ color: "var(--c-ink-soft)" }}>
            Mergi la <strong>{act.institutie_nume}</strong>
            {act.format ? ` și cere ${act.format}` : ""}.
          </p>
        </>
      )}

      {act.observatie ? (
        <p
          className="mt-2 text-xs italic"
          style={{ color: "var(--c-ink-soft)" }}
        >
          {act.observatie}
        </p>
      ) : null}
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
