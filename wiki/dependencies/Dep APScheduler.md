---
type: dependency
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Dep: APScheduler

In-process job scheduler. Single use: poll `pending_delivered_events` view every 5 seconds and write reminders.

## Config

```python
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(
    _process_pending_events,
    IntervalTrigger(seconds=POLL_INTERVAL_SECONDS),   # default 5
    id="reminders_worker",
    max_instances=1,                                   # serialize concurrent ticks
    coalesce=True,                                     # drop missed ticks instead of catching up
)
```

`max_instances=1, coalesce=True` together mean: at most one tick runs at a time, and a slow tick (DB hiccup) doesn't queue up backlog.

## Why in-process

Hackathon scope. Reminders pipeline is small enough to live in the same FastAPI worker without affecting request latency.

> [!gotcha] Multi-worker deployments would multiply jobs
> Two `uvicorn` workers = two schedulers = two of every job. For now we run a single worker. If we scale, split the worker into its own process and remove the scheduler from `main.lifespan`.

## Lifespan

`init_worker()` is called in [[main]]'s `lifespan` startup. `shutdown_worker()` is called on shutdown. Both idempotent — safe to call twice.

## If the import fails

```python
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    ...
except ImportError:
    log.warning("apscheduler not installed — reminders worker disabled")
    return
```

The app still starts; reminders just won't fire. Useful for slim test environments.

## See also

- [[worker]]
- [[Flow Reminders Worker]]
