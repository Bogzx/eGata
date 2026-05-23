"""set_reminder — insert a row in the reminders table.

Called by the conversational agent (rarely; only on explicit "remind me later"
intent) AND by Plan 4's background worker after document delivery. Plan 4 imports
this function directly with a synthetic ToolContext built from the citizen_id.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel

from app.db import get_supabase
from app.tools import ToolContext, register

_VALID_KINDS = {"in_scope_procedure", "external_redirect"}


class ReminderResult(BaseModel):
    id: uuid.UUID
    citizen_id: uuid.UUID
    trigger_doc_id: uuid.UUID | None = None
    kind: str
    procedure_id: str | None = None
    redirect_target: str | None = None
    title: str
    due_date: date | None = None
    status: str


@register("set_reminder")
async def set_reminder(
    ctx: ToolContext,
    kind: str,
    title: str,
    procedure_id: str | None = None,
    redirect_target: str | None = None,
    trigger_doc_id: str | None = None,
    deadline_days: int | None = None,
) -> ReminderResult:
    if kind not in _VALID_KINDS:
        raise ValueError(f"kind must be in {_VALID_KINDS}, got {kind!r}")
    if kind == "in_scope_procedure" and not procedure_id:
        raise ValueError("procedure_id required when kind=in_scope_procedure")
    if kind == "external_redirect" and not redirect_target:
        raise ValueError("redirect_target required when kind=external_redirect")

    due = (date.today() + timedelta(days=deadline_days)) if deadline_days else None

    row: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "citizen_id": ctx.citizen_id,
        "trigger_doc_id": trigger_doc_id or ctx.document_id,
        "kind": kind,
        "procedure_id": procedure_id,
        "redirect_target": redirect_target,
        "title": title,
        "due_date": due.isoformat() if due else None,
        "status": "pending",
    }
    resp = get_supabase().table("reminders").insert(row).execute()
    inserted = resp.data[0]
    return ReminderResult(**inserted)
