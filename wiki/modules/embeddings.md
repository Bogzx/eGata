---
type: module
path: "backend/app/embeddings.py"
status: active
language: python
purpose: "Gemini embeddings + pgvector retrieval."
depends_on: [config, db, models]
used_by: [procedures, agent_tools/lookup_procedure, scripts/embed_procedures.py, scripts/index_rag.py]
created: 2026-05-23
updated: 2026-05-23
---

# embeddings

The RAG layer. Embed text with Gemini `gemini-embedding-001` (768-dim output), store in `rag_entries`, query with pgvector cosine distance.

## Functions

| Function | Use |
|---|---|
| `embed_text(text) → list[float]` | One-off embedding, called at query time |
| `procedure_source_text(proc) → str` | Title + description + synonyms + sample queries joined by newlines |
| `scenario_source_text(sc) → str` | Authored `summary_for_rag` + synonyms + sample queries |
| `cosine_similarity(a, b) → float` | Pure-Python, used in unit tests; production uses pgvector's `<=>` |
| `upsert_rag_entry(id, kind, source_text, embedding)` | Insert or update a `rag_entries` row |
| `upsert_procedure_embedding(...)` | Back-compat shim around `upsert_rag_entry` |
| `search_top_k_rag(query_embedding, k=5) → list` | Returns `{id, kind, score}` across both kinds |
| `search_top_k(query_embedding, k=3) → list` | Procedures-only filter (back-compat) |

## How a query becomes results

```
query string
   │
   ▼
embed_text  ── Gemini API call
   │
   ▼
[768-dim vector]
   │
   ▼
SELECT id, kind, 1 - (embedding <=> %s::vector) AS score
FROM rag_entries
ORDER BY embedding <=> %s::vector ASC
LIMIT k;
```

`1 - cosine_distance` gives cosine similarity in `[0, 1]` — same scale [[lookup_procedure]] thresholds against.

## Two thresholds

- `lookup_procedure.MATCH_THRESHOLD = 0.45` — below: stay EXPLORING (no confident procedure match).
- `lookup_procedure.SCENARIO_THRESHOLD = 0.55` — the top hit must beat this AND be `kind=scenario` to trigger a scenario plan.
- `procedures.REDIRECT_THRESHOLD = 0.55` — used by the legacy `POST /procedures/lookup` route to decide whether to suggest a redirect candidate.

## Pre-indexing

`scripts/embed_procedures.py` runs at deploy/seed time and calls `upsert_procedure_embedding` for every procedure JSON. `scripts/index_rag.py` indexes scenarios too. Re-run when JSONs change.

## See also

- [[Database Schema]] — `rag_entries` table and indexes
- [[Dep Gemini]]
- [[Flow Procedure Lookup]]
