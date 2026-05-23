---
type: module
path: "backend/migrations/ + backend/scripts/apply_migrations.py"
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Migrations

Eight SQL files applied by `backend/scripts/apply_migrations.py` in order.

## Files

| Order | File | What it adds |
|---|---|---|
| 001 | `001_initial_schema.sql` | citizens, documents, ledger, reminders, procedures_embeddings, otp_challenges, pgvector + pgcrypto extensions |
| 002 | `002_seed_data.sql` | 3 demo citizens, 1 draft doc, 2 reminders, genesis ledger row |
| 003 | `003_ledger_function.sql` | `append_ledger()` + `ledger_tip_hash()` plpgsql functions |
| 004 | `004_rls_policies.sql` | RLS enabled + policies for citizens, documents, ledger, reminders |
| 005 | `005_processed_events.sql` | `processed_events` watermark + `pending_delivered_events` view |
| 006 | `006_seed_reminders.sql` | Per-citizen seed reminders (Maria + Elena) |
| 007 | `007_rag_entries.sql` | Renames `procedures_embeddings` → `rag_entries` + adds `kind` column |
| 008 | `008_sessions.sql` | The `sessions` table (state machine persistence) |

## Apply

```bash
python backend/scripts/apply_migrations.py
```

The script uses `SUPABASE_DB_URL`. It reads each `.sql` file and executes it via psycopg. Idempotent statements (`create extension if not exists ...`, `create table if not exists ...` where possible) so re-running is safe in most cases.

> [!gotcha] No down-migrations
> The hackathon repo never wrote rollback scripts. To revert, `DROP DATABASE` and re-run from scratch (or pg_dump first).

## Seed mirror in code

`backend/app/demo.py:SEED_BY_CNP` is a hardcoded mirror of `006_seed_reminders.sql`. **When you edit the seed migration, edit `SEED_BY_CNP` too.** No test catches the drift.

## After applying

Always re-run the indexers:

```bash
python backend/scripts/embed_procedures.py
python backend/scripts/index_rag.py
```

They `upsert` into `rag_entries` so re-running is safe.

## See also

- [[Database Schema]]
- [[demo]]
- [[embeddings]]
- backend/RUNBOOK.md
