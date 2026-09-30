"""Integration tests for migrations/009 against a real Postgres.

Opt-in: set TEST_DATABASE_URL to a database that has had `migrations/` applied
(CI does this against a pgvector service container; locally,
`docker compose up -d db` then point at it). Skipped otherwise, so the default
`pytest` run stays offline.

These exist because the rest of the ledger suite models the SQL rather than
running it. The load-bearing claim — that the timestamp string Postgres hashes
inside `append_ledger` is byte-identical to the one `ledger_row_ts_iso` renders
on read, and that Python's `verify_chain` agrees with both — can only be
checked by a real server.
"""
from __future__ import annotations

import os
from typing import Any
from uuid import UUID, uuid4

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set; skipping real-Postgres ledger tests",
)

psycopg = pytest.importorskip("psycopg")


@pytest.fixture
def pg(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Point app.ledger at TEST_DATABASE_URL and hand back a raw connection."""
    from psycopg.rows import dict_row

    from app import ledger as ledger_mod

    monkeypatch.setattr(
        ledger_mod,
        "get_pg_connection",
        lambda: psycopg.connect(TEST_DATABASE_URL, row_factory=dict_row),
    )
    with psycopg.connect(TEST_DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        yield conn


@pytest.fixture
def citizen_id(pg: Any) -> UUID:
    cid = uuid4()
    with pg.cursor() as cur:
        cur.execute(
            "insert into citizens (id, cnp, nume, prenume, data_nasterii, phone) "
            "values (%s, %s, 'Test', 'Ledger', '1990-01-01', '+40700000000');",
            (str(cid), f"TEST{cid.hex[:9]}"),
        )
    return cid


def _new_document(pg: Any, citizen_id: UUID) -> UUID:
    did = uuid4()
    with pg.cursor() as cur:
        cur.execute(
            "insert into documents (id, citizen_id, procedure_id) "
            "values (%s, %s, 'schimbare-domiciliu');",
            (str(did), str(citizen_id)),
        )
    return did


def test_interleaved_documents_verify_against_real_postgres(
    pg: Any, citizen_id: UUID
) -> None:
    from app.ledger import (
        GENESIS_HASH,
        LedgerEventType,
        append_ledger,
        fetch_ledger_for_document,
        verify_chain,
    )

    doc_a = _new_document(pg, citizen_id)
    doc_b = _new_document(pg, citizen_id)

    for i, (doc, event) in enumerate(
        [
            (doc_a, LedgerEventType.DOC_CREATED),
            (doc_b, LedgerEventType.DOC_CREATED),
            (doc_a, LedgerEventType.COMPLETED_DRAFT),
            (doc_b, LedgerEventType.COMPLETED_DRAFT),
            (doc_a, LedgerEventType.PDF_GENERATED),
            (doc_b, LedgerEventType.DELIVERED),
        ]
    ):
        append_ledger(
            citizen_id=citizen_id,
            event_type=event,
            payload={"document_id": str(doc), "n": i, "ro": "diacritice: ăîâșț"},
            document_id=doc,
        )

    genesis = GENESIS_HASH
    rows_a = fetch_ledger_for_document(doc_a)
    rows_b = fetch_ledger_for_document(doc_b)

    assert len(rows_a) == 3
    assert len(rows_b) == 3
    assert rows_a[0]["prev_hash"] == genesis
    assert rows_b[0]["prev_hash"] == genesis
    assert verify_chain(rows_a, genesis) is True
    assert verify_chain(rows_b, genesis) is True


def test_citizen_scoped_rows_do_not_join_a_document_chain(
    pg: Any, citizen_id: UUID
) -> None:
    from app.ledger import (
        GENESIS_HASH,
        LedgerEventType,
        append_ledger,
        fetch_ledger_for_document,
        verify_chain,
    )

    append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.REMINDER_CREATED,
        payload={"title": "before"},
        document_id=None,
    )
    doc = _new_document(pg, citizen_id)
    append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.DOC_CREATED,
        payload={"document_id": str(doc)},
        document_id=doc,
    )

    genesis = GENESIS_HASH
    rows = fetch_ledger_for_document(doc)
    assert len(rows) == 1
    assert rows[0]["prev_hash"] == genesis
    assert verify_chain(rows, genesis) is True


def test_update_is_rejected(pg: Any, citizen_id: UUID) -> None:
    from app.ledger import LedgerEventType, append_ledger

    doc = _new_document(pg, citizen_id)
    row = append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.DOC_CREATED,
        payload={"document_id": str(doc)},
        document_id=doc,
    )
    with pytest.raises(psycopg.errors.RestrictViolation), pg.cursor() as cur:
        cur.execute(
            "update ledger set payload = '{\"tampered\": true}'::jsonb where id = %s;",
            (row["id"],),
        )


def test_delete_is_rejected(pg: Any, citizen_id: UUID) -> None:
    from app.ledger import LedgerEventType, append_ledger

    doc = _new_document(pg, citizen_id)
    row = append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.DOC_CREATED,
        payload={"document_id": str(doc)},
        document_id=doc,
    )
    with pytest.raises(psycopg.errors.RestrictViolation), pg.cursor() as cur:
        cur.execute("delete from ledger where id = %s;", (row["id"],))


def test_truncate_is_rejected(pg: Any, citizen_id: UUID) -> None:
    """Row-level triggers do not fire on TRUNCATE and the owner keeps the
    privilege, so 009's UPDATE/DELETE triggers alone still allowed
    `truncate ledger` to empty the chain in one statement (migrations/011)."""
    from app.ledger import LedgerEventType, append_ledger

    doc = _new_document(pg, citizen_id)
    append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.DOC_CREATED,
        payload={"document_id": str(doc)},
        document_id=doc,
    )
    with pytest.raises(psycopg.errors.RestrictViolation), pg.cursor() as cur:
        cur.execute("truncate ledger cascade;")


def test_stored_hashes_are_server_derived(pg: Any, citizen_id: UUID) -> None:
    """The row the server stored must describe the payload the server stored,
    with no help from the caller."""
    from app.ledger import (
        LedgerEventType,
        append_ledger,
        canonical_json,
        compute_payload_hash,
        compute_row_hash,
    )

    doc = _new_document(pg, citizen_id)
    payload = {"document_id": str(doc), "note": "ăîâșț & 100%"}
    result = append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.DOC_CREATED,
        payload=payload,
        document_id=doc,
    )

    assert result["payload_hash"] == compute_payload_hash(payload)
    assert result["row_hash"] == compute_row_hash(
        "doc_created",
        result["payload_hash"],
        result["prev_hash"],
        result["created_at"],
    )

    with pg.cursor() as cur:
        cur.execute(
            "select payload::text as p, payload_hash, row_hash, "
            "ledger_row_ts_iso(created_at) as ts_iso from ledger where id = %s;",
            (result["id"],),
        )
        stored = cur.fetchone()

    assert stored is not None
    # The read-side timestamp expression reproduces exactly what was hashed.
    assert stored["ts_iso"] == result["created_at"]
    assert stored["payload_hash"] == result["payload_hash"]
    assert stored["row_hash"] == result["row_hash"]
    # jsonb round-trips our canonical form without changing any value.
    import json

    assert canonical_json(json.loads(stored["p"])) == canonical_json(payload)


def test_invalid_event_type_is_rejected(pg: Any, citizen_id: UUID) -> None:
    with pytest.raises(psycopg.errors.RaiseException), pg.cursor() as cur:
        cur.execute(
            "select * from append_ledger(%s, null, 'not_a_real_event', '{}');",
            (str(citizen_id),),
        )


# ---- migrations/014: signatures and the least-privilege role ---------------

APP_DATABASE_URL = os.environ.get("APP_DATABASE_URL")


def test_every_appended_row_is_signed(pg: Any, citizen_id: UUID) -> None:
    from app.ledger import LedgerEventType, append_ledger, fetch_ledger_for_document, verify_signatures

    doc = _new_document(pg, citizen_id)
    for event in (LedgerEventType.DOC_CREATED, LedgerEventType.COMPLETED_DRAFT):
        append_ledger(citizen_id=citizen_id, event_type=event, payload={"d": str(doc)}, document_id=doc)
    rows = fetch_ledger_for_document(doc)
    assert all(r["signature"] and r["key_id"] for r in rows)
    assert verify_signatures(rows, citizen_id=str(citizen_id), document_id=str(doc))
    # A signature is bound to its chain: the same rows do not verify as
    # another citizen's.
    assert not verify_signatures(rows, citizen_id=str(uuid4()), document_id=str(doc))


def test_rows_from_before_signing_are_signed_at_startup(pg: Any, citizen_id: UUID) -> None:
    from app.ledger import fetch_ledger_for_document, sign_unsigned_rows, verify_signatures

    doc = _new_document(pg, citizen_id)
    with pg.cursor() as cur:  # an old-style append: no signature row
        cur.execute(
            "select * from append_ledger(%s, %s, 'doc_created', '{}');", (str(citizen_id), str(doc))
        )
    assert fetch_ledger_for_document(doc)[0]["signature"] is None
    assert sign_unsigned_rows() >= 1
    rows = fetch_ledger_for_document(doc)
    assert verify_signatures(rows, citizen_id=str(citizen_id), document_id=str(doc))


def test_signatures_are_append_only(pg: Any, citizen_id: UUID) -> None:
    from app.ledger import LedgerEventType, append_ledger

    row = append_ledger(citizen_id=citizen_id, event_type=LedgerEventType.DOC_CREATED, payload={})
    with pytest.raises(psycopg.errors.RestrictViolation), pg.cursor() as cur:
        cur.execute("update ledger_signatures set signature = 'x' where ledger_id = %s;", (row["id"],))


@pytest.mark.skipif(not APP_DATABASE_URL, reason="APP_DATABASE_URL (egata_app login) not set")
def test_app_role_can_only_append_through_the_function(citizen_id: UUID) -> None:
    from psycopg.rows import dict_row

    with psycopg.connect(APP_DATABASE_URL, row_factory=dict_row, autocommit=True) as app:
        row = app.execute(
            "select id from append_ledger(%s, null, 'doc_created', '{}');", (str(citizen_id),)
        ).fetchone()
        assert row is not None
        for sql, params in (
            (
                "insert into ledger (citizen_id, event_type, payload_hash, prev_hash, row_hash) "
                "values (gen_random_uuid(), 'doc_created', 'x', 'y', 'z')",
                (),
            ),
            ("update ledger set row_hash = 'x' where id = %s", (row["id"],)),
            ("delete from ledger where id = %s", (row["id"],)),
            ("alter table ledger disable trigger ledger_no_update", ()),
            ("drop trigger ledger_no_delete on ledger", ()),
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                app.execute(sql, params)
