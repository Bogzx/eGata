---
type: module
path: "backend/app/agent_tools/lookup_procedure.py"
status: active
language: python
purpose: "Agent tool: RAG over procedures + scenarios."
depends_on: [embeddings, procedures, scenarios, sessions]
used_by: [session_engine, agent_voice, twilio_bridge]
valid_states: [EXPLORING, CONFIRMING_MATCH, DELIVERED, REDIRECTED]
created: 2026-05-23
updated: 2026-05-23
---

# lookup_procedure

The agent's main discovery tool. Embeds the user's query and pulls top-K matches across `procedures` AND `scenarios`.

## Parameters

```json
{ "query": "string (required)" }
```

## Behavior

1. `embed_text(query)` — 768-dim Gemini embedding.
2. `search_top_k_rag(emb, k=5)` — pgvector cosine across both kinds.
3. If top hit is `kind=scenario` AND score ≥ **0.55** → also build the `ScenarioPlan` via [[scenarios]]`.build_scenario_plan`.
4. Filter procedure matches; enrich each with `acte_necesare` via [[scenarios]]`.resolve_act`.
5. Threshold for transition: top score ≥ **0.45** OR scenario present → `transition_to=CONFIRMING_MATCH`. Otherwise stay in current state.

## Output

```json
{
  "matches": [{"procedure_id", "title", "score", "description", "acte_necesare"}],
  "scenario_plan": null | ScenarioPlan
}
```

Plus a `frontend_event: lookup_returned` carrying the same payload — so the right pane can render the matches list and (when present) the scenario plan immediately.

## Valid states

`EXPLORING, CONFIRMING_MATCH, DELIVERED, REDIRECTED`. Off during `FILLING / REVIEWING` so a mid-fill mention can't pivot the procedure.

## See also

- [[Flow Procedure Lookup]]
- [[embeddings]]
- [[procedures]]
- [[scenarios]]
