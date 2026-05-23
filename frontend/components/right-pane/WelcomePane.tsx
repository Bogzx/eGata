"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";
import type {
  CitizenAttributes,
  Procedure,
  Reminder,
  ScenarioSummary,
} from "@/lib/types";

function filterProcedures(
  procs: Procedure[],
  attrs: CitizenAttributes,
): Procedure[] {
  const out: Procedure[] = [];
  const seenCategories = new Set<string>();
  for (const p of procs) {
    if (p.category.includes("vehicul") && attrs.owns_vehicle === false) continue;
    if (p.category.includes("copii") && attrs.has_children === false) continue;
    if (seenCategories.has(p.category)) continue;
    seenCategories.add(p.category);
    out.push(p);
    if (out.length >= 2) break;
  }
  return out;
}

function filterScenarios(
  scenarios: ScenarioSummary[],
  attrs: CitizenAttributes,
): ScenarioSummary[] {
  return scenarios
    .filter((s) => {
      if (!s.applies_if) return true;
      const m = /^(\w+)\s*==\s*(true|false)$/.exec(s.applies_if.trim());
      if (!m) return true;
      const [, key, val] = m;
      const expected = val === "true";
      const actual = (attrs as Record<string, unknown>)[key];
      return actual === expected;
    })
    .slice(0, 2);
}

export function WelcomePane() {
  const citizen = useSessionStore((s) => s.citizen);
  const startProcedure = useSessionStore((s) => s.startProcedure);
  const openScenarioPlan = useSessionStore((s) => s.openScenarioPlan);
  const openDrawer = useSessionStore((s) => s.openDrawer);
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void Promise.all([
      api.listProcedures().catch(() => [] as Procedure[]),
      api.listScenarios().catch(() => [] as ScenarioSummary[]),
      api.listReminders().catch(() => [] as Reminder[]),
    ]).then(([p, s, r]) => {
      setProcedures(p);
      setScenarios(s);
      setReminders(r);
      setLoading(false);
    });
  }, []);

  const pendingReminders = reminders.filter((r) => r.status === "pending");
  const attrs = citizen?.attributes ?? {};
  const procSuggestions = filterProcedures(procedures, attrs);
  const scenarioSuggestions = filterScenarios(scenarios, attrs);

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center gap-5 p-6 text-center">
      <Sparkles className="text-primary" size={36} aria-hidden />
      <h2 className="text-2xl font-semibold">
        Bună{citizen?.prenume ? `, ${citizen.prenume}` : ""}. Cu ce te pot ajuta?
      </h2>
      <p className="text-sm text-muted-foreground">
        Spune-mi în cuvinte simple ce ai nevoie — eu mă ocup de hârtii.
      </p>

      <div className="flex flex-wrap justify-center gap-2 pt-2">
        {pendingReminders.length > 0 ? (
          <Button variant="secondary" size="sm" onClick={() => openDrawer()}>
            🔔 Ai {pendingReminders.length}{" "}
            {pendingReminders.length === 1
              ? "amintire activă"
              : "amintiri active"}
          </Button>
        ) : null}
        {scenarioSuggestions.map((s) => (
          <Button
            key={s.id}
            variant="secondary"
            size="sm"
            onClick={() => void openScenarioPlan(s.id)}
          >
            📋 {s.title}
          </Button>
        ))}
        {procSuggestions.map((p) => (
          <Button
            key={p.id}
            variant="outline"
            size="sm"
            onClick={() => void startProcedure(p.id)}
          >
            💡 {p.title}
          </Button>
        ))}
      </div>

      {loading && procedures.length === 0 && scenarios.length === 0 ? (
        <Card className="mt-4">
          <CardContent className="p-4 text-sm text-muted-foreground">
            Se încarcă procedurile…
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
