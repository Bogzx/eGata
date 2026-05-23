---
type: dependency
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Dep: Supabase

Hosted Postgres + Storage. Recommended region: EU (eu-central-1).

## Provides

| Service | Used for |
|---|---|
| **Postgres** | All app data: citizens, documents, ledger, reminders, sessions, otp_challenges, rag_entries, processed_events |
| **pgvector extension** | Embedding storage + cosine similarity search |
| **pgcrypto extension** | `gen_random_uuid()` for default UUIDs |
| **Storage** | `pdfs` public bucket — generated PDFs at `<citizen_uuid>/<doc_uuid>.pdf` |
| **RLS** | Defense in depth (the backend bypasses with service role) |

## Env vars

```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=<anon key>
SUPABASE_SERVICE_ROLE_KEY=<service role key>
SUPABASE_DB_URL=postgres://postgres:<pw>@db.<project>.supabase.co:5432/postgres
```

Backend uses **service role key** (see [[ADR Service Role Key + RLS Bypass]]).

## Setup steps

1. Create project in EU region.
2. Enable extensions in SQL editor: `create extension if not exists "vector";` `create extension if not exists "pgcrypto";`.
3. `python backend/scripts/apply_migrations.py` — runs the 8 migration SQL files in order.
4. `python backend/scripts/embed_procedures.py` — embeds the 22 procedures.
5. `python backend/scripts/index_rag.py` — embeds the scenarios.
6. First PDF upload auto-creates the `pdfs` bucket (`storage.create_bucket("pdfs", public=True)` with error suppressed).

## Connection model

[[db]]`.get_pg_connection()` opens a fresh psycopg connection per call. No pool. Acceptable for hackathon load; production should swap in `psycopg_pool.ConnectionPool` or pgbouncer.

## See also

- [[Database Schema]]
- [[Migrations]]
- [[ADR Service Role Key + RLS Bypass]]
