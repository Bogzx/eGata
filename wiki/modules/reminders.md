---
type: module
path: "backend/app/reminders.py"
status: active
language: python
purpose: "Reminder writer, evaluator, endpoints — driven by ledger 'delivered' events."
depends_on: [applies_if, db, ledger, models, security, procedures]
used_by: [worker, frontend home page (RemindersList)]
created: 2026-05-23
updated: 2026-05-23
---

# reminders

The proactive layer. When a document gets `delivered`, the [[worker]] reads the procedure's `next_steps[]`, filters by `applies_if`, and writes a reminder per applicable step.

## Endpoints

| Route | Verb | Returns | Notes |
|---|---|---|---|
| `/reminders` | GET | `list[ReminderResponse]` | Sorted by `due_date asc nulls last, created_at desc`. |
| `/reminders/{id}` | PATCH | `ReminderResponse` | `{status: pending\|started\|done\|dismissed}`. Owner-gated. |
| `/reminders/{id}/start` | POST | `StartReminderResponse` | For `kind=in_scope_procedure` only: creates a draft doc + appends `doc_created` to ledger (with `source: reminder, reminder_id`). Marks reminder `started`. |
| `/reminders/{id}/dismiss` | POST | `ReminderResponse` | Marks `dismissed`. |

## The writer

```python
evaluate_next_steps(citizen_id, procedure_id, trigger_doc_id) → list[reminder]
```

Idempotent per `(trigger_doc_id, kind, procedure_id_or_redirect_target)`. Each new row also appends a `reminder_created` ledger entry — the audit trail captures proactive nudges too.

## `_select_applicable_steps(next_steps, attrs)`

Pure-logic filter using [[applies_if]]. Example: `schimbare-domiciliu.next_steps` includes a DRPCIV step gated on `owns_vehicle == true`. Maria (`owns_vehicle: true`) gets it; Andrei (`owns_vehicle: false`) does not.

## Worker plumbing

| Helper | Used by |
|---|---|
| `fetch_pending_delivered_events()` | Worker — reads `pending_delivered_events` view (delivered ledger rows not yet processed) |
| `mark_event_processed(ledger_id)` | Worker — inserts into `processed_events` watermark table |
| `fetch_document_procedure_id(doc_id)` | Worker — resolves procedure id from the trigger doc |

## See also

- [[Flow Reminders Worker]]
- [[worker]] — APScheduler runner
- [[Database Schema]] — `reminders` + `processed_events` + `pending_delivered_events` view
