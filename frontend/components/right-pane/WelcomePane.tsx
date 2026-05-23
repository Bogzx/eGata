"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/sessionStore";
import type {
  CitizenAttributes,
  Procedure,
  Reminder,
  ScenarioSummary,
} from "@/lib/types";

type Suggestion = {
  key: string;
  kind: "scenario" | "procedure" | "reminder";
  id: string;
  icon: string;
  title: string;
  hint: string;
};

const ICON_BY_CATEGORY: Record<string, string> = {
  acte: "🪪",
  domiciliu: "🏠",
  fiscal: "🧾",
  venit: "📄",
  scolarizare: "🎓",
  copii: "👶",
  vehicul: "🚗",
  sanatate: "🩺",
};

function iconFor(category: string): string {
  for (const [key, ico] of Object.entries(ICON_BY_CATEGORY)) {
    if (category.includes(key)) return ico;
  }
  return "📋";
}

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
    if (out.length >= 3) break;
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
      if (!key) return true;
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
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);

  useEffect(() => {
    void Promise.all([
      api.listProcedures().catch(() => [] as Procedure[]),
      api.listScenarios().catch(() => [] as ScenarioSummary[]),
      api.listReminders().catch(() => [] as Reminder[]),
    ]).then(([p, s, r]) => {
      setProcedures(p);
      setScenarios(s);
      setReminders(r);
    });
  }, []);

  const attrs = citizen?.attributes ?? {};
  const suggestions = useMemo<Suggestion[]>(() => {
    const out: Suggestion[] = [];
    const pendingReminders = reminders.filter((r) => r.status === "pending");
    for (const r of pendingReminders.slice(0, 1)) {
      out.push({
        key: `reminder-${r.id}`,
        kind: "reminder",
        id: r.id,
        icon: "🔔",
        title: r.title,
        hint: r.due_date
          ? `Termen: ${new Date(r.due_date).toLocaleDateString("ro-RO")}`
          : "Amintire activă",
      });
    }
    for (const s of filterScenarios(scenarios, attrs)) {
      out.push({
        key: `scenario-${s.id}`,
        kind: "scenario",
        id: s.id,
        icon: "📋",
        title: s.title,
        hint: s.description ?? "Plan pas cu pas",
      });
    }
    for (const p of filterProcedures(procedures, attrs)) {
      out.push({
        key: `procedure-${p.id}`,
        kind: "procedure",
        id: p.id,
        icon: iconFor(p.category),
        title: p.title,
        hint: p.description ?? "Pornește această procedură",
      });
    }
    return out.slice(0, 4);
  }, [reminders, scenarios, procedures, attrs]);

  function handleClick(s: Suggestion) {
    if (s.kind === "scenario") void openScenarioPlan(s.id);
    else if (s.kind === "procedure") void startProcedure(s.id);
    else if (s.kind === "reminder") {
      void api.startReminder(s.id).then((out) => {
        void useSessionStore.getState().loadDocument(out.document_id);
      });
    }
  }

  const prenume = citizen?.prenume ?? "";

  return (
    <div className="welcome">
      <div className="welcome-pill">
        <span className="dot dot-pulse" aria-hidden="true" />
        Asistent CivicAI · ROeID activă
      </div>
      <h2 className="hello">
        Bună{prenume ? `, ${prenume}` : ""}.
        <br />
        <span className="hello-soft">Cu ce te pot ajuta astăzi?</span>
      </h2>
      <p className="welcome-sub">
        Spune-mi în cuvinte simple ce ai nevoie. Eu îți spun ce acte îți trebuie
        — și le completez cu tine.
      </p>

      {suggestions.length > 0 ? (
        <div
          className="suggest-grid"
          role="list"
          aria-label="Proceduri sugerate"
        >
          {suggestions.map((s) => (
            <button
              type="button"
              key={s.key}
              className="suggest-card"
              onClick={() => handleClick(s)}
              role="listitem"
            >
              <span className="suggest-icon" aria-hidden="true">
                {s.icon}
              </span>
              <span className="suggest-body">
                <span className="suggest-title">{s.title}</span>
                <span className="suggest-hint">{s.hint}</span>
              </span>
              <svg
                className="suggest-arrow"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
                focusable="false"
              >
                <path d="M5 12h14M13 5l7 7-7 7" />
              </svg>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
