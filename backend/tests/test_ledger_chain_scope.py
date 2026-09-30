"""The hash chain must be scoped the same way it is read back.

The bug this pins down: `append_ledger` chained every row against a *global*
tip (ledger.py `_fetch_tip_hash` -> `ledger_tip_hash()` in
migrations/003_ledger_function.sql:23-26, `order by id desc limit 1` over the
whole table) but `/documents/{id}/ledger` reads rows back filtered by
`document_id` and verifies that slice against the genesis hash. As soon as a
second document exists, its first row's `prev_hash` points at some *other*
document's row_hash, which is not in the slice — so `verify_chain` returns
False and the UI renders the red "neverificat" badge (AuditTimeline.tsx:47-54)
for every document but the first.

`FakeLedgerDB` below models the SQL side of both migrations so the test
exercises the real `app.ledger` code paths:

  * a `ledger_tip_hash()` call with no arguments  -> migration 003, global tip
  * a `ledger_tip_hash(citizen, document)` call   -> migration 009, scoped tip

Against migration 003 the interleaved test below fails on document #2.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest

from app import ledger as ledger_mod
from app.ledger import (
    LedgerEventType,
    append_ledger,
    canonical_json,
    fetch_ledger_for_document,
    verify_chain,
)

GENESIS = "0x" + "0" * 64
CITIZEN = UUID("11111111-1111-1111-1111-111111111111")
DOC_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DOC_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _sha(text: str) -> str:
    return "0x" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class FakeLedgerDB:
    """In-memory stand-in for the `ledger` table + its two SQL functions."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        # migrations/014: ledger_signatures, keyed by ledger id.
        self.signatures: dict[int, tuple[str, str]] = {}
        self._clock = datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc)
        self.rejected_updates = 0

    def _next_ts(self) -> datetime:
        self._clock += timedelta(seconds=1)
        return self._clock

    @staticmethod
    def _ts_iso(ts: datetime) -> str:
        # Mirrors the to_char(... 'YYYY-MM-DD"T"HH24:MI:SS.US') || '+00:00'
        # expression migration 009 uses on both write and read.
        return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "+00:00"

    def tip_global(self) -> str:
        """migration 003: ledger_tip_hash() — last row in the whole table."""
        return self.rows[-1]["row_hash"] if self.rows else GENESIS

    def tip_scoped(self, citizen_id: str, document_id: str | None) -> str:
        """migration 009: ledger_tip_hash(citizen, document) — last row of
        this (citizen, document) chain, `is not distinct from` on the doc."""
        for row in reversed(self.rows):
            if row["citizen_id"] == citizen_id and row["document_id"] == document_id:
                return str(row["row_hash"])
        return GENESIS

    def append_recomputing(
        self,
        citizen_id: str,
        document_id: str | None,
        event_type: str,
        payload_canonical: str,
    ) -> dict[str, Any]:
        """migration 009: the server derives prev_hash, both hashes and the
        timestamp itself — nothing hash-shaped comes from the caller."""
        prev_hash = self.tip_scoped(citizen_id, document_id)
        payload_hash = _sha(payload_canonical)
        ts = self._next_ts()
        ts_iso = self._ts_iso(ts)
        row_hash = _sha(event_type + payload_hash + prev_hash + ts_iso)
        row = {
            "id": len(self.rows) + 1,
            "citizen_id": citizen_id,
            "document_id": document_id,
            "event_type": event_type,
            "payload": json.loads(payload_canonical),
            "payload_hash": payload_hash,
            "prev_hash": prev_hash,
            "row_hash": row_hash,
            "created_at": ts,
            "ts_iso": ts_iso,
        }
        self.rows.append(row)
        return row

    def append_trusting(
        self,
        citizen_id: str,
        document_id: str | None,
        event_type: str,
        payload: str,
        payload_hash: str,
        expected_prev_hash: str,
        row_hash: str,
    ) -> dict[str, Any]:
        """migration 003: global tip, caller-supplied hashes stored verbatim.

        Note what is *not* in the argument list: the timestamp. The old
        `append_ledger` hashed a `datetime.now()` it computed in Python but
        never sent it, so `created_at` fell through to the column's
        `default now()` — a different instant from the one inside row_hash.
        The fake reproduces that by stamping its own clock.
        """
        if self.tip_global() != expected_prev_hash:
            raise RuntimeError("append_ledger: prev_hash mismatch")
        row = {
            "id": len(self.rows) + 1,
            "citizen_id": citizen_id,
            "document_id": document_id,
            "event_type": event_type,
            "payload": json.loads(payload),
            "payload_hash": payload_hash,
            "prev_hash": expected_prev_hash,
            "row_hash": row_hash,
            "created_at": self._next_ts(),
        }
        self.rows.append(row)
        return row

    def for_document(self, document_id: str) -> list[dict[str, Any]]:
        out = []
        for r in self.rows:
            if r["document_id"] != document_id:
                continue
            key_id, signature = self.signatures.get(r["id"], (None, None))
            out.append({**r, "key_id": key_id, "signature": signature})
        return out


