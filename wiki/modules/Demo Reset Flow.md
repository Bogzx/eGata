---
type: module
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Demo Reset Flow

When the demo runs once, citizen Maria accumulates documents, ledger rows, and reminders. The reset endpoint wipes them so the next walkthrough starts clean.

## Usage

```bash
curl -X POST https://<host>/demo/reset \
  -H "Content-Type: application/json" \
  -H "X-Demo-Token: $DEMO_RESET_TOKEN" \
  -d '{}'                   # defaults to Maria; or {"citizen_id":"<uuid>"}
```

Returns:

```json
{
  "ok": true,
  "citizen_id": "11111111-1111-1111-1111-111111111111",
  "counts": {
    "documents_deleted": N,
    "reminders_deleted": N,
    "ledger_deleted": N,
    "processed_events_deleted": N,
    "reminders_seeded": 2
  }
}
```

## What gets wiped

(In order, respecting FKs)

1. `processed_events` where ledger_id belongs to this citizen
2. `ledger` rows for this citizen
3. `reminders` for this citizen
4. `documents` for this citizen

## What does NOT get wiped

- The `citizens` row itself (we keep the user)
- OTP challenges (they expire on their own)
- `sessions` rows (the conversation history persists — flush separately if you need a totally fresh chat too)
- PDFs in Supabase Storage (just orphaned; no cost to leave)

## Then re-seeds

`SEED_BY_CNP[cnp]` — same shape as `migrations/006_seed_reminders.sql`. Currently:

- Maria → 2 reminders (preschimbare-CI + DRPCIV)
- Elena → 1 reminder (DRPCIV)
- Andrei → no seeds

## Auth

`X-Demo-Token` header MUST match `DEMO_RESET_TOKEN` env var. If `DEMO_RESET_TOKEN` is unset, the endpoint **always** 401s. Production-safe by default.

## FE

The `DemoResetButton` component calls `api.resetDemo()` ([[Frontend Lib]]) which reads `NEXT_PUBLIC_DEMO_TOKEN` from env and posts.

## See also

- [[demo]]
- [[Database Schema]]
