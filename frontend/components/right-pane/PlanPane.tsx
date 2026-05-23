"use client";

import { useSessionStore } from "@/lib/sessionStore";
import { DocPane } from "./DocPane";

export function PlanPane() {
  const plan = useSessionStore((s) => s.scenarioPlan);
  const startProcedure = useSessionStore((s) => s.startProcedure);

  if (!plan) {
    return (
      <DocPane eyebrow="Plan multi-pas" title="Se încarcă…">
        <p className="text-sm" style={{ color: "var(--c-ink-soft)" }}>
          Se încarcă planul…
        </p>
      </DocPane>
    );
  }

  return (
    <DocPane
      eyebrow="Plan multi-pas"
      title={plan.title}
      refNumber={plan.scenario_id.toUpperCase()}
    >
      <article className="space-y-5">
        <p className="text-sm" style={{ color: "var(--c-ink-soft)" }}>
          {plan.summary}
        </p>
        <div className="flex flex-wrap gap-3 text-xs">
          {plan.complexitate ? (
            <span
              className="rounded-full px-3 py-1"
              style={{
                background: "rgba(47, 160, 132, 0.12)",
                color: "var(--c-dark)",
              }}
            >
              Complexitate: {plan.complexitate}
            </span>
          ) : null}
          {plan.termen_total ? (
            <span
              className="rounded-full px-3 py-1"
              style={{
                background: "rgba(47, 160, 132, 0.12)",
                color: "var(--c-dark)",
              }}
            >
              Termen total: {plan.termen_total}
            </span>
          ) : null}
        </div>

        <section>
          <h3 className="docpane-eyebrow" style={{ marginBottom: "10px" }}>
            Ce pot completa eu pentru tine
          </h3>
          <ol className="space-y-3">
            {plan.in_scope_steps.map((step) => (
              <li
                key={step.procedure_id}
                className="flex items-start justify-between gap-3 rounded-lg border p-3"
                style={{
                  borderColor: "var(--c-line)",
                  background: "var(--c-bg)",
                }}
              >
                <div>
                  <p className="font-medium">
                    {step.ordine}. {step.procedure_title}
                  </p>
                  {step.deadline_days ? (
                    <p
                      className="text-xs"
                      style={{ color: "var(--c-ink-soft)" }}
                    >
                      Termen: {step.deadline_days} zile
                    </p>
                  ) : null}
                  {step.note ? (
                    <p
                      className="text-xs"
                      style={{ color: "var(--c-ink-soft)" }}
                    >
                      {step.note}
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="civic-btn civic-btn-primary"
                  onClick={() => void startProcedure(step.procedure_id)}
                >
                  Începe acum
                </button>
              </li>
            ))}
          </ol>
        </section>

        {plan.external_steps.length > 0 ? (
          <section>
            <h3 className="docpane-eyebrow" style={{ marginBottom: "10px" }}>
              Ce trebuie să faci tu (extern)
            </h3>
            <ul className="space-y-3">
              {plan.external_steps.map((step) => (
                <li
                  key={step.institutie_id}
                  className="rounded-lg border border-dashed p-3"
                  style={{ borderColor: "var(--c-line)" }}
                >
                  <p className="font-medium">{step.institutie_nume}</p>
                  {step.note ? (
                    <p
                      className="text-xs"
                      style={{ color: "var(--c-ink-soft)" }}
                    >
                      {step.note}
                    </p>
                  ) : null}
                  <div
                    className="mt-1 flex flex-wrap gap-3 text-xs"
                    style={{ color: "var(--c-ink-soft)" }}
                  >
                    {step.phone ? <span>📞 {step.phone}</span> : null}
                    {step.url ? (
                      <a
                        href={step.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline"
                        style={{ color: "var(--c-dark)" }}
                      >
                        🌐 {step.url}
                      </a>
                    ) : null}
                  </div>
                  {step.note_ai_cannot_complete ? (
                    <p
                      className="mt-2 text-xs italic"
                      style={{ color: "var(--c-ink-soft)" }}
                    >
                      {step.note_ai_cannot_complete}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </article>
    </DocPane>
  );
}
