from __future__ import annotations

import hashlib

from app.ledger import (
    LedgerEventType,
    canonical_json,
    compute_payload_hash,
    compute_row_hash,
    verify_chain,
)


def test_canonical_json_is_stable() -> None:
    a = canonical_json({"b": 1, "a": [3, 2, 1]})
    b = canonical_json({"a": [3, 2, 1], "b": 1})
    assert a == b
    assert a == '{"a":[3,2,1],"b":1}'


def test_payload_hash_is_sha256_of_canonical_json() -> None:
    payload = {"x": 1, "y": "two"}
    h = compute_payload_hash(payload)
    expected = "0x" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    assert h == expected


def test_row_hash_combines_event_payload_prev_ts() -> None:
    h = compute_row_hash(
        event_type="doc_created",
        payload_hash="0x" + "a" * 64,
        prev_hash="0x" + "0" * 64,
        iso_ts="2026-05-23T10:00:00+00:00",
    )
    raw = "doc_created" + ("0x" + "a" * 64) + ("0x" + "0" * 64) + "2026-05-23T10:00:00+00:00"
    expected = "0x" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert h == expected


def test_event_type_enum_matches_spec() -> None:
    expected = {
        "doc_created",
        "completed_draft",
        "pdf_generated",
        "delivered",
        "redirected",
        "reminder_created",
    }
    assert {e.value for e in LedgerEventType} == expected


def test_verify_chain_accepts_valid_chain() -> None:
    genesis = "0x" + "0" * 64
    p1 = compute_payload_hash({"n": 1})
    r1 = compute_row_hash("doc_created", p1, genesis, "2026-05-23T10:00:00+00:00")
    p2 = compute_payload_hash({"n": 2})
    r2 = compute_row_hash("completed_draft", p2, r1, "2026-05-23T10:01:00+00:00")
    chain = [
        {
            "event_type": "doc_created",
            "payload": {"n": 1},
            "payload_hash": p1,
            "prev_hash": genesis,
            "row_hash": r1,
            "created_at": "2026-05-23T10:00:00+00:00",
        },
        {
            "event_type": "completed_draft",
            "payload": {"n": 2},
            "payload_hash": p2,
            "prev_hash": r1,
            "row_hash": r2,
            "created_at": "2026-05-23T10:01:00+00:00",
        },
    ]
    assert verify_chain(chain, genesis) is True


def test_verify_chain_rejects_tampered_payload() -> None:
    genesis = "0x" + "0" * 64
    p1 = compute_payload_hash({"n": 1})
    r1 = compute_row_hash("doc_created", p1, genesis, "2026-05-23T10:00:00+00:00")
    chain = [
        {
            "event_type": "doc_created",
            "payload": {"n": 999},  # tampered
            "payload_hash": p1,
            "prev_hash": genesis,
            "row_hash": r1,
            "created_at": "2026-05-23T10:00:00+00:00",
        }
    ]
    assert verify_chain(chain, genesis) is False


def test_verify_chain_rejects_broken_link() -> None:
    genesis = "0x" + "0" * 64
    p1 = compute_payload_hash({"n": 1})
    r1 = compute_row_hash("doc_created", p1, genesis, "2026-05-23T10:00:00+00:00")
    p2 = compute_payload_hash({"n": 2})
    bad_prev = "0x" + "f" * 64
    r2 = compute_row_hash("completed_draft", p2, bad_prev, "2026-05-23T10:01:00+00:00")
    chain = [
        {
            "event_type": "doc_created", "payload": {"n": 1}, "payload_hash": p1,
            "prev_hash": genesis, "row_hash": r1, "created_at": "2026-05-23T10:00:00+00:00",
        },
        {
            "event_type": "completed_draft", "payload": {"n": 2}, "payload_hash": p2,
            "prev_hash": bad_prev, "row_hash": r2, "created_at": "2026-05-23T10:01:00+00:00",
        },
    ]
    assert verify_chain(chain, genesis) is False
