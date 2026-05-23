"use client";

import { Button } from "@/components/ui/button";
import { useSessionStore } from "@/lib/sessionStore";

export function GuidePane() {
  const procedure = useSessionStore((s) => s.procedure);
  const sendText = useSessionStore((s) => s.sendText);
  const transition = useSessionStore((s) => s.transitionRightPane);

  if (!procedure) return null;

  const stepLabels = procedure.fields
    .filter((f) => f.required)
    .map((f) => f.label);

  return (
    <article className="mx-auto max-w-2xl space-y-5 p-6">
      <header>
        <p className="text-xs uppercase tracking-wider text-muted-foreground">
          Pas curent · Ghid
        </p>
        <h2 className="mt-1 text-2xl font-semibold">{procedure.title}</h2>
        {procedure.description ? (
          <p className="mt-1 text-sm text-muted-foreground">
            {procedure.description}
          </p>
        ) : null}
      </header>

      <section>
        <h3 className="mb-2 text-sm font-medium">Ce vom face</h3>
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          {stepLabels.map((label) => (
            <li key={label}>{label}</li>
          ))}
          <li>Generăm PDF-ul gata de semnat</li>
        </ol>
      </section>

      {procedure.acte_necesare && procedure.acte_necesare.length > 0 ? (
        <section>
          <h3 className="mb-2 text-sm font-medium">
            Acte pe care să le ai la îndemână
          </h3>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {procedure.acte_necesare.map((a, i) => (
              <li key={i}>
                {a.denumire}
                {a.obligatoriu === false ? (
                  <span className="text-muted-foreground"> (opțional)</span>
                ) : null}
                {a.observatie ? (
                  <span className="text-muted-foreground"> — {a.observatie}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className="text-sm text-muted-foreground">
          Nu sunt acte fizice obligatorii pentru această procedură.
        </p>
      )}

      <div className="flex gap-2">
        <Button
          onClick={() => {
            transition({ kind: "filling" });
            void sendText("Da, continuă");
          }}
        >
          ✓ Continuă
        </Button>
        <Button
          variant="outline"
          onClick={() => void sendText("Vreau altceva, nu această procedură")}
        >
          Nu, vreau altceva
        </Button>
      </div>
    </article>
  );
}
