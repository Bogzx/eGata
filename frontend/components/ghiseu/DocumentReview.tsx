"use client";

import { CheckIcon, EditIcon } from "./icons";

type Field = { label: string; value: string; auto: boolean };

const FIELDS: Field[] = [
  { label: "Nume și prenume", value: "Popescu Ana-Maria", auto: true },
  { label: "CNP", value: "2940413081265", auto: true },
  {
    label: "Adresa",
    value: "Str. Memorandumului 28, ap. 14, Cluj-Napoca",
    auto: true,
  },
  { label: "Email confirmare", value: "ana.popescu@gmail.com", auto: true },
  { label: "Perioada", value: "Nov 2025 — Apr 2026 (6 luni)", auto: false },
  {
    label: "Instituție destinatară",
    value: "Banca Transilvania — Cluj Centru",
    auto: false,
  },
  { label: "Motiv", value: "Credit ipotecar", auto: false },
  { label: "Limba", value: "Română", auto: false },
];

type Props = {
  onConfirm: () => void;
  onAmend: () => void;
};

export function DocumentReview({ onConfirm, onAmend }: Props) {
  return (
    <div className="gh-review">
      <div className="gh-review-head">
        <h2 className="gh-review-title">Iată cererea ta. E corect totul?</h2>
      </div>

      <div className="doc-paper">
        <div className="doc-header">
          <div className="doc-stamp">
            <div>PRIMĂRIA</div>
            <div>CLUJ-NAPOCA</div>
          </div>
          <div className="doc-paper-titleblock">
            <div className="doc-title">Adeverință de venit</div>
            <div className="doc-paper-sub">
              Cerere către Direcția de Taxe și Impozite
            </div>
          </div>
          <div className="doc-paper-meta">
            <div>
              Cerere nr. <strong>2026-AV-08412</strong>
            </div>
            <div>Data: 24.05.2026</div>
          </div>
        </div>

        <div className="doc-fields-grid">
          {FIELDS.map((f) => (
            <div className="dfg-row" key={f.label}>
              <div className="dfg-label">{f.label}</div>
              <div className="dfg-value">
                <span className="dfg-text">{f.value}</span>
                {f.auto ? <span className="doc-auto">✓ auto</span> : null}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="gh-review-actions">
        <button
          type="button"
          className="gh-review-action"
          data-kind="confirm"
          onClick={onConfirm}
        >
          <span className="ra-icon">
            <CheckIcon size={22} />
          </span>
          <span className="ra-body">
            <span>Da, e corect</span>
            <span className="ra-hint">Continuă spre trimitere</span>
          </span>
        </button>
        <button
          type="button"
          className="gh-review-action"
          data-kind="amend"
          onClick={onAmend}
        >
          <span className="ra-icon">
            <EditIcon size={20} />
          </span>
          <span className="ra-body">
            <span>Mai am o corectură</span>
            <span className="ra-hint">Spune-mi ce să schimb</span>
          </span>
        </button>
      </div>
    </div>
  );
}
