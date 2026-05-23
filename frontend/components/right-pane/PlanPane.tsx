"use client";

import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/sessionStore";

export function PlanPane() {
  const plan = useSessionStore((s) => s.scenarioPlan);
  const startProcedure = useSessionStore((s) => s.startProcedure);

  if (!plan) {
    return (
      <p className="p-6 text-sm text-muted-foreground">Se încarcă planul…</p>
    );
  }

  return (
    <article className="mx-auto max-w-2xl space-y-6 p-6">
      <header>
        <p className="text-xs uppercase tracking-wider text-muted-foreground">
          Plan multi-pas
        </p>
        <h2 className="mt-1 text-2xl font-semibold">{plan.title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{plan.summary}</p>
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
          {plan.complexitate ? <span>Complexitate: {plan.complexitate}</span> : null}
          {plan.termen_total ? <span>Termen total: {plan.termen_total}</span> : null}
        </div>
      </header>

      <section>
        <h3 className="mb-2 text-sm font-medium">
          ✅ Ce pot completa eu pentru tine
        </h3>
        <ol className="space-y-3">
          {plan.in_scope_steps.map((step) => (
            <li
              key={step.procedure_id}
              className="flex items-start justify-between gap-3 rounded-lg border p-3"
            >
              <div>
                <p className="font-medium">
                  {step.ordine}. {step.procedure_title}
                </p>
                {step.deadline_days ? (
                  <p className="text-xs text-muted-foreground">
                    Termen: {step.deadline_days} zile
                  </p>
                ) : null}
                {step.note ? (
                  <p className="text-xs text-muted-foreground">{step.note}</p>
                ) : null}
              </div>
              <Button
                size="sm"
                onClick={() => void startProcedure(step.procedure_id)}
              >
                Începe acum
              </Button>
            </li>
          ))}
        </ol>
      </section>

      {plan.external_steps.length > 0 ? (
        <section>
          <h3 className="mb-2 text-sm font-medium">
            ↗ Ce trebuie să faci tu (extern)
          </h3>
          <ul className="space-y-3">
            {plan.external_steps.map((step) => (
              <li
                key={step.institutie_id}
                className="rounded-lg border border-dashed p-3"
              >
                <p className="font-medium">{step.institutie_nume}</p>
                {step.note ? (
                  <p className="text-xs text-muted-foreground">{step.note}</p>
                ) : null}
                <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
                  {step.phone ? <span>📞 {step.phone}</span> : null}
                  {step.url ? (
                    <a
                      href={step.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline"
                    >
                      🌐 {step.url}
                    </a>
                  ) : null}
                </div>
                {step.note_ai_cannot_complete ? (
                  <p className="mt-2 text-xs italic text-muted-foreground">
                    {step.note_ai_cannot_complete}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}
