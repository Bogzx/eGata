"""Hash-chain ledger module.

Row format (migrations/009 computes it; `verify_chain` and the standalone
`scripts/verify_ledger.py` recompute it):

    payload_hash = sha256(canonical_json(payload))
    row_hash     = sha256(event_type || payload_hash || prev_hash || ts_iso)

Each (citizen, document) pair is its own chain, starting at GENESIS_HASH.
"""
from __future__ import annotations

import enum
import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from app.db import get_pg_connection

# The first prev_hash of every chain. A protocol constant, not configuration:
# `ledger_tip_hash()` in migrations/009 hard-codes the same value, so a
# different genesis on the Python side (the old LEDGER_GENESIS_HASH setting)
# only made every chain fail verification.
GENESIS_HASH = "0x" + "0" * 64


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


def sha256_hex(data: bytes) -> str:
    """`0x`-prefixed sha256, the ledger's hash notation."""
    return "0x" + hashlib.sha256(data).hexdigest()


def verify_chain(rows: list[dict[str, Any]], genesis_hash: str = GENESIS_HASH) -> bool:
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
