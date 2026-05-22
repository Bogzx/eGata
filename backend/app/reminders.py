"""Reminder endpoints (Wave 1 stubs — Plan 4 adds the worker that creates them).

Wave 1 exposes:
- GET  /reminders                : list reminders for the authenticated citizen
- PATCH /reminders/{id}          : update status (pending|started|done|dismissed)

The reminders table is created in migration 001 and seeded for Maria in 002.
Plan 4 will add a background worker that writes new rows after each `delivered`
ledger event by evaluating each procedure's `next_steps[].applies_if`.
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.db import get_pg_connection
from app.models import ReminderResponse
from app.security import current_citizen_id

router = APIRouter(prefix="/reminders", tags=["reminders"])


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
