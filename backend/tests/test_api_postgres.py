"""The document API end-to-end against a real Postgres.

Opt-in like test_ledger_postgres.py: needs TEST_DATABASE_URL pointing at a
database with migrations/ applied (CI's backend-postgres job, or
`docker compose up -d db` + `python -m scripts.bootstrap_local_db`).

Everything else in the suite mocks the SQL layer. These drive the real
routes, real SQL, the real ledger function and the local storage backend, and
check the result with the independent verifier script — the path a citizen's
form actually takes. pdflatex is stubbed unless RUN_PDF_TESTS=1.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set; skipping real-Postgres API tests",
)

psycopg = pytest.importorskip("psycopg")

PROCEDURE = "schimbare-domiciliu"
FAKE_PDF = b"%PDF-1.4 stub render\n"


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    from fastapi.testclient import TestClient

    from app.config import get_settings

    monkeypatch.setenv("SUPABASE_DB_URL", TEST_DATABASE_URL or "")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("PDF_STORAGE_DIR", str(tmp_path / "pdfs"))
    get_settings.cache_clear()
    if os.environ.get("RUN_PDF_TESTS") != "1":
        monkeypatch.setattr("app.documents.render_and_compile", lambda *_a, **_k: FAKE_PDF)

    from app.main import app

    # No lifespan: the reminders worker has no business in these tests.
    yield TestClient(app)
    get_settings.cache_clear()


def _citizen() -> UUID:
    cid = uuid4()
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute(
            "insert into citizens (id, cnp, nume, prenume, data_nasterii, phone, attributes) "
            "values (%s, %s, 'Test', 'Api', '1990-01-01', '+40700000000', '{}'::jsonb);",
            (str(cid), f"9{cid.int % 10**12:012d}"),
        )
    return cid


def _hdr(cid: UUID) -> dict[str, str]:
    from app.security import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(cid)}"}


def _complete_fields() -> dict[str, Any]:
    from app.procedures import get_registry

    proc = get_registry()[PROCEDURE]
    return {
        f.name: (f.options[0] if f.options else f"valoare {f.name} ăîșț")
        for f in proc.fields
    }


def test_document_lifecycle_is_enforced_and_verifiable(api: Any, tmp_path: Path) -> None:
    from scripts import verify_ledger

    cid = _citizen()
    h = _hdr(cid)

    doc = api.post("/documents", json={"procedure_id": PROCEDURE}, headers=h).json()
    doc_id = doc["id"]

    # Schema validation on PATCH.
    r = api.patch(f"/documents/{doc_id}/fields", json={"fields": {"nu_exista": "x"}}, headers=h)
    assert r.status_code == 422
    r = api.patch(
        f"/documents/{doc_id}/fields", json={"fields": {"nume_complet": "x" * 5000}}, headers=h
    )
    assert r.status_code == 422

    fields = _complete_fields()
    r = api.patch(f"/documents/{doc_id}/fields", json={"fields": fields}, headers=h)
    assert r.status_code == 200, r.text

    # No PDF yet → cannot deliver.
    r = api.post(f"/documents/{doc_id}/deliver", json={"delivery": "save"}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "pdf_missing_or_stale"

    assert api.post(f"/documents/{doc_id}/generate-pdf", headers=h).status_code == 200

    # Edit after rendering → the PDF is stale → cannot deliver.
    first = next(iter(fields))
    r = api.patch(
        f"/documents/{doc_id}/fields",
        json={"fields": {first: fields[first] if isinstance(fields[first], bool) else "modificat"}},
        headers=h,
    )
    assert r.status_code == 200
    if not isinstance(fields[first], bool):
        r = api.post(f"/documents/{doc_id}/deliver", json={"delivery": "save"}, headers=h)
        assert r.status_code == 409

    gen = api.post(f"/documents/{doc_id}/generate-pdf", headers=h)
    assert gen.status_code == 200
    signed = urlparse(gen.json()["pdf_url"])

    r = api.post(f"/documents/{doc_id}/deliver", json={"delivery": "save"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "finalized"

    # Frozen after delivery.
    assert api.patch(
        f"/documents/{doc_id}/fields", json={"fields": {first: "altceva"}}, headers=h
    ).status_code == 409
    assert api.post(f"/documents/{doc_id}/generate-pdf", headers=h).status_code == 409
    assert api.post(
        f"/documents/{doc_id}/deliver", json={"delivery": "save"}, headers=h
    ).status_code == 409

    # The ledger verifies server-side AND with the independent script, and the
    # PDF served by the signed link is the one the ledger hashed.
    ledger = api.get(f"/documents/{doc_id}/ledger", headers=h).json()
    assert ledger["verified"] is True
    events = [e["event_type"] for e in ledger["entries"]]
    assert events.count("delivered") == 1
    assert events[0] == "doc_created" and events[-1] == "delivered"

    pdf = api.get(f"{signed.path}?{signed.query}")
    assert pdf.status_code == 200
    import json

    export = tmp_path / "ledger.json"
    export.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "doc.pdf").write_bytes(pdf.content)
    assert verify_ledger.main([str(export), "--pdf", str(tmp_path / "doc.pdf")]) == 0


def test_other_citizens_cannot_reach_a_document(api: Any) -> None:
    owner, intruder = _citizen(), _citizen()
    doc_id = api.post(
        "/documents", json={"procedure_id": PROCEDURE}, headers=_hdr(owner)
    ).json()["id"]
    h = _hdr(intruder)
    assert api.get(f"/documents/{doc_id}", headers=h).status_code == 403
    assert api.get(f"/documents/{doc_id}/ledger", headers=h).status_code == 403
    assert api.patch(
        f"/documents/{doc_id}/fields", json={"fields": {}}, headers=h
    ).status_code == 403
    r = api.post(
        "/agent/chat", json={"document_id": doc_id, "message": "salut"}, headers=h
    )
    assert r.status_code == 403


def test_foreign_conversation_is_refused_with_a_real_session(api: Any) -> None:
    from app.sessions import SessionOwnershipError, fetch_or_create_session, insert_session

    owner, intruder = _citizen(), _citizen()
    sess = insert_session(owner)
    with pytest.raises(SessionOwnershipError):
        fetch_or_create_session(intruder, session_id=sess.id)
    r = api.post(
        "/agent/chat/stream",
        json={"conversation_id": sess.id, "message": "ce am completat?"},
        headers=_hdr(intruder),
    )
    assert r.status_code == 403


def test_otp_guessing_is_capped(api: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.auth import MAX_OTP_ATTEMPTS

    monkeypatch.setenv("MOCK_OTP", "1")
    from app.config import get_settings

    get_settings.cache_clear()

    def challenge() -> str:
        r = api.post("/auth/login-roeid", json={"persona_id": "maria-ionescu"})
        assert r.status_code == 200, r.text
        return r.json()["challenge_id"]

    # A couple of typos, then the right code: still fine.
    ch = challenge()
    for _ in range(2):
        assert api.post("/auth/otp", json={"challenge_id": ch, "code": "000000"}).status_code == 401
    assert api.post("/auth/otp", json={"challenge_id": ch, "code": "123456"}).status_code == 200

    # Exhaust the attempts: the challenge is burned, even for the right code.
    ch = challenge()
    for _ in range(MAX_OTP_ATTEMPTS):
        assert api.post("/auth/otp", json={"challenge_id": ch, "code": "000000"}).status_code == 401
    r = api.post("/auth/otp", json={"challenge_id": ch, "code": "123456"})
    assert r.status_code == 401
