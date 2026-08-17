"""Hash-chain ledger module."""
from __future__ import annotations

import enum
import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from app.config import get_settings
from app.db import get_pg_connection


class LedgerEventType(str, enum.Enum):
    DOC_CREATED = "doc_created"
    COMPLETED_DRAFT = "completed_draft"
    PDF_GENERATED = "pdf_generated"
    DELIVERED = "delivered"
    REDIRECTED = "redirected"
    REMINDER_CREATED = "reminder_created"
    # Appended by POST /demo/reset instead of deleting rows — the ledger is
    # append-only (migrations/009), so a reset is recorded, not erased.
    DEMO_RESET = "demo_reset"


def canonical_json(value: Any) -> str:
    """Stable JSON: keys sorted, no whitespace, ensure_ascii=False for RO chars."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_payload_hash(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return "0x" + digest


def compute_row_hash(event_type: str, payload_hash: str, prev_hash: str, iso_ts: str) -> str:
    raw = event_type + payload_hash + prev_hash + iso_ts
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return "0x" + digest


def fetch_tip_hash(
    citizen_id: UUID | str, document_id: UUID | str | None = None
) -> str:
    """Tip of the chain this row will extend.

    Scoped to (citizen_id, document_id) — the same slice
    `fetch_ledger_for_document` reads back and `verify_chain` walks. Chaining
    against a global tip while verifying a document-scoped slice is what made
    the "verificat" badge unreachable; see migrations/009.
    """
    settings = get_settings()
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select ledger_tip_hash(%s, %s) as tip;",
            (
                str(citizen_id),
                str(document_id) if document_id is not None else None,
            ),
        )
        row = cur.fetchone()
    if row is None or row["tip"] is None:
        return settings.ledger_genesis_hash
    return str(row["tip"])


def append_ledger(
    citizen_id: UUID | str,
    event_type: LedgerEventType,
    payload: dict[str, Any],
    document_id: UUID | str | None = None,
) -> dict[str, Any]:
    """Append a ledger row via the Postgres append_ledger() function.

    Nothing hash-shaped crosses the wire: the function receives the canonical
    JSON and derives payload_hash, prev_hash, the timestamp and row_hash
    itself, then returns what it stored. A caller cannot write a row whose
    hash disagrees with its payload.
    """
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select l.id, l.payload_hash, l.prev_hash, l.row_hash, "
            "ledger_row_ts_iso(l.created_at) as ts_iso "
            "from append_ledger(%s, %s, %s, %s) as l;",
            (
                str(citizen_id),
                str(document_id) if document_id is not None else None,
                event_type.value,
                canonical_json(payload),
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("append_ledger returned no row")
        conn.commit()

    return {
        "id": int(row["id"]),
        "event_type": event_type.value,
        "payload": payload,
        "payload_hash": str(row["payload_hash"]),
        "prev_hash": str(row["prev_hash"]),
        "row_hash": str(row["row_hash"]),
        "created_at": str(row["ts_iso"]),
    }


def fetch_ledger_for_document(document_id: UUID | str) -> list[dict[str, Any]]:
    """Read one document's chain.

    `ts_iso` is rendered by the same SQL expression the append function hashed,
    so verification does not depend on the session TimeZone or on Python's
    isoformat trimming rules.
    """
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, event_type, payload, payload_hash, prev_hash, row_hash, "
            "created_at, ledger_row_ts_iso(created_at) as ts_iso "
            "from ledger where document_id = %s order by id asc;",
            (str(document_id),),
        )
        return list(cur.fetchall())


def verify_chain(rows: list[dict[str, Any]], genesis_hash: str) -> bool:
    """Walk the chain end-to-end. Returns True if every link checks out."""
    prev = genesis_hash
    for r in rows:
        payload_field = r.get("payload", {})
        payload = json.loads(payload_field) if isinstance(payload_field, str) else payload_field
        expected_payload_hash = compute_payload_hash(payload)
        if expected_payload_hash != r["payload_hash"]:
            return False
        if r["prev_hash"] != prev:
            return False
        # `ts_iso` is the exact string the DB hashed (ledger_row_ts_iso).
        # Fall back to created_at for hand-built chains in tests.
        ts = r.get("ts_iso") or r["created_at"]
        if isinstance(ts, datetime):
            ts = ts.isoformat()
        expected_row_hash = compute_row_hash(r["event_type"], r["payload_hash"], r["prev_hash"], ts)
        if expected_row_hash != r["row_hash"]:
            return False
        prev = r["row_hash"]
    return True
