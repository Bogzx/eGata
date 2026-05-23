---
type: module
path: "backend/app/db.py"
status: active
language: python
purpose: "Supabase client + psycopg connection factory."
depends_on: [config]
used_by: "every module that touches the database"
created: 2026-05-23
updated: 2026-05-23
---

# db

Two factories. That's the whole file.

## `get_supabase() → Client`

`lru_cache(maxsize=1)`. Returns a Supabase Python client built with the **service role key**. Used for Storage uploads ([[storage]]) and any future Supabase Auth metadata.

> [!key-insight] Service role bypasses RLS
> The backend has full access to all rows. [[ADR Service Role Key + RLS Bypass]] explains why and what RLS still gives us.

## `get_pg_connection() → psycopg.Connection[dict[str, Any]]`

Opens a **fresh psycopg connection** per call, with `row_factory=dict_row`. Used as `with get_pg_connection() as conn, conn.cursor() as cur:` everywhere.

> [!gotcha] No connection pool yet
> Every request opens a new TCP/TLS connection to Supabase. Fine for hackathon load; in production swap for `psycopg_pool.ConnectionPool` or pgbouncer. Search the repo for `get_pg_connection()` to find all 30+ call sites.

## See also

- [[Database Schema]] — every table + view + function
- [[Dep Supabase]]
