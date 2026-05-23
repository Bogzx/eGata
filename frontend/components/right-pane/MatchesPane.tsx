"use client";

import { useSessionStore } from "@/lib/sessionStore";
import { DocPane } from "./DocPane";

export function MatchesPane() {
  const matches = useSessionStore((s) => s.lookupMatches);
  const startProcedure = useSessionStore((s) => s.startProcedure);

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

  const others = matches.slice(1);
  const countLabel =
    matches.length === 1 ? "1 procedură găsită" : `${matches.length} proceduri găsite`;

  return (
    <DocPane eyebrow={countLabel} title={top.title}>
      <article className="space-y-5">
        {top.description ? (
          <p className="text-sm" style={{ color: "var(--c-ink-soft)" }}>
            {top.description}
          </p>
        ) : null}

        {top.acte_necesare && top.acte_necesare.length > 0 ? (
          <section>
            <h3 className="docpane-eyebrow" style={{ marginBottom: "10px" }}>
              Acte pe care să le ai la îndemână
            </h3>
            <ul className="space-y-2 text-sm">
              {top.acte_necesare.map((a, i) => (
                <li
                  key={`${a.denumire}-${i}`}
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
                        background: "rgba(255, 165, 0, 0.18)",
                        color: "var(--c-dark)",
                      }}
                      title="Acest document trebuie obținut de la o altă instituție — eGata nu îl poate genera."
                    >
                      📥 De la altă instituție: {a.institutie_nume}
                    </span>
                  ) : a.emitent === "primarie" ? (
                    <span
                      className="mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium"
                      style={{
                        background: "rgba(47, 160, 132, 0.18)",
                        color: "var(--c-dark)",
                      }}
                      title="Document emis de Primăria Cluj-Napoca — completat în această aplicație."
                    >
                      🏛️ Emis de Primăria Cluj-Napoca
                    </span>
                  ) : a.emitent === "user" ? (
                    <span
                      className="mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium"
                      style={{
                        background: "rgba(120, 120, 120, 0.18)",
                        color: "var(--c-dark)",
                      }}
                      title="Document pe care îl ai deja (CI, acte personale)."
                    >
                      👤 Ai tu (acte personale)
                    </span>
                  ) : a.emitent === "extern" ? (
                    <span
                      className="mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium"
                      style={{
                        background: "rgba(255, 165, 0, 0.18)",
                        color: "var(--c-dark)",
                      }}
                      title="Document obținut din afara aplicației (chitanță, document terț)."
                    >
                      📥 Din afara aplicației
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
                </li>
              ))}
            </ul>
          </section>
        ) : (
          <p className="text-sm" style={{ color: "var(--c-ink-soft)" }}>
            Nu sunt acte fizice obligatorii pentru această procedură.
          </p>
        )}

        <div className="flex justify-end">
          <button
            type="button"
            className="civic-btn civic-btn-primary"
            onClick={() => void startProcedure(top.procedure_id)}
          >
            Începe „{top.title}&rdquo;
          </button>
        </div>

        {others.length > 0 ? (
          <section>
            <h3 className="docpane-eyebrow" style={{ marginBottom: "10px" }}>
              Alte potriviri
            </h3>
            <ul className="space-y-2 text-sm">
              {others.map((m) => (
                <li
                  key={m.procedure_id}
                  className="flex items-start justify-between gap-3 rounded-lg border p-3"
                  style={{
                    borderColor: "var(--c-line)",
                    background: "var(--c-bg)",
                  }}
                >
                  <div>
                    <p className="font-medium">{m.title}</p>
                    {m.description ? (
                      <p
                        className="mt-1 text-xs"
                        style={{ color: "var(--c-ink-soft)" }}
                      >
                        {m.description}
                      </p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className="civic-btn civic-btn-ghost"
                    onClick={() => void startProcedure(m.procedure_id)}
                  >
                    Începe
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </article>
    </DocPane>
  );
}
