"""Hash-chain ledger module."""
from __future__ import annotations

import enum
import hashlib
import json
import time
from datetime import datetime, timezone
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


def _fetch_tip_hash() -> str:
    settings = get_settings()
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute("select ledger_tip_hash() as tip;")
        row = cur.fetchone()
    if row is None or row["tip"] is None:
        return settings.ledger_genesis_hash
    return str(row["tip"])


# ---- Global verification with cache ----------------------------------------
#
# `verify_chain` over a per-document subset always returns False in practice:
# the subset's first row's `prev_hash` references a ledger row that belongs
# to a different document (or the genesis row), not `genesis_hash` itself.
# Per-document `/ledger` responses therefore can't use the subset directly.
#
# Fix: verify the whole chain from genesis, cache the result, and return the
# cached verdict for per-document responses. The cache invalidates on every
# successful append so a tampered DB write is caught on the next /ledger
# call. TTL is a fallback for clock skew / cold start.

_GLOBAL_VERIFY_TTL_SECONDS = 60.0
_global_verified_cache: dict[str, Any] = {"verified": None, "stamp": 0.0}


def _invalidate_global_verified_cache() -> None:
    """Called by `append_ledger` after a successful insert."""
    _global_verified_cache["verified"] = None
    _global_verified_cache["stamp"] = 0.0


def append_ledger(
    citizen_id: UUID | str,
    event_type: LedgerEventType,
    payload: dict[str, Any],
    document_id: UUID | str | None = None,
) -> dict[str, Any]:
    """Append a ledger row via the Postgres append_ledger() function.

    Returns the inserted row data (event_type, hashes, created_at).
    Raises if prev_hash mismatch (chain integrity violation).
    """
    prev_hash = _fetch_tip_hash()
    payload_hash = compute_payload_hash(payload)
    iso_ts = datetime.now(timezone.utc).isoformat()
    row_hash = compute_row_hash(event_type.value, payload_hash, prev_hash, iso_ts)

    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select append_ledger(%s, %s, %s, %s::jsonb, %s, %s, %s) as id;",
            (
                str(citizen_id),
                str(document_id) if document_id is not None else None,
                event_type.value,
                canonical_json(payload),
                payload_hash,
                prev_hash,
                row_hash,
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("append_ledger returned no row")
        conn.commit()
        ledger_id = int(row["id"])

    # The global verified cache becomes stale on append. Invalidate so
    # the next /ledger response recomputes against the updated chain.
    _invalidate_global_verified_cache()

    return {
        "id": ledger_id,
        "event_type": event_type.value,
        "payload": payload,
        "payload_hash": payload_hash,
        "prev_hash": prev_hash,
        "row_hash": row_hash,
        "created_at": iso_ts,
    }


def fetch_ledger_for_document(document_id: UUID | str) -> list[dict[str, Any]]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, event_type, payload, payload_hash, prev_hash, row_hash, created_at "
            "from ledger where document_id = %s order by id asc;",
            (str(document_id),),
        )
        return list(cur.fetchall())


def verify_chain(rows: list[dict[str, Any]], genesis_hash: str) -> bool:
    """Walk the chain end-to-end. Returns True if every link checks out.

    Pass `genesis_hash` as the anchor for the very first row's `prev_hash`.
    Callers that hold a per-document subset must pass the row_hash of the
    row immediately preceding the subset (use `verify_global_chain` for
    that — it walks the whole ledger from genesis and is what the HTTP
    `/documents/{id}/ledger` route uses).
    """
    prev = genesis_hash
    for r in rows:
        payload_field = r.get("payload", {})
        payload = json.loads(payload_field) if isinstance(payload_field, str) else payload_field
        expected_payload_hash = compute_payload_hash(payload)
        if expected_payload_hash != r["payload_hash"]:
            return False
        if r["prev_hash"] != prev:
            return False
        ts = r["created_at"]
        if isinstance(ts, datetime):
            ts = ts.isoformat()
        expected_row_hash = compute_row_hash(r["event_type"], r["payload_hash"], r["prev_hash"], ts)
        if expected_row_hash != r["row_hash"]:
            return False
        prev = r["row_hash"]
    return True


def _fetch_full_ledger() -> list[dict[str, Any]]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, event_type, payload, payload_hash, prev_hash, row_hash, created_at "
            "from ledger order by id asc;"
        )
        return list(cur.fetchall())


def verify_global_chain(*, force: bool = False) -> bool:
    """Verify the entire ledger from genesis. Cached for `_GLOBAL_VERIFY_TTL_SECONDS`.

    Use this for the per-document `verified` boolean — the chain is global,
    not per-document, so the only sound answer is "is the whole chain intact."
    """
    now = time.monotonic()
    cached = _global_verified_cache.get("verified")
    cached_age = now - float(_global_verified_cache.get("stamp") or 0.0)
    if not force and cached is not None and cached_age < _GLOBAL_VERIFY_TTL_SECONDS:
        return bool(cached)
    rows = _fetch_full_ledger()
    result = verify_chain(rows, get_settings().ledger_genesis_hash)
    _global_verified_cache["verified"] = result
    _global_verified_cache["stamp"] = now
    return result
