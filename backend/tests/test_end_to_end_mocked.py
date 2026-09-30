"""End-to-end happy-path test against a mocked DB layer.

Walks: login-roeid -> otp -> me -> create doc -> patch fields -> generate-pdf -> deliver -> ledger.
All DB and external calls mocked. Integration with a live Supabase is the separate apply_migrations
+ deployed smoke test (Task 18).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.documents import pdf_generated_payload
from app.ledger import GENESIS_HASH, compute_payload_hash, compute_row_hash
from app.ledger_signing import sign_row
from app.main import app

CITIZEN = UUID("11111111-1111-1111-1111-111111111111")
DOC = uuid4()
FILLED = {
    "nume_complet": "Maria Ionescu", "cnp": "2851014123456",
    "adresa_curenta": "X", "adresa_noua": "Y", "tip_proprietate": "proprietar",
}


def _chain_for_document(document_id: str) -> list[dict]:
    """Build the ledger rows the DB would hold for one finished document.

    Mirrors migrations/009: each chain starts at the genesis hash, the
    timestamp inside row_hash is the one stored, and `ts_iso` is the string
    the SQL side hashed.
    """
    genesis = GENESIS_HASH
    events = [
        ("doc_created", {"document_id": document_id, "procedure_id": "schimbare-domiciliu"}),
        ("completed_draft", {"document_id": document_id}),
        ("pdf_generated", pdf_generated_payload(
            document_id, f"{CITIZEN}/{document_id}.pdf", b"%PDF-1.4 fake", FILLED,
        )),
        ("delivered", {"document_id": document_id, "delivery": "send", "ref_number": "CV-AAAA"}),
    ]
    rows: list[dict] = []
    prev = genesis
    base = datetime(2026, 5, 23, 10, 0, 0, tzinfo=timezone.utc)
    for i, (event_type, payload) in enumerate(events):
        ts = base + timedelta(seconds=i)
        ts_iso = ts.strftime("%Y-%m-%dT%H:%M:%S.%f") + "+00:00"
        payload_hash = compute_payload_hash(payload)
        row_hash = compute_row_hash(event_type, payload_hash, prev, ts_iso)
        rows.append({
            "id": i + 1,
            "event_type": event_type,
            "payload": payload,
            "payload_hash": payload_hash,
            "prev_hash": prev,
            "row_hash": row_hash,
            "created_at": ts,
            "ts_iso": ts_iso,
        })
        rows[-1]["key_id"], rows[-1]["signature"] = sign_row(
            citizen_id=str(CITIZEN), document_id=document_id, row_id=i + 1, row_hash=row_hash,
        )
        prev = row_hash
    return rows


def _doc_row(status: str = "draft", fields: dict | None = None) -> dict:
    return {
        "id": DOC,
        "citizen_id": CITIZEN,
        "procedure_id": "schimbare-domiciliu",
        "status": status,
        "fields": fields or {},
        "pdf_url": None,
        "delivery": None,
        "ref_number": None,
        "created_at": datetime.now(timezone.utc),
        "delivered_at": None,
    }


@patch("app.documents.append_ledger")
@patch("app.documents.fetch_ledger_for_document")
@patch("app.documents.finalize_document")
@patch("app.documents.create_signed_pdf_url", return_value="https://x/pdf.pdf?token=sig")
@patch("app.documents.upload_pdf_to_storage", return_value="11111111-1111-1111-1111-111111111111/doc.pdf")
@patch("app.documents.render_and_compile", return_value=b"%PDF-1.4 fake")
@patch("app.documents.set_document_pdf_url")
@patch("app.documents.fetch_phone_for_citizen", return_value="+40712345678")
@patch("app.documents.send_delivery_sms")
@patch("app.documents.update_document_fields")
@patch("app.documents.fetch_document")
@patch("app.documents.insert_document")
@patch("app.citizens.fetch_citizen_by_id")
@patch("app.auth.fetch_citizen_by_persona_id")
@patch("app.auth.issue_otp")
@patch("app.auth.verify_otp_and_consume")
def test_full_happy_path(
    mock_verify_otp: MagicMock,
    mock_issue: MagicMock,
    mock_fetch_persona: MagicMock,
    mock_fetch_citizen: MagicMock,
    mock_insert_doc: MagicMock,
    mock_fetch_doc: MagicMock,
    mock_update_doc: MagicMock,
    mock_send_sms: MagicMock,
    mock_phone: MagicMock,
    mock_set_pdf: MagicMock,
    mock_compile: MagicMock,
    mock_upload: MagicMock,
    mock_sign: MagicMock,
    mock_finalize: MagicMock,
    mock_fetch_ledger: MagicMock,
    mock_ledger: MagicMock,
) -> None:
    mock_fetch_persona.return_value = {"id": str(CITIZEN), "phone": "+40712345678", "nume": "Ionescu"}
    mock_issue.return_value = "ch_e2e"
    mock_verify_otp.return_value = str(CITIZEN)
    mock_fetch_citizen.return_value = {
        "id": CITIZEN,
        "cnp": "2851014123456",
        "nume": "Ionescu",
        "prenume": "Maria",
        "data_nasterii": "1985-03-14",
        "email": "maria@example.com",
        "phone": "+40712345678",
        "attributes": {},
    }
    mock_insert_doc.return_value = _doc_row()
    mock_fetch_doc.return_value = _doc_row(fields={
        "nume_complet": "Maria Ionescu", "cnp": "2851014123456",
        "adresa_curenta": "X", "adresa_noua": "Y", "tip_proprietate": "proprietar",
    })
    mock_update_doc.return_value = _doc_row(fields={
        "nume_complet": "Maria Ionescu", "cnp": "2851014123456",
        "adresa_curenta": "X", "adresa_noua": "Y", "tip_proprietate": "proprietar",
    })
    finalized = _doc_row(status="finalized")
    finalized["delivery"] = "send"
    finalized["ref_number"] = "CV-AAAA"
    finalized["delivered_at"] = datetime.now(timezone.utc)
    mock_finalize.return_value = finalized

    client = TestClient(app)

    # 1) login + otp
    r1 = client.post("/auth/login-roeid", json={})
    assert r1.status_code == 200
    challenge = r1.json()["challenge_id"]
    r2 = client.post("/auth/otp", json={"challenge_id": challenge, "code": "123456"})
    assert r2.status_code == 200
    token = r2.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}

    # 2) profile
    r3 = client.get("/citizens/me", headers=hdr)
    assert r3.status_code == 200

    # 3) create doc
    r4 = client.post("/documents", json={"procedure_id": "schimbare-domiciliu"}, headers=hdr)
    assert r4.status_code == 201
    doc_id = r4.json()["id"]

    # 4) patch fields
    r5 = client.patch(
        f"/documents/{doc_id}/fields",
        json={"fields": {"adresa_noua": "Y"}},
        headers=hdr,
    )
    assert r5.status_code == 200

    # 5) generate pdf
    r6 = client.post(f"/documents/{doc_id}/generate-pdf", headers=hdr)
    assert r6.status_code == 200
    # The response carries a freshly signed link, and what got persisted is
    # the storage object path — not a permanent public URL (storage.py).
    assert r6.json()["pdf_url"] == "https://x/pdf.pdf?token=sig"
    assert mock_upload.call_args.args[0] == f"{CITIZEN}/{doc_id}.pdf"
    assert mock_set_pdf.call_args.args[1] == f"{CITIZEN}/{doc_id}.pdf"

    # 6) deliver — the row now points at the rendered PDF, and the ledger's
    # pdf_generated row was rendered from the current fields.
    rendered = _doc_row(fields=FILLED)
    rendered["pdf_url"] = f"{CITIZEN}/{doc_id}.pdf"
    mock_fetch_doc.return_value = rendered
    mock_fetch_ledger.return_value = _chain_for_document(str(DOC))[:3]
    r7 = client.post(f"/documents/{doc_id}/deliver", json={"delivery": "send"}, headers=hdr)
    assert r7.status_code == 200
    assert r7.json()["ref_number"].startswith("CV-")

    # 7) ledger — a real four-link chain, not an empty list.
    #
    # This assertion used to run against `return_value=[]`: verify_chain([])
    # is vacuously True, so the endpoint's whole reason for existing went
    # untested. Feed it the rows the DB would actually return for this
    # document and assert the badge is earned.
    mock_fetch_ledger.return_value = _chain_for_document(str(DOC))
    r8 = client.get(f"/documents/{doc_id}/ledger", headers=hdr)
    assert r8.status_code == 200
    body8 = r8.json()
    assert len(body8["entries"]) == 4
    assert [e["event_type"] for e in body8["entries"]] == [
        "doc_created", "completed_draft", "pdf_generated", "delivered",
    ]
    assert body8["verified"] is True

    # And the badge must go red when a payload no longer matches its hash.
    tampered = _chain_for_document(str(DOC))
    tampered[2]["payload"] = {"document_id": str(DOC), "pdf_url": "https://evil/x.pdf"}
    mock_fetch_ledger.return_value = tampered
    r9 = client.get(f"/documents/{doc_id}/ledger", headers=hdr)
    assert r9.status_code == 200
    assert r9.json()["verified"] is False
