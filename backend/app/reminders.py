"""Reminder writer, worker helpers, and endpoints (Plan 4).

Wave 1 shipped a stub with GET /reminders + PATCH /reminders/{id}. Plan 4 adds:
- `_select_applicable_steps`: pure selection over a procedure's next_steps.
- `evaluate_next_steps`: read procedure registry, filter by applies_if, persist
  matching reminders and emit a `reminder_created` ledger row each.
- Worker helpers: `fetch_pending_delivered_events`, `mark_event_processed`.
- POST /reminders/{id}/start  — for in_scope_procedure reminders.
- POST /reminders/{id}/dismiss — mark status=dismissed.

Idempotency: writer is idempotent per (trigger_doc_id, step identity); if the
worker reruns the same ledger row, no duplicate reminders are written.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Literal, Mapping
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.applies_if import evaluate as evaluate_applies_if
from app.db import get_pg_connection
from app.ledger import LedgerEventType, append_ledger
from app.models import ReminderResponse
from app.security import current_citizen_id

log = logging.getLogger(__name__)

router = APIRouter(prefix="/reminders", tags=["reminders"])


# ---------- Wave 1 read helpers (kept) ----------


class PatchReminderRequest(BaseModel):
    status: Literal["pending", "started", "done", "dismissed"]


def list_reminders_for_citizen(citizen_id: UUID) -> list[dict[str, Any]]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, citizen_id, trigger_doc_id, kind, procedure_id, redirect_target, "
            "title, due_date, status, created_at "
            "from reminders where citizen_id = %s order by due_date asc nulls last, created_at desc;",
            (str(citizen_id),),
        )
        return [dict(r) for r in cur.fetchall()]


def fetch_reminder(reminder_id: UUID) -> dict[str, Any]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, citizen_id, trigger_doc_id, kind, procedure_id, redirect_target, "
            "title, due_date, status, created_at "
            "from reminders where id = %s;",
            (str(reminder_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return dict(row)


def update_reminder_status(reminder_id: UUID, new_status: str) -> dict[str, Any]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "update reminders set status = %s where id = %s "
            "returning id, citizen_id, trigger_doc_id, kind, procedure_id, redirect_target, "
            "title, due_date, status, created_at;",
            (new_status, str(reminder_id)),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Reminder not found")
        conn.commit()
    return dict(row)


# ---------- Plan 4 selection + writer ----------


def _next_steps_for(procedure_id: str) -> list[Mapping[str, Any]]:
    from app.procedures import get_registry  # lazy: avoids pulling embeddings at import time

    reg = get_registry()
    proc = reg.get(procedure_id)
    if proc is None:
        return []
    return [s.model_dump() for s in proc.next_steps]


def _select_applicable_steps(
    next_steps: list[Mapping[str, Any]],
    attributes: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    """Pure-logic: filter next_steps by their applies_if expression."""
    out: list[Mapping[str, Any]] = []
    for step in next_steps:
        cond = step.get("applies_if")
        if evaluate_applies_if(cond, attributes):
            out.append(step)
    return out


def _step_identity(step: Mapping[str, Any]) -> tuple[str, str | None]:
    """Stable identity for a next_step within a procedure (for idempotency)."""
    return (
        step["kind"],
        step.get("procedure_id") or step.get("redirect_target"),
    )


def fetch_citizen_attributes(citizen_id: UUID) -> dict[str, Any]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select attributes from citizens where id = %s;",
            (str(citizen_id),),
        )
        row = cur.fetchone()
    if row is None:
        return {}
    return dict(row.get("attributes") or {})


def fetch_reminders_for_trigger(trigger_doc_id: UUID | None) -> list[dict[str, Any]]:
    if trigger_doc_id is None:
        return []
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select kind, procedure_id, redirect_target "
            "from reminders where trigger_doc_id = %s;",
            (str(trigger_doc_id),),
        )
        return [dict(r) for r in cur.fetchall()]


def _insert_reminder_row(
    *,
    citizen_id: UUID,
    trigger_doc_id: UUID | None,
    kind: str,
    procedure_id: str | None,
    redirect_target: str | None,
    title: str,
    due_date: date | None,
) -> dict[str, Any]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into reminders (citizen_id, trigger_doc_id, kind, procedure_id, "
            "redirect_target, title, due_date, status) "
            "values (%s, %s, %s, %s, %s, %s, %s, 'pending') "
            "returning id, citizen_id, trigger_doc_id, kind, procedure_id, redirect_target, "
            "title, due_date, status, created_at;",
            (
                str(citizen_id),
                str(trigger_doc_id) if trigger_doc_id else None,
                kind,
                procedure_id,
                redirect_target,
                title,
                due_date,
            ),
        )
        row = cur.fetchone()
        conn.commit()
    if row is None:
        raise RuntimeError("insert reminder returned no row")
    return dict(row)


def evaluate_next_steps(
    *,
    citizen_id: UUID,
    procedure_id: str,
    trigger_doc_id: UUID | None,
) -> list[dict[str, Any]]:
    """For a procedure's next_steps, persist a reminder per applicable step.

    Skips steps whose `applies_if` evaluates False against citizen.attributes.
    Idempotent per (trigger_doc_id, step identity).
    Each newly created reminder emits a `reminder_created` ledger entry.
    """
    steps = _next_steps_for(procedure_id)
    if not steps:
        return []

    attrs = fetch_citizen_attributes(citizen_id)
    applicable = _select_applicable_steps(steps, attrs)

    existing = fetch_reminders_for_trigger(trigger_doc_id)
    existing_keys = {_step_identity(r) for r in existing}

    created: list[dict[str, Any]] = []
    for step in applicable:
        if _step_identity(step) in existing_keys:
            continue
        deadline_days = step.get("deadline_days")
        due = date.today() + timedelta(days=deadline_days) if deadline_days else None
        row = _insert_reminder_row(
            citizen_id=citizen_id,
            trigger_doc_id=trigger_doc_id,
            kind=step["kind"],
            procedure_id=step.get("procedure_id"),
            redirect_target=step.get("redirect_target"),
            title=step["title"],
            due_date=due,
        )
        try:
            append_ledger(
                citizen_id=citizen_id,
                event_type=LedgerEventType.REMINDER_CREATED,
                payload={
                    "reminder_id": str(row["id"]),
                    "kind": step["kind"],
                    "title": step["title"],
                    "procedure_id": step.get("procedure_id"),
                    "redirect_target": step.get("redirect_target"),
                },
                document_id=trigger_doc_id,
            )
        except Exception:
            log.exception("ledger append failed for reminder %s", row["id"])
        created.append(row)
    return created


# ---------- Worker helpers ----------


def fetch_pending_delivered_events() -> list[dict[str, Any]]:
    """Ledger rows where event_type='delivered' and not yet processed."""
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, citizen_id, document_id "
            "from pending_delivered_events limit 50;"
        )
        return [dict(r) for r in cur.fetchall()]


def mark_event_processed(ledger_id: int) -> None:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into processed_events (ledger_id) values (%s) "
            "on conflict (ledger_id) do nothing;",
            (ledger_id,),
        )
        conn.commit()


def fetch_document_procedure_id(document_id: UUID | str) -> str | None:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select procedure_id from documents where id = %s;",
            (str(document_id),),
        )
        row = cur.fetchone()
    return None if row is None else row["procedure_id"]


# ---------- Endpoints ----------


class StartReminderResponse(BaseModel):
    id: UUID
    status: str
    document_id: UUID
    procedure_id: str


@router.get("", response_model=list[ReminderResponse])
def list_my_reminders(
    citizen_id: UUID = Depends(current_citizen_id),
) -> list[ReminderResponse]:
    rows = list_reminders_for_citizen(citizen_id)
    return [ReminderResponse(**r) for r in rows]


@router.patch("/{reminder_id}", response_model=ReminderResponse)
def patch_reminder(
    reminder_id: UUID,
    req: PatchReminderRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> ReminderResponse:
    existing = fetch_reminder(reminder_id)
    if str(existing["citizen_id"]) != str(citizen_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your reminder")
    updated = update_reminder_status(reminder_id, req.status)
    return ReminderResponse(**updated)


@router.post("/{reminder_id}/start", response_model=StartReminderResponse)
def start_reminder(
    reminder_id: UUID,
    citizen_id: UUID = Depends(current_citizen_id),
) -> StartReminderResponse:
    """For in_scope_procedure reminders only: create a draft doc, mark started."""
    from app.documents import insert_document as _insert_doc

    rem = fetch_reminder(reminder_id)
    if str(rem["citizen_id"]) != str(citizen_id):
        raise HTTPException(status_code=404, detail="Reminder not found")
    if rem["kind"] != "in_scope_procedure":
        raise HTTPException(
            status_code=400,
            detail="Reminder is an external redirect; cannot start in-app.",
        )
    procedure_id = rem.get("procedure_id")
    if not procedure_id:
        raise HTTPException(status_code=400, detail="Reminder has no procedure_id")
    from app.procedures import get_registry as _get_registry

    if procedure_id not in _get_registry():
        raise HTTPException(status_code=400, detail=f"Unknown procedure {procedure_id}")

    new_doc = _insert_doc(citizen_id, procedure_id)
    append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.DOC_CREATED,
        payload={
            "document_id": str(new_doc["id"]),
            "procedure_id": procedure_id,
            "source": "reminder",
            "reminder_id": str(reminder_id),
        },
        document_id=new_doc["id"],
    )
    update_reminder_status(reminder_id, "started")
    return StartReminderResponse(
        id=reminder_id,
        status="started",
        document_id=new_doc["id"],
        procedure_id=procedure_id,
    )


@router.post("/{reminder_id}/dismiss", response_model=ReminderResponse)
def dismiss_reminder(
    reminder_id: UUID,
    citizen_id: UUID = Depends(current_citizen_id),
) -> ReminderResponse:
    rem = fetch_reminder(reminder_id)
    if str(rem["citizen_id"]) != str(citizen_id):
        raise HTTPException(status_code=404, detail="Reminder not found")
    updated = update_reminder_status(reminder_id, "dismissed")
    return ReminderResponse(**updated)
