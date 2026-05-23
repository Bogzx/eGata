---
type: dependency
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Database Schema

Every Postgres table, view, and function. Applied by `backend/scripts/apply_migrations.py` (runs the 8 SQL files in order).

## Tables

### `citizens`

```sql
id            uuid PK default gen_random_uuid()
cnp           text UNIQUE NOT NULL
nume          text NOT NULL
prenume       text NOT NULL
data_nasterii date NOT NULL
email         text
phone         text NOT NULL
attributes    jsonb DEFAULT '{}'  -- see [[citizens]] for keys
created_at    timestamptz DEFAULT now()
```

### `documents`

```sql
id            uuid PK
citizen_id    uuid FK citizens(id) ON DELETE CASCADE
procedure_id  text NOT NULL                  -- references procedures/*.json id
status        text DEFAULT 'draft' CHECK (status IN ('draft','finalized'))
fields        jsonb DEFAULT '{}'
pdf_url       text
delivery      text CHECK (delivery IN ('save','send','print'))
ref_number    text                            -- "CV-XXXX"
created_at    timestamptz DEFAULT now()
delivered_at  timestamptz
```

Indexes: `idx_documents_citizen`, `idx_documents_status`.

### `ledger`

```sql
id            bigserial PK
citizen_id    uuid NOT NULL
document_id   uuid
event_type    text CHECK (event_type IN (
  'doc_created','completed_draft','pdf_generated',
  'delivered','redirected','reminder_created'
))
payload       jsonb DEFAULT '{}'
payload_hash  text NOT NULL
prev_hash     text NOT NULL
row_hash      text NOT NULL
created_at    timestamptz DEFAULT now()
```

Indexes: `idx_ledger_citizen`, `idx_ledger_document`.

### `reminders`

```sql
id              uuid PK
citizen_id      uuid FK citizens(id) ON DELETE CASCADE
trigger_doc_id  uuid FK documents(id) ON DELETE SET NULL
kind            text CHECK (kind IN ('in_scope_procedure','external_redirect'))
procedure_id    text
redirect_target text
title           text NOT NULL
due_date        date
status          text DEFAULT 'pending' CHECK (status IN ('pending','started','done','dismissed'))
created_at      timestamptz DEFAULT now()
```

Indexes: `idx_reminders_citizen`, `idx_reminders_status`.

### `rag_entries` (was `procedures_embeddings`)

```sql
id          text PK
kind        text NOT NULL CHECK (kind IN ('procedure','scenario')) DEFAULT 'procedure'
embedding   vector(768) NOT NULL
source_text text NOT NULL
updated_at  timestamptz DEFAULT now()
```

Index: `idx_rag_entries_kind`.

### `otp_challenges`

```sql
id          text PK             -- "ch_..."
citizen_id  uuid FK citizens(id) ON DELETE CASCADE
phone       text NOT NULL
twilio_sid  text
expires_at  timestamptz NOT NULL
consumed    boolean DEFAULT false
created_at  timestamptz DEFAULT now()
```

Index: `idx_otp_expires`.

### `sessions`

```sql
id                 text PK              -- "sess_..." or legacy "conv_..."
citizen_id         uuid FK citizens(id) ON DELETE CASCADE
state              text NOT NULL DEFAULT 'exploring' CHECK (state IN (
  'exploring','confirming_match','filling','reviewing','delivered','redirected'
))
active_document_id uuid FK documents(id) ON DELETE SET NULL
scenario_id        text
step_index         int
pending_widgets    jsonb DEFAULT '[]'
history            jsonb DEFAULT '[]'   -- Gemini Content list, JSON-serialized
created_at         timestamptz DEFAULT now()
updated_at         timestamptz DEFAULT now()
```

Indexes: `idx_sessions_citizen`, `idx_sessions_active_doc`, `idx_sessions_state`.

### `processed_events`

```sql
ledger_id    bigint PK FK ledger(id) ON DELETE CASCADE
processed_at timestamptz DEFAULT now()
```

Index: `idx_processed_events_processed_at`.

## Views

### `pending_delivered_events`

```sql
SELECT l.*
FROM ledger l
LEFT JOIN processed_events p ON p.ledger_id = l.id
WHERE l.event_type = 'delivered' AND p.ledger_id IS NULL
ORDER BY l.id ASC;
```

Used by [[worker]] for idempotent reminder generation.

## Functions

### `append_ledger(p_citizen_id, p_document_id, p_event_type, p_payload, p_payload_hash, p_expected_prev_hash, p_row_hash) → bigint`

`migrations/003_ledger_function.sql`. Atomically validates `p_expected_prev_hash == ledger_tip_hash()` then inserts. Raises on mismatch. See [[ledger]] + [[ADR Hash-Chain Ledger]].

### `ledger_tip_hash() → text`

Returns the `row_hash` of the latest ledger row or the genesis hash if empty.

## RLS

`migrations/004_rls_policies.sql` enables RLS on citizens, documents, ledger, reminders. Policies allow the row's owner to select/modify. Backend uses service-role key → bypasses. See [[ADR Service Role Key + RLS Bypass]].

## Migrations order

```
001_initial_schema.sql       — base tables + procedures_embeddings
002_seed_data.sql            — 3 citizens, 1 doc, 2 reminders, genesis ledger row
003_ledger_function.sql      — append_ledger() + ledger_tip_hash()
004_rls_policies.sql         — RLS policies
005_processed_events.sql     — watermark table + view
006_seed_reminders.sql       — per-citizen seed reminders
007_rag_entries.sql          — rename + add `kind` column
008_sessions.sql             — sessions table
```

## See also

- [[Migrations]]
- [[Dep Supabase]]
- [[ledger]]
- [[sessions]]
