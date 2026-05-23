---
type: module
path: "backend/app/worker.py"
status: active
language: python
purpose: "APScheduler interval worker that polls delivered ledger rows and writes reminders."
depends_on: [reminders]
used_by: [main (lifespan startup/shutdown)]
created: 2026-05-23
updated: 2026-05-23
---

# worker

In-process background scheduler that drives the proactive reminders pipeline.

## Lifespan

`init_worker()` is idempotent; called from FastAPI's lifespan (`main.lifespan`). If `apscheduler` isn't installed, it's a no-op so the app still starts.

Poll interval: `REMINDERS_POLL_SECONDS` (env, default 5).

## What the job does

```
every 5s:
  rows = fetch_pending_delivered_events()
  for row in rows:
    procedure_id = fetch_document_procedure_id(row.document_id)
    evaluate_next_steps(citizen_id, procedure_id, trigger_doc_id)
    mark_event_processed(row.id)
```

- The DB view `pending_delivered_events` is `ledger LEFT JOIN processed_events WHERE event_type='delivered' AND processed_events.ledger_id IS NULL` — naturally idempotent.
- On exception, the row is **not** marked processed; the next tick retries.

## Why in-process and not a separate dyno

Hackathon scope. The whole reminders pipeline fits in 50 lines and one `BackgroundScheduler`. Multi-worker scale would split this off into its own deployment to avoid scheduling 5 copies of the same job.

> [!gotcha] `max_instances=1, coalesce=True`
> Two concurrent ticks would race on the same `delivered` rows. The APScheduler settings serialize them. If you swap APScheduler for something else, preserve these semantics.

## See also

- [[Flow Reminders Worker]]
- [[reminders]]
- [[Database Schema]] — `pending_delivered_events` view + `processed_events`
- [[Dep APScheduler]]
