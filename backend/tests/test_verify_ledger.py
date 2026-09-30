"""The ledger can be checked without trusting the server.

`GET /documents/{id}/ledger` now returns each row's payload and the exact
timestamp string that was hashed, and `pdf_generated` rows carry the sha256
of the stored PDF. `scripts/verify_ledger.py` — stdlib only, no `app`
imports — must accept an honest export and reject a tampered one or a
swapped PDF.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.documents import pdf_generated_payload
from app.ledger import GENESIS_HASH, compute_payload_hash, compute_row_hash
from app.ledger_signing import sign_row
from app.main import app
from app.security import mint_access_token
from scripts import verify_ledger

CITIZEN = UUID("11111111-1111-1111-1111-111111111111")
DOC = UUID("44444444-4444-4444-4444-444444444444")
PDF = b"%PDF-1.4 the citizen's form"
FIELDS = {"nume_complet": "Maria Ionescu", "adresa_noua": "Str. Ștefan cel Mare 5"}


def _rows() -> list[dict]:
    events = [
        ("doc_created", {"document_id": str(DOC), "procedure_id": "schimbare-domiciliu"}),
        ("completed_draft", {"document_id": str(DOC)}),
        ("pdf_generated", pdf_generated_payload(DOC, f"{CITIZEN}/{DOC}.pdf", PDF, FIELDS)),
        ("delivered", {"document_id": str(DOC), "delivery": "save", "ref_number": "CV-4444"}),
    ]
    rows, prev = [], GENESIS_HASH
    base = datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)
    for i, (event_type, payload) in enumerate(events):
        ts = base + timedelta(seconds=i, microseconds=123)
        ts_iso = ts.strftime("%Y-%m-%dT%H:%M:%S.%f") + "+00:00"
        ph = compute_payload_hash(payload)
        rh = compute_row_hash(event_type, ph, prev, ts_iso)
        rows.append(
            {
                "id": i + 1,
                "event_type": event_type,
                # jsonb comes back from psycopg as a dict
                "payload": payload,
                "payload_hash": ph,
                "prev_hash": prev,
                "row_hash": rh,
                "created_at": ts,
                "ts_iso": ts_iso,
            }
        )
        rows[-1]["key_id"], rows[-1]["signature"] = sign_row(
            citizen_id=str(CITIZEN), document_id=str(DOC), row_id=i + 1, row_hash=rh
        )
        prev = rh
    return rows


def _export(rows: list[dict]) -> dict:
    doc = {
        "id": DOC,
        "citizen_id": CITIZEN,
        "procedure_id": "schimbare-domiciliu",
        "status": "finalized",
        "fields": FIELDS,
        "pdf_url": None,
        "delivery": "save",
        "ref_number": "CV-4444",
        "created_at": datetime.now(timezone.utc),
        "delivered_at": datetime.now(timezone.utc),
    }
    with patch("app.documents.fetch_document", return_value=doc), patch(
        "app.documents.fetch_ledger_for_document", return_value=rows
    ):
        r = TestClient(app).get(
            f"/documents/{DOC}/ledger",
            headers={"Authorization": f"Bearer {mint_access_token(CITIZEN)}"},
        )
    assert r.status_code == 200
    return r.json()


def _run(tmp_path: Path, body: dict, pdf: bytes | None = None) -> int:
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    argv = [str(ledger)]
    if pdf is not None:
        (tmp_path / "doc.pdf").write_bytes(pdf)
        argv += ["--pdf", str(tmp_path / "doc.pdf")]
    return verify_ledger.main(argv)


def test_api_exposes_what_a_verifier_needs() -> None:
    body = _export(_rows())
    assert body["verified"] is True
    assert body["genesis_hash"] == GENESIS_HASH
    first = body["entries"][0]
    assert first["payload"]["procedure_id"] == "schimbare-domiciliu"
    assert first["hashed_at"].endswith("+00:00")
    pdf_row = body["entries"][2]
    assert pdf_row["payload"]["pdf_sha256"] == verify_ledger._sha256(PDF)


def test_honest_export_and_pdf_verify(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(tmp_path, _export(_rows()), PDF) == 0
    assert "VERIFIED" in capsys.readouterr().out


def test_swapped_pdf_is_detected(tmp_path: Path) -> None:
    assert _run(tmp_path, _export(_rows()), b"%PDF-1.4 a different form") == 1


def test_edited_payload_is_detected(tmp_path: Path) -> None:
    body = _export(_rows())
    body["entries"][3]["payload"]["ref_number"] = "CV-FAKE"
    assert _run(tmp_path, body) == 1


def test_dropped_middle_row_is_detected(tmp_path: Path) -> None:
    body = _export(_rows())
    del body["entries"][1]
    assert _run(tmp_path, body) == 1


def test_romanian_text_survives_the_round_trip(tmp_path: Path) -> None:
    # ensure_ascii=False on both sides: "Ș" must hash as its UTF-8 bytes, not "\\u0218".
    rows = _rows()
    assert "Ștefan" in json.dumps(FIELDS, ensure_ascii=False)
    assert _run(tmp_path, _export(rows), PDF) == 0


def test_verifier_agrees_with_the_app_implementation() -> None:
    payload = {"b": "ăîâșț", "a": [1, 2], "c": {"z": None}}
    assert verify_ledger._sha256(
        verify_ledger._canonical_json(payload).encode()
    ) == compute_payload_hash(payload)
    assert verify_ledger.GENESIS_HASH == GENESIS_HASH


def test_pdf_generated_payload_binds_bytes_and_fields() -> None:
    p = pdf_generated_payload(DOC, "x/y.pdf", PDF, FIELDS)
    assert p["pdf_sha256"] == verify_ledger._sha256(PDF)
    other = pdf_generated_payload(DOC, "x/y.pdf", PDF, {**FIELDS, "adresa_noua": "alta"})
    assert other["fields_sha256"] != p["fields_sha256"]


def test_generate_pdf_endpoint_records_the_hash() -> None:
    doc = {
        "id": DOC,
        "citizen_id": CITIZEN,
        "procedure_id": "schimbare-domiciliu",
        "status": "draft",
        "fields": FIELDS,
        "pdf_url": None,
        "delivery": None,
        "ref_number": None,
        "created_at": datetime.now(timezone.utc),
        "delivered_at": None,
    }
    ledger = MagicMock()
    with patch("app.documents.fetch_document", return_value=doc), patch(
        "app.documents.render_and_compile", return_value=PDF
    ), patch("app.documents.upload_pdf_to_storage"), patch(
        "app.documents.set_document_pdf_url"
    ), patch("app.documents.create_signed_pdf_url", return_value="http://x/signed"), patch(
        "app.documents.append_ledger", ledger
    ):
        r = TestClient(app).post(
            f"/documents/{DOC}/generate-pdf",
            headers={"Authorization": f"Bearer {mint_access_token(CITIZEN)}"},
        )
    assert r.status_code == 200, r.text
    payload = ledger.call_args.kwargs["payload"]
    assert payload["pdf_sha256"] == verify_ledger._sha256(PDF)


# ---- signatures (migrations/014) ------------------------------------------


def test_stdlib_ed25519_matches_rfc8032_vector_1() -> None:
    pub = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    sig = bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )
    assert verify_ledger.ed25519_verify(pub, b"", sig)
    assert not verify_ledger.ed25519_verify(pub, b"x", sig)
    assert not verify_ledger.ed25519_verify(pub, b"", sig[:-1] + bytes([sig[-1] ^ 1]))


def test_stdlib_ed25519_agrees_with_cryptography() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    for i in range(5):
        key = Ed25519PrivateKey.generate()
        pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        msg = f"mesaj {i} ăîșț".encode() * (i + 1)
        sig = key.sign(msg)
        assert verify_ledger.ed25519_verify(pub, msg, sig)
        other = Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        assert not verify_ledger.ed25519_verify(other, msg, sig)


def _pinned() -> list[str]:
    from app.ledger_signing import signing_key

    return ["--public-key", signing_key().public_b64]


def test_signatures_verify_against_a_pinned_key(tmp_path: Path) -> None:
    body = _export(_rows())
    assert body["signing_keys"][0]["status"] == "current"
    ledger = tmp_path / "l.json"
    ledger.write_text(json.dumps(body), encoding="utf-8")
    assert verify_ledger.main([str(ledger), *_pinned()]) == 0


def test_a_chain_signed_by_another_key_is_rejected(tmp_path: Path) -> None:
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    # Someone with database access but not the key rebuilds the chain and
    # signs it with a key of their own, publishing that key in the export.
    body = _export(_rows())
    rogue = Ed25519PrivateKey.generate()
    raw = rogue.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    rogue_id = verify_ledger.key_id_for(raw)
    for e in body["entries"]:
        msg = verify_ledger._statement(rogue_id, body["citizen_id"], body["document_id"], e["id"], e["row_hash"])
        e["key_id"], e["signature"] = rogue_id, base64.b64encode(rogue.sign(msg)).decode()
    body["signing_keys"] = [{"key_id": rogue_id, "public_key": base64.b64encode(raw).decode(),
                             "algorithm": "Ed25519", "status": "current"}]
    ledger = tmp_path / "l.json"
    ledger.write_text(json.dumps(body), encoding="utf-8")
    assert verify_ledger.main([str(ledger)]) == 0  # self-consistent: why the key must be pinned
    assert verify_ledger.main([str(ledger), *_pinned()]) == 1


def test_unsigned_rows_fail_unless_allowed(tmp_path: Path) -> None:
    body = _export(_rows())
    body["entries"][1]["signature"] = None
    ledger = tmp_path / "l.json"
    ledger.write_text(json.dumps(body), encoding="utf-8")
    assert verify_ledger.main([str(ledger), *_pinned()]) == 1
    assert verify_ledger.main([str(ledger), *_pinned(), "--allow-unsigned"]) == 0


def test_receipt_proves_a_re_signed_rewrite(tmp_path: Path) -> None:
    """The key holder rewrites the last row and re-signs everything: the chain
    verifies again, but the citizen's earlier receipt no longer fits."""
    from app.ledger_signing import sign_row

    body = _export(_rows())
    ledger = tmp_path / "l.json"
    receipt = tmp_path / "receipt.json"
    ledger.write_text(json.dumps(body), encoding="utf-8")
    assert verify_ledger.main([str(ledger), *_pinned(), "--save-receipt", str(receipt)]) == 0
    assert verify_ledger.main([str(ledger), *_pinned(), "--receipt", str(receipt)]) == 0

    last = body["entries"][-1]
    last["payload"]["ref_number"] = "CV-ALTA"
    last["payload_hash"] = compute_payload_hash(last["payload"])
    last["row_hash"] = compute_row_hash(last["event_type"], last["payload_hash"], last["prev_hash"], last["hashed_at"])
    last["key_id"], last["signature"] = sign_row(
        citizen_id=body["citizen_id"], document_id=body["document_id"], row_id=last["id"], row_hash=last["row_hash"]
    )
    ledger.write_text(json.dumps(body), encoding="utf-8")
    assert verify_ledger.main([str(ledger), *_pinned()]) == 0
    assert verify_ledger.main([str(ledger), *_pinned(), "--receipt", str(receipt)]) == 1


def test_well_known_keys_endpoint_is_public() -> None:
    r = TestClient(app).get("/.well-known/egata-ledger-keys.json")
    assert r.status_code == 200
    keys = r.json()["keys"]
    assert keys[0]["key_id"].startswith("ed25519:") and keys[0]["status"] == "current"
