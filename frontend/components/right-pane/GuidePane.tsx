"use client";

import { useSessionStore } from "@/lib/sessionStore";
import { DocPane } from "./DocPane";

export function GuidePane() {
  const procedure = useSessionStore((s) => s.procedure);
  const sendText = useSessionStore((s) => s.sendText);
  const transition = useSessionStore((s) => s.transitionRightPane);

  if (!procedure) return null;

  const stepLabels = procedure.fields
    .filter((f) => f.required)
    .map((f) => f.label);

  return (
    <DocPane
      eyebrow="Pas curent · Ghid"
      title={procedure.title}
      refNumber={procedure.id.slice(0, 8).toUpperCase()}
      actions={
        <>
          <button
            type="button"
            className="civic-btn civic-btn-ghost"
            onClick={() =>
              void sendText("Vreau altceva, nu această procedură")
            }
          >
            Nu, vreau altceva
          </button>
          <button
            type="button"
            className="civic-btn civic-btn-primary"
            onClick={() => {
              transition({ kind: "filling" });
              void sendText("Da, continuă");
            }}
          >
            ✓ Continuă
          </button>
        </>
      }
    >
      <article className="space-y-5">
        {procedure.description ? (
          <p className="text-sm" style={{ color: "var(--c-ink-soft)" }}>
            {procedure.description}
          </p>
        ) : null}

        <section>
          <h3 className="docpane-eyebrow" style={{ marginBottom: "10px" }}>
            Ce vom face
          </h3>
          <ol className="list-decimal space-y-1.5 pl-5 text-sm">
            {stepLabels.map((label) => (
              <li key={label}>{label}</li>
            ))}
            <li>Generăm PDF-ul gata de semnat</li>
          </ol>
        </section>

        {procedure.acte_necesare && procedure.acte_necesare.length > 0 ? (
          <section>
            <h3 className="docpane-eyebrow" style={{ marginBottom: "10px" }}>
              Acte pe care să le ai la îndemână
            </h3>
            <ul className="space-y-2 text-sm">
              {procedure.acte_necesare.map((a, i) => (
                <li
                  key={i}
                  className="rounded-lg border p-3"
                  style={{
                    borderColor: "var(--c-line)",
                    background: "var(--c-bg)",
                  }}
                >
                  <p className="font-medium">
                    {a.denumire}
                    {a.obligatoriu === false ? (
                      <span
                        className="ml-1 text-xs"
                        style={{ color: "var(--c-ink-soft)" }}
                      >
                        (opțional)
                      </span>
                    ) : null}
                  </p>
                  {a.institutie_nume ? (
                    <span
                      className="mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium"
                      style={{
                        background: "rgba(47, 160, 132, 0.14)",
                        color: "var(--c-dark)",
                      }}
                    >
                      ↗ {a.institutie_nume}
                    </span>
                  ) : null}
                  {a.observatie ? (
                    <p
                      className="mt-1 text-xs"
                      style={{ color: "var(--c-ink-soft)" }}
                    >
                      {a.observatie}
                    </p>
                  ) : null}
                  {a.note_ai_cannot_complete ? (
                    <p
                      className="mt-1 text-xs italic"
                      style={{ color: "var(--c-ink-soft)" }}
                    >
                      {a.note_ai_cannot_complete}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ) : (
          <p className="text-sm" style={{ color: "var(--c-ink-soft)" }}>
            Nu sunt acte fizice obligatorii pentru această procedură.
          </p>
        )}
      </article>
    </DocPane>
  );
}
