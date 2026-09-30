"""Demo reset endpoint (Plan 4).

Wipes a citizen's documents and reminders, appends a `demo_reset` marker to
the (append-only) ledger, then re-applies the per-citizen seed reminders so
the demo starts from a known state.

Authorized via static dev token in DEMO_RESET_TOKEN. If the env var is unset,
the endpoint always returns 401 (so production deploys are safe by default).
"""
from __future__ import annotations

import hmac
import os
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.db import get_pg_connection
from app.ledger import LedgerEventType, append_ledger

router = APIRouter(prefix="/demo", tags=["demo"])

DEFAULT_DEMO_CITIZEN_CNP = "2851014123456"  # Maria Ionescu


class ResetRequest(BaseModel):
    citizen_id: UUID | None = None


class ResetCounts(BaseModel):
    documents_deleted: int
    reminders_deleted: int
    # The ledger is append-only (migrations/009): a reset appends a
    # `demo_reset` marker row rather than erasing history. Kept as a count so
    # the response shape stays stable for the frontend.
    ledger_marked: int
    processed_events_deleted: int
    reminders_seeded: int


class ResetResponse(BaseModel):
    ok: bool
    citizen_id: UUID
    counts: ResetCounts


def _verify_token(x_demo_token: str | None) -> None:
    expected = os.environ.get("DEMO_RESET_TOKEN")
    if not expected or not hmac.compare_digest(
        (x_demo_token or "").encode(), expected.encode()
    ):
        raise HTTPException(status_code=401, detail="Invalid demo token")


def _resolve_default_citizen_id() -> UUID:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute("select id from citizens where cnp = %s;", (DEFAULT_DEMO_CITIZEN_CNP,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=500, detail="Default demo citizen not seeded")
    return UUID(str(row["id"]))


def _wipe_citizen(citizen_id: UUID) -> dict[str, int]:
    """Clear the citizen's demo state.

    Documents and reminders are demo scaffolding and are deleted. The ledger
    is not: it is append-only (migrations/009 revokes DELETE and installs a
    trigger), so the reset appends a `demo_reset` marker instead. Ledger rows
    belonging to the deleted documents are simply no longer reachable —
    `/documents/{id}/ledger` reads per document, and the document is gone.

    processed_events rows are watermarks keyed by ledger_id; since those
    ledger rows survive, the watermarks must survive too, or the reminders
    worker would re-process every historical `delivered` event and resurrect
    the reminders this reset just cleared.
    """
    cid = str(citizen_id)
    counts: dict[str, int] = {
        "processed_events_deleted": 0,
        "ledger_marked": 0,
        "reminders_deleted": 0,
        "documents_deleted": 0,
    }
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute("delete from reminders where citizen_id = %s;", (cid,))
        counts["reminders_deleted"] = cur.rowcount or 0

        cur.execute("delete from documents where citizen_id = %s;", (cid,))
        counts["documents_deleted"] = cur.rowcount or 0

        conn.commit()

    append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.DEMO_RESET,
        payload={
            "documents_deleted": counts["documents_deleted"],
            "reminders_deleted": counts["reminders_deleted"],
        },
        document_id=None,
    )
    counts["ledger_marked"] = 1
    return counts


# Hard-coded mirror of the per-citizen seed reminders (002 + 006).
# IMPORTANT: keep in sync with migrations/002_seed_data.sql + 006_seed_reminders.sql.
SEED_BY_CNP: dict[str, list[dict[str, Any]]] = {
    "2851014123456": [  # Maria
        {
            "kind": "in_scope_procedure",
            "procedure_id": "preschimbare-ci",
            "title": "Cartea de identitate expiră în 23 de zile — programează preschimbarea",
            "due_offset_days": 23,
        },
        {
            "kind": "external_redirect",
            "redirect_target": "DRPCIV",
            "title": "După schimbarea domiciliului trebuie să-ți actualizezi certificatul de înmatriculare la DRPCIV",
            "due_offset_days": 30,
        },
    ],
    "2620908123456": [  # Elena
        {
            "kind": "external_redirect",
            "redirect_target": "DRPCIV",
            "title": "Actualizare certificat înmatriculare auto (termen 30 zile)",
            "due_offset_days": 30,
        },
    ],
}


def _seed_for_citizen(citizen_id: UUID) -> int:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute("select cnp from citizens where id = %s;", (str(citizen_id),))
        row = cur.fetchone()
        if row is None:
            return 0
        cnp = row["cnp"]
        seeds = SEED_BY_CNP.get(cnp, [])
        if not seeds:
            return 0
        for s in seeds:
            cur.execute(
                "insert into reminders (citizen_id, kind, procedure_id, redirect_target, "
                "title, due_date, status) values "
                "(%s, %s, %s, %s, %s, "
                "case when %s::int is null then null else current_date + (%s::int || ' days')::interval end, "
                "'pending');",
                (
                    str(citizen_id),
                    s["kind"],
                    s.get("procedure_id"),
                    s.get("redirect_target"),
                    s["title"],
                    s.get("due_offset_days"),
                    s.get("due_offset_days"),
                ),
            )
        conn.commit()
    return len(seeds)


@router.post("/reset", response_model=ResetResponse)
def reset_demo(
    body: ResetRequest,
    x_demo_token: str | None = Header(default=None),
) -> ResetResponse:
    _verify_token(x_demo_token)
    citizen_id = body.citizen_id or _resolve_default_citizen_id()
    counts = _wipe_citizen(citizen_id)
    seeded = _seed_for_citizen(citizen_id)
    return ResetResponse(
        ok=True,
        citizen_id=citizen_id,
        counts=ResetCounts(
            documents_deleted=counts["documents_deleted"],
            reminders_deleted=counts["reminders_deleted"],
            ledger_marked=counts["ledger_marked"],
            processed_events_deleted=counts["processed_events_deleted"],
            reminders_seeded=seeded,
        ),
    )
