---
type: module
path: "backend/app/agent_tools/list_procedures.py"
status: active
language: python
purpose: "Agent tool: catalog browse — categories or drill-in."
depends_on: [procedures, sessions]
used_by: [session_engine]
valid_states: [EXPLORING, CONFIRMING_MATCH, DELIVERED, REDIRECTED]
created: 2026-05-23
updated: 2026-05-23
---

# list_procedures

The "what can you help me with?" tool. `lookup_procedure` is for "I need X"; this is for "what is X-shaped catalog like?".

## Parameters

```json
{ "category": "string (optional)" }
```

## Behavior

- **No arg**: returns category summaries — `{category, label, count, procedures}` for each of 10 categories (asistenta-sociala, dizabilitati, ecologie-spatii-verzi, evidenta-persoanelor, fiscalitate-locala, parcare, premii-evenimente, siguranta-circulatiei, stare-civila, urbanism-constructii). The agent prompt rule 2a says: present only category names (max 10 words), not all 26 procedures.
- **With `category=<slug>` (or human label)**: drill-in. Returns `{category, label, procedures, count}` — all procedures in that category. The prompt rule 2b says: enumerate all titles.

## Tolerant category matching

`_resolve_category(arg, available_slugs)`:

1. Exact slug match.
2. Normalized label match (strips Romanian diacritics).
3. Substring on label.
4. Substring on slug.

So `"urbanism"`, `"Urbanism"`, `"construcții"` all resolve to `urbanism-constructii`. Bad input returns an `available_categories` list so the agent can recover gracefully.

## See also

- [[lookup_procedure]] — semantic search counterpart
- [[procedures]]
