"use client";

import type { ExportMethod } from "@/lib/ghiseuStore";
import { CityIcon, MailIcon } from "./icons";

type Pick = Exclude<ExportMethod, null>;

type Option = {
  id: Pick;
  title: string;
  hint: string;
  icon: React.ReactNode;
  recommended?: boolean;
};

const OPTIONS: Option[] = [
  {
    id: "city",
    title: "Trimite la primărie",
    hint: "Cererea intră în lucru imediat.",
    icon: <CityIcon size={36} />,
    recommended: true,
  },
  {
    id: "email",
    title: "Trimite pe email",
    hint: "Pe ana.popescu@gmail.com.",
    icon: <MailIcon size={36} />,
  },
];

type Props = {
  onPick: (id: Pick) => void;
  submitting?: boolean;
  submittingMethod?: Pick | null;
};

export function ExportOptions({
  onPick,
  submitting = false,
  submittingMethod = null,
}: Props) {
  return (
    <div className="gh-export">
      <div className="gh-review-head">
        <h2 className="gh-status-text">Cum trimitem actul?</h2>
      </div>
      <div className="gh-export-grid">
        {OPTIONS.map((o) => (
          <button
            key={o.id}
            type="button"
            className="gh-export-card"
            data-recommended={o.recommended ? "true" : "false"}
            data-submitting={submittingMethod === o.id ? "true" : "false"}
            disabled={submitting}
            onClick={() => onPick(o.id)}
          >
            <div className="ec-icon">{o.icon}</div>
            <div>
              <h3 className="ec-title">{o.title}</h3>
              <p className="ec-hint">{o.hint}</p>
            </div>
            <div className="ec-bottom">
              <span className="ec-go" aria-hidden="true">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M5 12h14" />
                  <path d="M13 5l7 7-7 7" />
                </svg>
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
