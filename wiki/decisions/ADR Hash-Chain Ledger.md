---
type: decision
status: active
created: 2026-05-23
updated: 2026-05-23
---

# ADR: Hash-Chain Ledger

## Decision

Every significant event (doc_created, completed_draft, pdf_generated, delivered, redirected, reminder_created) is appended to a single `ledger` table that **chains rows via `prev_hash → row_hash`**. Inserts go through a Postgres function (`append_ledger`) that **enforces the chain at the database level**.

## Why

Two non-negotiables for a government-facing app:

1. **Tamper-evidence** — if anyone modifies an old payload, every downstream `payload_hash` and `row_hash` recomputes to something different. `verify_chain` catches it instantly.
2. **Append-only audit** — no UPDATE / DELETE. Even a misbehaving service can't quietly retcon history.

Plus: it's a striking demo moment. The `/documents/{id}/ledger` response includes `verified: true/false` and the FE timeline shows the row hashes — visible proof of the audit trail.

## Mechanism (recap)

```
payload_hash = "0x" + sha256(canonical_json(payload))
row_hash     = "0x" + sha256(event_type || payload_hash || prev_hash || iso_ts)
```

Canonical JSON: keys sorted, no whitespace, `ensure_ascii=False`. See [[ledger]].

## Why a Postgres function and not just Python

Without the DB-level check, two concurrent processes could each read tip = H, both compute `prev_hash=H`, both insert with the same prev_hash, and the chain branches. `migrations/003_ledger_function.sql` enforces `prev_hash = ledger_tip_hash()` inside the same transaction as the insert. Race-free.

## Cost

- All ledger writes go through one helper. No raw `INSERT INTO ledger`. We have a grep convention for this — search the repo for `INSERT INTO ledger` and verify only the function references it.
- Genesis row matters. Without it, the first append has nothing to chain against. The seed migration writes it.

## What it doesn't protect against

- Someone with DB credentials nuking the whole table and rebuilding. The function only protects against **partial** tampers.
- Backdated reminders: the chain doesn't know the difference between a `delivered` row at T+5 and one at T-3.

## See also

- [[ledger]]
- [[Database Schema]]
- [[Flow Document Lifecycle]]
