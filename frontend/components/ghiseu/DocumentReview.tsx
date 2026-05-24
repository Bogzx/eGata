"use client";

import { formatValue } from "@/lib/format";
import { useSessionStore } from "@/lib/sessionStore";
import { CheckIcon, EditIcon } from "./icons";

type Props = {
  onConfirm: () => void;
  onAmend: () => void;
};

export function DocumentReview({ onConfirm, onAmend }: Props) {
  const document = useSessionStore((s) => s.document);
  const procedure = useSessionStore((s) => s.procedure);

  if (!document || !procedure) {
    return (
      <div className="gh-review gh-review-loading">
        <div className="gh-review-head">
          <h2 className="gh-review-title">Se încarcă cererea...</h2>
        </div>
      </div>
    );
  }

  const fields = (document.fields ?? {}) as Record<string, unknown>;
  const rows = procedure.fields.map((pf) => {
    const value = fields[pf.name];
    const hasValue = value != null && value !== "";
    return {
      label: pf.label,
      value: formatValue(value),
      auto: pf.source.includes("profile") && hasValue,
    };
  });

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
            <div className="doc-title">{procedure.title}</div>
            <div className="doc-paper-sub">Cerere în curs de pregătire</div>
          </div>
        </div>

        <div className="doc-fields-grid">
          {rows.map((f) => (
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
