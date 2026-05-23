"""APScheduler-based background worker for proactive reminders (Plan 4).

Polls the `pending_delivered_events` view every 5 seconds; for each new
`delivered` ledger entry, calls evaluate_next_steps to write reminders.

Idempotent: the processed_events watermark table records which ledger ids
have been handled.

If apscheduler is not installed (e.g., during partial dev), the bootstrap
is a no-op so the FastAPI app still starts.
"""
from __future__ import annotations

import logging
import os
from typing import Any
from uuid import UUID

log = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = int(os.environ.get("REMINDERS_POLL_SECONDS", "5"))

_SCHEDULER: Any | None = None


def _process_pending_events() -> None:
    from app.reminders import (
        evaluate_next_steps,
        fetch_document_procedure_id,
        fetch_pending_delivered_events,
        mark_event_processed,
    )

    rows = fetch_pending_delivered_events()
    if not rows:
        return
    for row in rows:
        ledger_id = int(row["id"])
        doc_id = row.get("document_id")
        citizen_id = row.get("citizen_id")
        if doc_id is None or citizen_id is None:
            mark_event_processed(ledger_id)
            continue
        try:
            procedure_id = fetch_document_procedure_id(doc_id)
            if procedure_id is None:
                log.warning(
                    "worker: ledger row %s references missing document %s",
                    ledger_id, doc_id,
                )
                mark_event_processed(ledger_id)
                continue
            evaluate_next_steps(
                citizen_id=UUID(str(citizen_id)),
                procedure_id=procedure_id,
                trigger_doc_id=UUID(str(doc_id)),
            )
            mark_event_processed(ledger_id)
        except Exception:
            log.exception("worker: failed to process ledger row %s", ledger_id)
            # leave it for retry on next tick


def init_worker() -> None:
    """Idempotent bootstrap: starts the APScheduler interval job once."""
    global _SCHEDULER

    if _SCHEDULER is not None:
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        log.warning("apscheduler not installed — reminders worker disabled")
        return

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        _process_pending_events,
        IntervalTrigger(seconds=POLL_INTERVAL_SECONDS),
        id="reminders_worker",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _SCHEDULER = scheduler
    log.info("reminders worker started; poll=%ss", POLL_INTERVAL_SECONDS)


def shutdown_worker() -> None:
    global _SCHEDULER
    if _SCHEDULER is not None:
        try:
            _SCHEDULER.shutdown(wait=False)
        except Exception:
            log.exception("worker shutdown failed")
        _SCHEDULER = None
