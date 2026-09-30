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
