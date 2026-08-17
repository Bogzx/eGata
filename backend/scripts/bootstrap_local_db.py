"""Bring a database up to the schema the app expects, then seed it.

Used by the `migrate` service in docker-compose so `docker compose up` gives a
stranger a working stack with no Supabase project, and by CI to set up the
Postgres the ledger integration tests run against.

Re-runnable. `migrations/*.sql` were written assuming a one-shot run against a
fresh Supabase project — 001 has bare `create table`, 007 renames a table, 002
inserts rows with literal ids — so a second pass used to fail in three
different ways. A `schema_migrations` table records what has been applied and
each file runs exactly once.

Two things happen here that `apply_migrations.py` alone could not:

1. `migrations/004_rls_policies.sql` calls `auth.uid()`, which only exists on
   Supabase. On a plain server we install a stub returning NULL first, so the
   policies apply. They are inert either way — the backend connects as the
   owner and bypasses RLS (see the README's security note).
2. It reports what is and is not usable offline, because the honest answer is
   "everything except the agent chat, which needs an Azure OpenAI key".
"""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg

from app.config import get_settings

MIG_DIR = Path(__file__).resolve().parents[1] / "migrations"

LEDGER_TABLE = """
create table if not exists schema_migrations (
  filename   text primary key,
  applied_at timestamptz not null default now()
);
"""

AUTH_SHIM = """
create schema if not exists auth;
create or replace function auth.uid() returns uuid as $$
  select null::uuid;
$$ language sql stable;
comment on function auth.uid() is
  'Local stub so 004_rls_policies.sql applies off Supabase. Always NULL, so
   every RLS policy denies — which is moot, the backend connects as owner.';
"""

# Migrations that predate schema_migrations. If the schema is already there
# but the tracking table is not, these are recorded as done rather than
# re-run (which would fail on duplicate tables / rows / a missing rename).
PRE_TRACKING = [
    "001_initial_schema.sql",
    "002_seed_data.sql",
    "003_ledger_function.sql",
    "004_rls_policies.sql",
    "005_processed_events.sql",
    "006_seed_reminders.sql",
    "007_rag_entries.sql",
    "008_sessions.sql",
]


def _table_exists(cur: psycopg.Cursor, name: str) -> bool:
    cur.execute("select to_regclass(%s) is not null as ok;", (f"public.{name}",))
    row = cur.fetchone()
    return bool(row and row[0])


def _has_supabase_auth(cur: psycopg.Cursor) -> bool:
    cur.execute(
        "select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
        "where n.nspname = 'auth' and p.proname = 'uid' limit 1;"
    )
    return cur.fetchone() is not None


def _applied(cur: psycopg.Cursor) -> set[str]:
    cur.execute("select filename from schema_migrations;")
    return {r[0] for r in cur.fetchall()}


def _count(cur: psycopg.Cursor, table: str) -> int:
    if not _table_exists(cur, table):
        return 0
    cur.execute(f"select count(*) from {table};")  # noqa: S608 - fixed names
    row = cur.fetchone()
    return int(row[0]) if row else 0


def main() -> int:
    settings = get_settings()
    dsn = settings.supabase_db_url
    if not dsn:
        print("SUPABASE_DB_URL is not set", file=sys.stderr)
        return 1

    files = sorted(MIG_DIR.glob("*.sql"))
    if not files:
        print(f"No migrations found in {MIG_DIR}", file=sys.stderr)
        return 1

    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        if _has_supabase_auth(cur):
            print("auth.uid() present (Supabase) — no shim needed.")
        else:
            print("Installing local auth.uid() stub so RLS migrations apply...")
            cur.execute(AUTH_SHIM)

        tracking_existed = _table_exists(cur, "schema_migrations")
        cur.execute(LEDGER_TABLE)

        if not tracking_existed and _table_exists(cur, "citizens"):
            print("Existing schema found — recording pre-tracking migrations as applied.")
            for name in PRE_TRACKING:
                cur.execute(
                    "insert into schema_migrations (filename) values (%s) "
                    "on conflict do nothing;",
                    (name,),
                )

        done = _applied(cur)
        for path in files:
            if path.name in done:
                print(f"  skip {path.name} (already applied)")
                continue
            print(f"Applying {path.name}...")
            cur.execute(path.read_text(encoding="utf-8"))  # type: ignore[arg-type]
            cur.execute(
                "insert into schema_migrations (filename) values (%s);", (path.name,)
            )

        citizens = _count(cur, "citizens")
        rag = _count(cur, "rag_entries")

    print()
    print(f"Schema ready. {citizens} demo citizens seeded.")
    print()
    print("Works offline, no API keys needed:")
    print("  login (mock OTP 123456) · profile · procedure catalogue ·")
    print("  document create/fill · pdflatex render · delivery · audit ledger")
    print()
    if rag == 0:
        print("NOT usable yet — the agent chat:")
        print("  rag_entries is empty, so lookup_procedure has nothing to match")
        print("  against. It needs embeddings, which need a paid Azure OpenAI")
        print("  key. With AZURE_OPENAI_* set in .env, run:")
        print("      docker compose run --rm migrate python -m scripts.index_rag")
    else:
        print(f"RAG index: {rag} entries. Agent chat also needs AZURE_OPENAI_API_KEY.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
