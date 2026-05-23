---
type: module
path: "backend/app/procedures.py"
status: active
language: python
purpose: "Procedure registry loader + RAG lookup endpoint."
depends_on: [db, embeddings, scenarios, security, models]
used_by: [agent_tools/lookup_procedure, agent_tools/list_procedures, documents, session_engine, reminders]
created: 2026-05-23
updated: 2026-05-23
---

# procedures

The catalog door. Loads all `backend/procedures/*.json` files at first call and caches them (`lru_cache(maxsize=1)`).

## Loader contract

```python
get_registry() -> dict[str, Procedure]
```

Validates that `proc.id == path.stem` for every JSON. Raises on mismatch — keeps filename and id in sync so [[start_procedure]] can use either.

## Routes

| Route | Returns | Notes |
|---|---|---|
| `GET /procedures` | `list[Procedure]` | Bulk catalog dump. Used by FE for the manual procedure picker. |
| `GET /procedures/{id}` | `ResolvedProcedure` | Same shape but `acte_necesare[]` enriched with institution names + AI-cannot-complete notes. See [[scenarios]]. |
| `POST /procedures/lookup` | `ProcedureLookupResponse` | RAG: embed the query, pgvector top-K, return matches. Falls back to keyword-based `redirect_candidate` (ANAF/CNAS/DRPCIV) when top score < 0.55. |

## Constants

```python
REDIRECT_THRESHOLD = 0.55      # below → suggest external institution
REDIRECT_HINTS = { "ANAF": [...], "CNAS": [...], "DRPCIV": [...] }
```

These hints are the **fallback** keyword detector — the agent uses `lookup_procedure` first, but `find_redirect` ([[find_redirect]]) and this endpoint both apply the same map when semantic scores are low.

## See also

- [[Flow Procedure Lookup]]
- [[Procedure JSON Schema]]
- [[lookup_procedure]] — the tool wrapper used by the agent
- [[embeddings]] — `embed_text` + `search_top_k`
