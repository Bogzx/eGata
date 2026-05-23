"use client";

import type { ReactNode } from "react";

export type DocPaperField = {
  label: string;
  value?: ReactNode;
  auto?: boolean;
};

type Props = {
  /** Stamp text — defaults to PRIMĂRIA CLUJ-NAPOCA. */
  stamp?: string;
  refNumber?: string;
  date?: string;
  title: string;
  fields: DocPaperField[];
  /** Hide the corner DRAFT badge (used when document is finalized). */
  final?: boolean;
  /** Show signature lines at the bottom. */
  showSignatures?: boolean;
  /** Wider padding for the drawer detail view. */
  detail?: boolean;
};

/**
 * Civic paper rendering — used by both DocPane (right column) and the drawer
 * detail panel. Mirrors the design's `.doc-paper` markup exactly.
 */
export function DocPaper({
  stamp = "PRIMĂRIA\nCLUJ-NAPOCA",
  refNumber,
  date,
  title,
  fields,
  final = false,
  showSignatures = false,
  detail = false,
}: Props) {
  return (
    <div
      className={[
        "doc-paper",
        detail ? "doc-paper-detail" : "",
        final ? "is-final" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="doc-header">
        <div className="doc-stamp">
          {stamp.split("\n").map((l, i) => (
            <div key={i}>{l}</div>
          ))}
        </div>
        <div className="doc-paper-meta">
          {refNumber ? (
            <div>
              {final ? "Document nr." : "Cerere nr."}{" "}
              <strong>{refNumber}</strong>
            </div>
          ) : null}
          {date ? <div>Data: {date}</div> : null}
        </div>
      </div>

      <div className="doc-title">{title}</div>

      <table className="doc-fields">
        <tbody>
          {fields.map((f, i) => {
            const isEmpty =
              f.value === undefined ||
              f.value === null ||
              (typeof f.value === "string" && f.value.trim() === "");
            return (
              <tr key={`${f.label}-${i}`}>
                <td className="doc-label">{f.label}</td>
                <td className="doc-value">
                  {isEmpty ? (
                    <span className="doc-empty">…</span>
                  ) : (
                    <span>{f.value}</span>
                  )}
                  {f.auto && !isEmpty ? (
                    <span
                      className="doc-auto"
                      title="Auto-completat din ROeID"
                    >
                      ✓ auto
                    </span>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {showSignatures ? (
        <div className="doc-foot">
          <div>
            <div className="doc-sig">Semnătură</div>
            <div className="doc-sig-line" />
          </div>
          <div>
            <div className="doc-sig">Funcționar</div>
            <div className="doc-sig-line" />
          </div>
        </div>
      ) : null}
    </div>
  );
}
