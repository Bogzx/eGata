---
type: flow
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Flow: Reminders Worker

Background process that turns `delivered` ledger rows into proactive reminders.

## Pipeline

```
documents.deliver  ─►  ledger row { event_type: 'delivered', document_id, citizen_id, ... }
                                                                                       │
                                                                                       ▼
                                                                        pending_delivered_events VIEW
                                                                        (ledger LEFT JOIN processed_events
                                                                         WHERE event_type='delivered'
                                                                           AND processed_events.ledger_id IS NULL)
                                                                                       │
                          APScheduler tick (every REMINDERS_POLL_SECONDS, default 5s)  │
                                                                                       ▼
                                                                          for each row:
                                                                            procedure_id = fetch_document_procedure_id(doc_id)
                                                                            attrs       = fetch_citizen_attributes(citizen_id)
                                                                            steps       = procedure.next_steps
                                                                            applicable  = _select_applicable_steps(steps, attrs)  ◄── applies_if
                                                                            existing    = fetch_reminders_for_trigger(doc_id)
                                                                            for step not already in existing:
                                                                              insert reminder
                                                                              append_ledger(reminder_created, ...)
                                                                            mark_event_processed(ledger_id)
```

## Idempotency layers

| Layer | Mechanism |
|---|---|
| Per-tick double-fire | `apscheduler: max_instances=1, coalesce=True` ([[worker]]) |
| Crash mid-tick | `processed_events` only marked on success; failed rows retry next tick |
| Duplicate write | `existing_keys = {(kind, procedure_id_or_redirect_target)}` checked before insert |

## applies_if step filter

`schimbare-domiciliu.next_steps` has:

```json
[
  { "kind": "in_scope_procedure", "procedure_id": "preschimbare-ci", "deadline_days": 15, "title": "..." },
  { "kind": "external_redirect",  "redirect_target": "DRPCIV", "deadline_days": 30,
    "title": "Actualizare certificat înmatriculare auto",
    "applies_if": "owns_vehicle == true" },
  { "kind": "external_redirect",  "redirect_target": "CNAS", "title": "..." },
  { "kind": "external_redirect",  "redirect_target": "ANAF", "title": "..." }
]
```

After Maria (`owns_vehicle: true`) delivers, all 4 reminders are written. After Andrei (`owns_vehicle: false`), only 3 — the DRPCIV step's `applies_if` evaluates false. See [[applies_if]] + [[reminders]]`._select_applicable_steps`.

## Why a watermark table not a row flag

`processed_events.ledger_id` is the watermark. Keeping it separate from `ledger` lets the ledger stay **strictly append-only with hash chain intact**. Adding a `processed` column to `ledger` would change row hashes after the fact and break verification.

## Reminder lifecycle

- Created `pending`.
- User clicks "Începe" on an `in_scope_procedure` reminder → `POST /reminders/{id}/start` → creates a draft doc (+ ledger row tagged `source: reminder`), marks reminder `started`.
- User clicks "Dismiss" → `POST /reminders/{id}/dismiss` → `dismissed`.

## See also

- [[reminders]]
- [[worker]]
- [[applies_if]]
- [[Database Schema]] — `pending_delivered_events` view definition
