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
2. It (re)builds the offline procedure-search index (app/local_embeddings.py)
   so the chat works with no API key — the offline agent
   (app/offline_agent.py) searches it — and reports what is usable.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
import psycopg.sql

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


def _enable_app_login(cur: psycopg.Cursor) -> str:
    """Give `egata_app` (migrations/014) a login when APP_DB_PASSWORD is set.

    The password comes from the environment on every run, so rotating it is
    re-running this script with a new value. Returns a status line.
    """
    password = os.environ.get("APP_DB_PASSWORD", "").strip()
    cur.execute("select 1 from pg_roles where rolname = 'egata_app';")
    if cur.fetchone() is None:
        return "egata_app role missing (no CREATE ROLE privilege?) — backend must use the owner"
    if not password:
        return "egata_app exists without a login — set APP_DB_PASSWORD to enable it"
    cur.execute(
        psycopg.sql.SQL("alter role egata_app with login password {}").format(
            psycopg.sql.Literal(password)
        )
    )
    return "egata_app can log in (least-privilege backend role; ledger is append-only for it)"


def _dsn() -> str:
    """Read SUPABASE_DB_URL directly rather than through app.config.

    Settings also demands JWT_SIGNING_SECRET and would refuse to build without
    it — applying migrations should not require an unrelated secret.
    """
    return os.environ.get("SUPABASE_DB_URL", "").strip()


def main() -> int:
    dsn = _dsn()
    if not dsn:
        print(
            "SUPABASE_DB_URL is not set. Point it at your Postgres, e.g.\n"
            "  postgresql://postgres:postgres@localhost:5432/egata",
            file=sys.stderr,
        )
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

        app_role = _enable_app_login(cur)

        # Cheap (a few dozen rows, no network) and keeps the offline index in
        # step with procedure/scenario JSON edits on every start.
        from scripts.index_rag import index_local

        local_indexed = index_local(conn)

        citizens = _count(cur, "citizens")
        cur.execute("select count(*) from rag_entries where embedding_model = 'azure';")
        row = cur.fetchone()
        azure_rag = int(row[0]) if row else 0

    has_key = bool(os.environ.get("AZURE_OPENAI_API_KEY", "").strip())
    print()
    print(f"Schema ready. {citizens} demo citizens seeded.")
    print(f"Offline procedure index: {local_indexed} entries.")
    print(f"App role: {app_role}.")
    print()
    print("Works with no API keys:")
    print("  login (mock OTP 123456) · profile · procedure catalogue ·")
    print("  document create/fill · pdflatex render · delivery · audit ledger ·")
    print("  text chat with the OFFLINE agent (scripted, keyword search — not an LLM)")
    print()
    if not has_key:
        print("Needs Azure: the LLM agent and voice. Put AZURE_OPENAI_* in .env,")
        print("restart, and build the Azure index once:")
        print("      docker compose run --rm migrate python -m scripts.index_rag")
    elif azure_rag == 0:
        print("AZURE_OPENAI_API_KEY is set but the Azure index is empty. Build it:")
        print("      docker compose run --rm migrate python -m scripts.index_rag")
    else:
        print(f"Azure index: {azure_rag} entries. The LLM agent is active.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
