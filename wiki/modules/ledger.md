---
type: module
path: "backend/app/ledger.py"
status: active
language: python
purpose: "Hash-chain ledger writer + verifier."
depends_on: [config, db]
used_by: [documents, agent_tools/start_procedure, agent_tools/complete_document, reminders]
created: 2026-05-23
updated: 2026-05-23
---

# ledger

Append-only, hash-chained event log. Each row links to the previous via `prev_hash`. Any tamper anywhere invalidates everything downstream.

## Event types

```
doc_created
completed_draft
pdf_generated
delivered
redirected
reminder_created
```

Enforced both in Python (`LedgerEventType` enum) and SQL (`check (event_type in (...))`).

## How the chain works

```
prev_hash ─► payload_hash ─► row_hash ─► (becomes next row's prev_hash)
```

Per-row:
```
payload_hash = "0x" + sha256(canonical_json(payload))
row_hash     = "0x" + sha256(event_type || payload_hash || prev_hash || iso_ts)
```

Canonical JSON: keys sorted, no whitespace, `ensure_ascii=False` (Romanian diacritics intact).

## `append_ledger(citizen_id, event_type, payload, document_id?) → dict`

Flow:

1. Read current tip via `SELECT ledger_tip_hash()` ([[Database Schema]]).
2. Compute `payload_hash`, `iso_ts`, `row_hash`.
3. Call Postgres function `append_ledger(...)` which **re-checks** prev_hash equals the current tip — if not, raises.

This is the central guarantee: bypassing the function or racing between processes can't quietly insert a row with a wrong prev_hash. See `migrations/003_ledger_function.sql`.

## `verify_chain(rows, genesis_hash) → bool`

Walks the rows in order. For each:

- Recompute `payload_hash` from the payload; must equal stored.
- Stored `prev_hash` must equal the previous row's `row_hash` (or `genesis_hash` for the first).
- Recompute `row_hash` from `(event_type, payload_hash, prev_hash, iso_ts)`; must match stored.

Used by `GET /documents/{id}/ledger` ([[documents]]) to set `verified: bool` on the response.

## Genesis row

`migrations/002_seed_data.sql` inserts a `doc_created` row with `payload={}` and a fixed `row_hash = sha256("genesis")`. **Without that row, the first append would have nothing to point at** — the chain only works because there's a known anchor.

## See also

- [[ADR Hash-Chain Ledger]] — rationale
- [[Database Schema]] — table definition + functions
- [[Flow Document Lifecycle]] — which calls fire which events
