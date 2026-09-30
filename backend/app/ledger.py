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
from app.ledger_signing import sign_row

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


_MAX_SAFE_INT = 2**53 - 1


def _require_portable(value: Any, path: str = "payload") -> None:
    """Only values every verifier encodes byte-for-byte like canonical_json.

    The browser (frontend/lib/ledgerVerify.ts) re-derives payload hashes with
    JSON.stringify, which writes 1.0 as `1` and 1e-07 as `1e-7`, and loses
    integers beyond 2**53. A payload holding one would hash differently there
    and an honest chain would show as broken, so it is refused here instead.
    """
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int):
        if abs(value) > _MAX_SAFE_INT:
            raise TypeError(f"{path}: integer outside ±2**53 is not portable")
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise TypeError(f"{path}: non-string key {k!r}")
            _require_portable(v, f"{path}.{k}")
        return
    if isinstance(value, list):
        for i, v in enumerate(value):
            _require_portable(v, f"{path}[{i}]")
        return
    raise TypeError(f"{path}: {type(value).__name__} is not allowed in a ledger payload")


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
    _require_portable(payload)
    doc = str(document_id) if document_id is not None else None
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select l.id, l.payload_hash, l.prev_hash, l.row_hash, "
            "ledger_row_ts_iso(l.created_at) as ts_iso "
            "from append_ledger(%s, %s, %s, %s) as l;",
            (str(citizen_id), doc, event_type.value, canonical_json(payload)),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("append_ledger returned no row")
        # Same transaction: a row is never committed without its signature.
        key_id, signature = sign_row(
            citizen_id=str(citizen_id), document_id=doc,
            row_id=int(row["id"]), row_hash=str(row["row_hash"]),
        )
        cur.execute(
            "insert into ledger_signatures (ledger_id, key_id, signature) values (%s, %s, %s);",
            (int(row["id"]), key_id, signature),
        )
        conn.commit()

    return {
        "id": int(row["id"]),
        "key_id": key_id,
        "signature": signature,
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
            "select l.id, l.citizen_id, l.document_id, l.event_type, l.payload, "
            "l.payload_hash, l.prev_hash, l.row_hash, l.created_at, "
            "ledger_row_ts_iso(l.created_at) as ts_iso, s.key_id, s.signature "
            "from ledger l left join ledger_signatures s on s.ledger_id = l.id "
            "where l.document_id = %s order by l.id asc;",
            (str(document_id),),
        )
        return list(cur.fetchall())


def sign_unsigned_rows(batch: int = 1000) -> int:
    """Sign the history written before rows were signed on append.

    Run at startup, so upgrading a deployment attests its existing history;
    ledger_signatures.signed_at records when. Only rows up to the watermark
    migrations/016 recorded are eligible: every later row was signed when it
    was appended, so a later unsigned row came from outside the backend
    (a direct append_ledger() call) and signing it would launder it. Those
    are left unsigned, and so unverifiable, and counted by
    `count_unsigned_after_watermark`. Returns how many rows were signed.
    """
    signed = 0
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute("select max_id from ledger_legacy_watermark;")
        mark = cur.fetchone()
        if mark is None:
            return 0
        while True:
            cur.execute(
                "select l.id, l.citizen_id, l.document_id, l.row_hash from ledger l "
                "where l.id <= %s and not exists "
                "(select 1 from ledger_signatures s where s.ledger_id = l.id) "
                "order by l.id limit %s;",
                (int(mark["max_id"]), batch),
            )
            rows = cur.fetchall()
            for r in rows:
                key_id, signature = sign_row(
                    citizen_id=str(r["citizen_id"]),
                    document_id=str(r["document_id"]) if r["document_id"] else None,
                    row_id=int(r["id"]), row_hash=str(r["row_hash"]),
                )
                cur.execute(
                    "insert into ledger_signatures (ledger_id, key_id, signature) "
                    "values (%s, %s, %s) on conflict (ledger_id) do nothing;",
                    (int(r["id"]), key_id, signature),
                )
            conn.commit()
            signed += len(rows)
            if len(rows) < batch:
                return signed


def count_unsigned_after_watermark() -> int:
    """Rows the backend did not append: unsigned, and newer than the history
    migrations/016 marked as predating signatures."""
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select count(*) as n from ledger l "
            "where l.id > (select max_id from ledger_legacy_watermark) and not exists "
            "(select 1 from ledger_signatures s where s.ledger_id = l.id);"
        )
        row = cur.fetchone()
    return int(row["n"]) if row else 0


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


def verify_signatures(
    rows: list[dict[str, Any]], *, citizen_id: str, document_id: str | None
) -> bool:
    """Every row carries a valid signature by a published key.

    Server-side counterpart of the signature check in scripts/verify_ledger.py
    and frontend/lib/ledgerVerify.ts.
    """
    import base64

    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    from app.ledger_signing import published_keys, statement

    keys = {k["key_id"]: base64.b64decode(k["public_key"]) for k in published_keys()}
    for r in rows:
        key_id, signature = r.get("key_id"), r.get("signature")
        if not key_id or not signature or key_id not in keys:
            return False
        stmt = statement(
            key_id=key_id, citizen_id=citizen_id, document_id=document_id,
            row_id=int(r["id"]), row_hash=str(r["row_hash"]),
        )
        try:
            Ed25519PublicKey.from_public_bytes(keys[key_id]).verify(
                base64.b64decode(signature), canonical_json(stmt).encode("utf-8")
            )
        except (InvalidSignature, ValueError):
            return False
    return True
