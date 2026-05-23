from __future__ import annotations

import hashlib
from typing import Any

import app.ledger as ledger_module
from app.ledger import (
    LedgerEventType,
    canonical_json,
    compute_payload_hash,
    compute_row_hash,
    verify_chain,
    verify_global_chain,
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


def _build_valid_global_chain(genesis: str) -> list[dict[str, Any]]:
    """A 3-row chain anchored on `genesis`, returned as rows the way
    `_fetch_full_ledger` would deliver them."""
    p1 = compute_payload_hash({"doc": "alpha"})
    r1 = compute_row_hash("doc_created", p1, genesis, "2026-05-23T10:00:00+00:00")
    p2 = compute_payload_hash({"doc": "beta"})
    r2 = compute_row_hash("doc_created", p2, r1, "2026-05-23T10:01:00+00:00")
    p3 = compute_payload_hash({"doc": "beta-pdf"})
    r3 = compute_row_hash("pdf_generated", p3, r2, "2026-05-23T10:02:00+00:00")
    return [
        {"event_type": "doc_created",   "payload": {"doc": "alpha"},    "payload_hash": p1, "prev_hash": genesis, "row_hash": r1, "created_at": "2026-05-23T10:00:00+00:00"},
        {"event_type": "doc_created",   "payload": {"doc": "beta"},     "payload_hash": p2, "prev_hash": r1,      "row_hash": r2, "created_at": "2026-05-23T10:01:00+00:00"},
        {"event_type": "pdf_generated", "payload": {"doc": "beta-pdf"}, "payload_hash": p3, "prev_hash": r2,      "row_hash": r3, "created_at": "2026-05-23T10:02:00+00:00"},
    ]


def test_verify_global_chain_passes_on_intact_chain(monkeypatch) -> None:
    """B1 regression: the per-document subset issue must not break global verify.

    The frontend's `verified` boolean depends on this returning True for an
    intact chain — pre-fix, it returned False whenever the per-document
    subset's first prev_hash didn't equal genesis."""
    genesis = "0x" + "0" * 64
    chain = _build_valid_global_chain(genesis)
    monkeypatch.setattr(ledger_module, "_fetch_full_ledger", lambda: chain)
    monkeypatch.setattr(ledger_module, "get_settings", lambda: type("S", (), {"ledger_genesis_hash": genesis})())
    ledger_module._invalidate_global_verified_cache()
    assert verify_global_chain(force=True) is True


def test_verify_global_chain_catches_tamper(monkeypatch) -> None:
    """A flipped payload anywhere in the chain must invalidate the global verify."""
    genesis = "0x" + "0" * 64
    chain = _build_valid_global_chain(genesis)
    # Tamper row 2's stored payload — payload_hash no longer matches.
    chain[1]["payload"] = {"doc": "BETA-TAMPERED"}
    monkeypatch.setattr(ledger_module, "_fetch_full_ledger", lambda: chain)
    monkeypatch.setattr(ledger_module, "get_settings", lambda: type("S", (), {"ledger_genesis_hash": genesis})())
    ledger_module._invalidate_global_verified_cache()
    assert verify_global_chain(force=True) is False


def test_verify_global_chain_cache_invalidated_on_append(monkeypatch) -> None:
    """After append_ledger writes a row, the cached verdict must clear so
    the next /ledger call re-verifies against the new tip."""
    genesis = "0x" + "0" * 64
    chain = _build_valid_global_chain(genesis)
    monkeypatch.setattr(ledger_module, "_fetch_full_ledger", lambda: chain)
    monkeypatch.setattr(ledger_module, "get_settings", lambda: type("S", (), {"ledger_genesis_hash": genesis})())
    ledger_module._invalidate_global_verified_cache()
    assert verify_global_chain() is True
    # Cache populated:
    assert ledger_module._global_verified_cache["verified"] is True
    # Simulate append invalidation:
    ledger_module._invalidate_global_verified_cache()
    assert ledger_module._global_verified_cache["verified"] is None


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
