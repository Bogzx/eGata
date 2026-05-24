"use client";

import type { ExportMethod } from "@/lib/ghiseuStore";
import { useSessionStore } from "@/lib/sessionStore";
import { CheckIcon, MicIcon } from "./icons";

type Props = {
  method: Exclude<ExportMethod, null>;
  onRestart: () => void;
};

const METHOD_LABEL: Record<Exclude<ExportMethod, null>, string> = {
  city: "trimis direct la primărie",
  email: "trimis pe email",
};

const REF_FALLBACK = "REG-PENDING";

export function DoneScreen({ method, onRestart }: Props) {
  const methodLabel = METHOD_LABEL[method];
  const refNumber = useSessionStore(
    (s) => s.document?.ref_number ?? REF_FALLBACK,
  );
  return (
    <div className="gh-stage">
      <div className="gh-done-check" aria-hidden="true">
        <CheckIcon size={64} />
      </div>
      <div className="gh-status">
        <h2 className="gh-status-text">
          Gata. Cererea a fost {methodLabel}.
        </h2>
        <p className="gh-status-hint">
          Număr de înregistrare:{" "}
          <strong
            style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.04em" }}
          >
            {refNumber}
          </strong>{" "}
          · Vei primi confirmarea pe email.
        </p>
      </div>
      <button type="button" className="gh-cta" onClick={onRestart}>
        <MicIcon size={18} />
        Începe o nouă conversație
      </button>
    </div>
  );
}
