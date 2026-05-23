---
type: contract
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Scenario JSON Schema

`backend/scenarios/*.json` files. Loaded by [[scenarios]]`.get_scenarios_registry`. Validated by Pydantic `Scenario` model.

## Shape

```yaml
id: "cumparare-apartament"          # must equal filename
title: "Cumpărare apartament"
description: "Plan complet după cumpărarea unui apartament în Cluj-Napoca."
summary_for_rag: "După cumpărarea unui apartament trebuie să-ți schimbi domiciliul, ..."
synonyms: ["am cumpărat apartament", "mutare după cumpărare"]
sample_queries: ["m-am mutat după ce mi-am luat apartament", ...]
complexitate: "ridicată"
termen_total: "30-60 zile"
applies_if: "owns_property == true"  # optional — scenario only surfaces when condition holds

in_scope_steps:                      # procedures we can complete in-app
  - ordine: 1
    procedure_id: "schimbare-domiciliu"
    deadline_days: 15
    note: "..."

external_steps:                      # institutions we redirect to
  - ordine: 4
    institutie_id: "anaf"            # references institutions/<id>.json
    obligatoriu: true
    note: "Notifică ANAF în 30 zile."
```

## Resolution

`build_scenario_plan(id)` ([[scenarios]]) returns a `ScenarioPlan`:

- `in_scope_steps[]` enriched with `procedure_title` + `acte_necesare` (each act resolved via `resolve_act`).
- `external_steps[]` enriched with `institutie_nume`, `scope`, `url`, `phone`, `note_ai_cannot_complete`.

## How a scenario surfaces

1. [[lookup_procedure]] embeds the user query and finds the scenario among the top hits.
2. If `top.kind == "scenario"` AND `top.score >= 0.55` → build the plan, include it in the tool output.
3. The agent summarizes briefly (prompt rule 13).
4. The FE renders the plan in `PlanPane`.

## See also

- [[scenarios]]
- [[institutions]]
- [[Flow Procedure Lookup]]
