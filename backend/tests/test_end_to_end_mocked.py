"""End-to-end happy-path test against a mocked DB layer.

Walks: login-roeid -> otp -> me -> create doc -> patch fields -> generate-pdf -> deliver -> ledger.
All DB and external calls mocked. Integration with a live Supabase is the separate apply_migrations
+ deployed smoke test (Task 18).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app

CITIZEN = UUID("11111111-1111-1111-1111-111111111111")
DOC = uuid4()


def _doc_row(
    status: str = "draft",
    fields: dict | None = None,
    pdf_url: str | None = None,
) -> dict:
    return {
        "id": DOC,
        "citizen_id": CITIZEN,
        "procedure_id": "schimbare-domiciliu",
        "status": status,
        "fields": fields or {},
        "pdf_url": pdf_url,
        "delivery": None,
        "ref_number": None,
        "created_at": datetime.now(timezone.utc),
        "delivered_at": None,
    }


# Full required set for schimbare-domiciliu (no applies_if conditionals fire
# without owns_vehicle etc. — the unconditional required set is enough).
_FULL_FIELDS = {
    "nume_complet": "Maria Ionescu",
    "cnp": "2851014123456",
    "adresa_curenta": "X",
    "adresa_noua": "Y",
    "tip_proprietate": "proprietar",
}


@patch("app.documents.append_ledger")
@patch("app.documents.fetch_ledger_for_document", return_value=[])
@patch("app.documents.finalize_document")
@patch("app.documents.upload_pdf_to_storage", return_value="https://x/pdf.pdf")
@patch("app.documents.render_and_compile", return_value=b"%PDF-1.4 fake")
@patch("app.documents.set_document_pdf_url")
@patch("app.documents.fetch_phone_for_citizen", return_value="+40712345678")
@patch("app.documents.send_delivery_sms")
@patch("app.documents.update_document_fields")
@patch("app.documents.fetch_document")
@patch("app.documents.insert_document")
@patch("app.documents._fetch_citizen_attributes", return_value={})
@patch("app.documents.verify_global_chain", return_value=True)
@patch("app.citizens.fetch_citizen_by_id")
@patch("app.auth.fetch_citizen_by_persona_id")
@patch("app.auth.issue_otp")
@patch("app.auth.verify_otp_and_consume")
def test_full_happy_path(
    mock_verify_otp: MagicMock,
    mock_issue: MagicMock,
    mock_fetch_persona: MagicMock,
    mock_fetch_citizen: MagicMock,
    mock_verify_chain: MagicMock,
    mock_fetch_attrs: MagicMock,
    mock_insert_doc: MagicMock,
    mock_fetch_doc: MagicMock,
    mock_update_doc: MagicMock,
    mock_send_sms: MagicMock,
    mock_phone: MagicMock,
    mock_set_pdf: MagicMock,
    mock_compile: MagicMock,
    mock_upload: MagicMock,
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
    # fetch_document is called by PATCH (pre-PATCH read), generate-pdf
    # (before rendering), deliver (must see the pdf_url set by generate-pdf),
    # and ledger (owner check). The side_effect cycles through the four
    # states this test exercises.
    mock_fetch_doc.side_effect = [
        _doc_row(fields=_FULL_FIELDS, pdf_url=None),
        _doc_row(fields=_FULL_FIELDS, pdf_url=None),
        _doc_row(fields=_FULL_FIELDS, pdf_url="https://x/pdf.pdf"),
        _doc_row(status="finalized", fields=_FULL_FIELDS, pdf_url="https://x/pdf.pdf"),
    ]
    mock_update_doc.return_value = _doc_row(fields=_FULL_FIELDS, pdf_url=None)
    finalized = _doc_row(status="finalized", fields=_FULL_FIELDS, pdf_url="https://x/pdf.pdf")
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

    # 6) deliver
    r7 = client.post(f"/documents/{doc_id}/deliver", json={"delivery": "send"}, headers=hdr)
    assert r7.status_code == 200
    assert r7.json()["ref_number"].startswith("CV-")

    # 7) ledger
    r8 = client.get(f"/documents/{doc_id}/ledger", headers=hdr)
    assert r8.status_code == 200
    assert r8.json()["verified"] is True
