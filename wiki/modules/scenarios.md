---
type: module
path: "backend/app/scenarios.py"
status: active
language: python
purpose: "Scenario catalog + multi-procedure plan builder."
depends_on: [institutions, procedures, models]
used_by: [agent_tools/lookup_procedure, agent_tools/start_procedure (DELIVERED→FILLING), frontend right-pane PlanPane]
created: 2026-05-23
updated: 2026-05-23
---

# scenarios

A *scenario* is a real-life situation that requires several procedures and external steps. Example: "buying an apartment" requires a `schimbare-domiciliu`, a `declarare-cladire`, a `preschimbare-ci`, plus visits to ANCPI, ANAF, DRPCIV.

Files: `backend/scenarios/*.json` ([[Scenario JSON Schema]]).

## Routes

| Route | Returns | Notes |
|---|---|---|
| `GET /scenarios` | `list[ScenarioSummary]` | Lightweight summaries for the catalog UI. |
| `GET /scenarios/{id}` | `ScenarioPlan` | Full plan with resolved procedure titles, `acte_necesare` enriched with institution names, and external steps enriched with phone / URL / "AI cannot complete" notes. |

## Key helper: `resolve_act(act)`

Returns `ResolvedActeNecesareItem`. If `act.emitent_id` is set, looks up the [[institutions]] registry and attaches `institutie_nume` + `note_ai_cannot_complete`. The latter tells the agent "I can't get this for you — you have to go yourself."

`resolve_act` is also used by [[procedures]]`.get_procedure` to enrich the single-procedure response.

## How a scenario gets surfaced

1. [[lookup_procedure]] embeds the query and does `search_top_k_rag(k=5)`.
2. If the top hit is `kind=="scenario"` with score ≥ 0.55, it calls `build_scenario_plan(id)` and includes it in the tool result.
3. The agent text-summarises ("Plan pentru cumpărare apartament: 3 cereri la primărie și 3 pași externi.") — see prompt rule 13 in [[prompts]].
4. The frontend renders the plan in the right pane (`PlanPane`).
5. When the user picks a step, the FE calls `start_procedure` with that procedure's id.

## See also

- [[Scenario JSON Schema]]
- [[institutions]]
- [[Flow Procedure Lookup]]
