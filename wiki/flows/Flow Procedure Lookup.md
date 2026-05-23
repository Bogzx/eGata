---
type: flow
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Flow: Procedure Lookup

How a Romanian phrase becomes a procedure (or scenario) match.

## Two API surfaces

1. **`POST /procedures/lookup`** ([[procedures]]) — legacy HTTP route still used by the FE's "manual procedure picker" page.
2. **`lookup_procedure` tool** ([[lookup_procedure]]) — the agent-callable version. Adds scenario detection + frontend events.

Both share [[embeddings]].

## Pipeline

```
"vreau să-mi schimb domiciliul"
        │
        ▼
embed_text  → 768-dim vector  ── Gemini API
        │
        ▼
SELECT id, kind, 1 - (embedding <=> %s::vector) AS score
FROM rag_entries
ORDER BY embedding <=> %s::vector ASC
LIMIT 5;
        │
        ▼
[ {id: schimbare-domiciliu,  kind: procedure, score: 0.81 },
  {id: cumparare-apartament, kind: scenario,  score: 0.62 }, ... ]
        │
        ├── Top hit is scenario AND score ≥ 0.55 → build_scenario_plan
        │
        └── Filter procedure entries → enrich with resolve_act
                          │
                          ▼
                    matches: [{procedure_id, title, score, description, acte_necesare}]
                    scenario_plan: ScenarioPlan | null
```

## Thresholds

| Threshold | Where | Meaning |
|---|---|---|
| 0.45 | `lookup_procedure.MATCH_THRESHOLD` | Top score ≥ this → transition to CONFIRMING_MATCH |
| 0.55 | `lookup_procedure.SCENARIO_THRESHOLD` | Scenario hit must beat this to be surfaced |
| 0.55 | `procedures.REDIRECT_THRESHOLD` | Legacy HTTP: below → suggest redirect candidate |

## Index population

`scripts/embed_procedures.py` (and `scripts/index_rag.py` for scenarios) run at deploy/seed time. Re-run when JSONs change. The script reads each file, computes `procedure_source_text` / `scenario_source_text` (title + description + synonyms + sample_queries), embeds, and `upsert_rag_entry`s.

## Redirect fallback

When the HTTP `lookup` finds no confident procedure (top score < 0.55), it runs `guess_redirect_target(query)` — a tiny regex over the same `REDIRECT_HINTS` map as `find_redirect`. Adds `redirect_candidate: "ANAF"` to the response so the FE can render a redirect card without calling another endpoint.

## See also

- [[lookup_procedure]] — tool
- [[procedures]] — HTTP route
- [[embeddings]]
- [[scenarios]]
- [[find_redirect]]