class _FakeCursor:
    def __init__(self, db: FakeLedgerDB) -> None:
        self.db = db
        self._result: list[dict[str, Any]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        s = " ".join(sql.split()).lower()

        if "ledger_tip_hash()" in s:
            self._result = [{"tip": self.db.tip_global()}]
        elif "ledger_tip_hash(" in s:
            self._result = [{"tip": self.db.tip_scoped(params[0], params[1])}]
        elif "append_ledger(" in s and len(params) == 4:
            self._result = [self.db.append_recomputing(*params)]
        elif "append_ledger(" in s:
            self._result = [self.db.append_trusting(*params)]
        elif "from ledger where document_id" in s or "where l.document_id" in s:
            self._result = self.db.for_document(params[0])
        elif s.startswith("insert into ledger_signatures"):
            self.db.signatures[int(params[0])] = (params[1], params[2])
            self._result = []
        elif s.startswith("update ledger") or s.startswith("delete from ledger"):
            # The immutability trigger added in migration 009.
            self.db.rejected_updates += 1
            raise RuntimeError("ledger is append-only")
        else:  # pragma: no cover - unexpected statement
            raise AssertionError(f"FakeLedgerDB got unexpected SQL: {sql!r}")

    def fetchone(self) -> dict[str, Any] | None:
        return self._result[0] if self._result else None

    def fetchall(self) -> list[dict[str, Any]]:
        return self._result


class _FakeConn:
    def __init__(self, db: FakeLedgerDB) -> None:
        self.db = db
        self.commits = 0

    def __enter__(self) -> _FakeConn:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self.db)

    def commit(self) -> None:
        self.commits += 1


@pytest.fixture
def fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeLedgerDB:
    db = FakeLedgerDB()
    monkeypatch.setattr(ledger_mod, "get_pg_connection", lambda: _FakeConn(db))
    return db


def _write(document_id: UUID, event: LedgerEventType, n: int) -> None:
    append_ledger(
        citizen_id=CITIZEN,
        event_type=event,
        payload={"document_id": str(document_id), "n": n},
        document_id=document_id,
    )


def test_two_interleaved_documents_both_verify(fake_db: FakeLedgerDB) -> None:
    """The regression test for the red-badge bug.

    Two documents written interleaved, exactly as two browser tabs (or one
    citizen finishing a second procedure) would produce. Each document's
    slice must verify on its own against the genesis hash, because that is
    how /documents/{id}/ledger reads it back.
    """
    _write(DOC_A, LedgerEventType.DOC_CREATED, 1)
    _write(DOC_B, LedgerEventType.DOC_CREATED, 2)
    _write(DOC_A, LedgerEventType.COMPLETED_DRAFT, 3)
    _write(DOC_B, LedgerEventType.COMPLETED_DRAFT, 4)
    _write(DOC_A, LedgerEventType.PDF_GENERATED, 5)
    _write(DOC_B, LedgerEventType.DELIVERED, 6)

    rows_a = fetch_ledger_for_document(DOC_A)
    rows_b = fetch_ledger_for_document(DOC_B)
    assert len(rows_a) == 3
    assert len(rows_b) == 3

    assert verify_chain(rows_a, GENESIS) is True, "document A's chain must verify"
    assert verify_chain(rows_b, GENESIS) is True, (
        "document B's chain must verify — before the fix its first row chained "
        "against document A's row_hash, which is not in B's slice, so the UI "
        "showed the red 'neverificat' badge for every document but the first"
    )


def test_each_document_chain_starts_at_genesis(fake_db: FakeLedgerDB) -> None:
    _write(DOC_A, LedgerEventType.DOC_CREATED, 1)
    _write(DOC_B, LedgerEventType.DOC_CREATED, 2)

    assert fetch_ledger_for_document(DOC_A)[0]["prev_hash"] == GENESIS
    assert fetch_ledger_for_document(DOC_B)[0]["prev_hash"] == GENESIS


