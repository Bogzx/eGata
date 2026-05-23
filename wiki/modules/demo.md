---
type: module
path: "backend/app/demo.py"
status: active
language: python
purpose: "POST /demo/reset — wipe a citizen's runtime state and re-seed reminders."
depends_on: [db]
used_by: [frontend DemoResetButton]
created: 2026-05-23
updated: 2026-05-23
---

# demo

The live-demo recovery button. Wipes everything a single citizen has accumulated and re-seeds the canned reminders so the next walkthrough starts clean.

## Auth

Header `X-Demo-Token: <env DEMO_RESET_TOKEN>`. If `DEMO_RESET_TOKEN` is unset, the endpoint **always** 401s — production deploys are safe by default.

## What it wipes

Order matters because of FK chains:

1. `processed_events` where `ledger_id IN (ledger of this citizen)`
2. `ledger` rows for this citizen
3. `reminders` for this citizen
4. `documents` for this citizen

It does NOT touch the citizen row itself, OTP challenges, sessions, or PDFs in Supabase Storage.

## What it re-seeds

`SEED_BY_CNP[cnp]` — hard-coded mirror of `002_seed_data.sql` + `006_seed_reminders.sql`. Currently:

- Maria (`2851014123456`): preschimbare-CI reminder + DRPCIV redirect reminder.
- Elena (`2620908123456`): DRPCIV redirect reminder.
- Andrei: no seeds.

> [!gotcha] Mirror gets out of sync
> When you change `002` or `006`, **also update `SEED_BY_CNP`** in this file. There's no test that catches drift — manually verify by running a reset.

## See also

- [[Demo Reset Flow]]