def test_rows_within_a_document_chain_to_each_other(fake_db: FakeLedgerDB) -> None:
    _write(DOC_A, LedgerEventType.DOC_CREATED, 1)
    _write(DOC_B, LedgerEventType.DOC_CREATED, 2)
    _write(DOC_A, LedgerEventType.COMPLETED_DRAFT, 3)

    rows = fetch_ledger_for_document(DOC_A)
    assert rows[1]["prev_hash"] == rows[0]["row_hash"]


def test_tampering_with_one_document_leaves_the_other_verifiable(
    fake_db: FakeLedgerDB,
) -> None:
    """Per-document scoping is a deliberate trade-off: a tampered row breaks
    its own document's chain, not every document written afterwards."""
    _write(DOC_A, LedgerEventType.DOC_CREATED, 1)
    _write(DOC_B, LedgerEventType.DOC_CREATED, 2)
    _write(DOC_A, LedgerEventType.COMPLETED_DRAFT, 3)

    fake_db.rows[0]["payload"] = {"document_id": str(DOC_A), "n": 999}

    assert verify_chain(fetch_ledger_for_document(DOC_A), GENESIS) is False
    assert verify_chain(fetch_ledger_for_document(DOC_B), GENESIS) is True


def test_caller_supplied_hashes_are_not_trusted(fake_db: FakeLedgerDB) -> None:
    """The append call must not carry a hash the server stores verbatim.

    migrations/003 took `p_payload_hash` and `p_row_hash` from the caller and
    inserted them unchanged, so anyone able to call the function could write a
    row whose stored hash did not describe its payload. The server derives
    both now — this asserts the wire call carries no hash-shaped argument.
    """
    captured: list[tuple[Any, ...]] = []
    real_execute = _FakeCursor.execute

    def spy(self: _FakeCursor, sql: str, params: tuple[Any, ...] = ()) -> None:
        if "append_ledger(" in sql:
            captured.append(params)
        real_execute(self, sql, params)

    _FakeCursor.execute = spy  # type: ignore[method-assign]
    try:
        _write(DOC_A, LedgerEventType.DOC_CREATED, 1)
    finally:
        _FakeCursor.execute = real_execute  # type: ignore[method-assign]

    assert captured, "append_ledger was never called"
    params = captured[0]
    assert len(params) == 4, (
        "append_ledger should take (citizen, document, event_type, canonical_payload) "
        f"and derive the hashes itself; got {len(params)} arguments"
    )
    for value in params:
        assert not (isinstance(value, str) and value.startswith("0x") and len(value) == 66), (
            f"a hash was passed to append_ledger and would be stored verbatim: {value}"
        )


def test_appended_row_payload_hash_describes_the_payload(fake_db: FakeLedgerDB) -> None:
    payload = {"document_id": str(DOC_A), "n": 1}
    result = append_ledger(
        citizen_id=CITIZEN,
        event_type=LedgerEventType.DOC_CREATED,
        payload=payload,
        document_id=DOC_A,
    )
    assert result["payload_hash"] == _sha(canonical_json(payload))
    assert result["prev_hash"] == GENESIS
    assert result["row_hash"] == _sha(
        "doc_created" + result["payload_hash"] + GENESIS + result["created_at"]
    )


def test_citizen_level_events_form_their_own_chain(fake_db: FakeLedgerDB) -> None:
    """Rows with no document (reminders.py writes these) must not be dragged
    into any document's chain, nor drag a document's chain out of shape."""
    append_ledger(
        citizen_id=CITIZEN,
        event_type=LedgerEventType.REMINDER_CREATED,
        payload={"title": "x"},
        document_id=None,
    )
    _write(DOC_A, LedgerEventType.DOC_CREATED, 1)
    append_ledger(
        citizen_id=CITIZEN,
        event_type=LedgerEventType.REMINDER_CREATED,
        payload={"title": "y"},
        document_id=None,
    )

    rows_a = fetch_ledger_for_document(DOC_A)
    assert len(rows_a) == 1
    assert rows_a[0]["prev_hash"] == GENESIS
    assert verify_chain(rows_a, GENESIS) is True

    citizen_rows = [r for r in fake_db.rows if r["document_id"] is None]
    assert citizen_rows[0]["prev_hash"] == GENESIS
    assert citizen_rows[1]["prev_hash"] == citizen_rows[0]["row_hash"]
