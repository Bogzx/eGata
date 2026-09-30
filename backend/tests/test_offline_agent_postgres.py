"""The offline agent, end to end, against a real Postgres.

Opt-in (TEST_DATABASE_URL, migrations applied — bootstrap_local_db also
builds the offline search index this relies on). Drives the chat the way the
frontend does: chat turns, plus /agent/widget-result for widget clicks with
the follow-up turn the store sends when `requires_chat_followup` is set.
pdflatex is stubbed unless RUN_PDF_TESTS=1.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set; skipping real-Postgres offline-agent tests",
)

psycopg = pytest.importorskip("psycopg")


class Chat:
    def __init__(self, client: Any, citizen: UUID) -> None:
        from app.security import mint_access_token

        self.client = client
        self.h = {"Authorization": f"Bearer {mint_access_token(citizen)}"}
        self.conv: str | None = None

    def say(self, message: str) -> dict[str, Any]:
        r = self.client.post(
            "/agent/chat", json={"conversation_id": self.conv, "message": message}, headers=self.h
        )
        assert r.status_code == 200, r.text
        body = r.json()
        self.conv = body["conversation_id"]
        return body

    def session(self) -> Any:
        from app.sessions import fetch_session

        assert self.conv
        return fetch_session(self.conv)

    def click(self, value: str, question_contains: str = "") -> dict[str, Any] | None:
        pending = [w for w in self.session().pending_widgets if question_contains in w.question]
        assert pending, f"no pending widget matching {question_contains!r}"
        r = self.client.post(
            "/agent/widget-result",
            json={"conversation_id": self.conv, "widget_id": pending[0].widget_id, "value": value},
            headers=self.h,
        )
        assert r.status_code == 200, r.text
        return self.say(value) if r.json()["requires_chat_followup"] else None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    from fastapi.testclient import TestClient

    from app.config import get_settings

    # The app itself connects as the least-privilege role when one is
    # configured (migrations/014) — the whole flow must work without owner
    # rights. Test fixtures keep writing with TEST_DATABASE_URL.
    monkeypatch.setenv("SUPABASE_DB_URL", os.environ.get("APP_DATABASE_URL") or TEST_DATABASE_URL or "")
    monkeypatch.setenv("AGENT_BACKEND", "offline")
    monkeypatch.setenv("EMBEDDINGS_BACKEND", "local")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("PDF_STORAGE_DIR", str(tmp_path / "pdfs"))
    get_settings.cache_clear()
    if os.environ.get("RUN_PDF_TESTS") != "1":
        monkeypatch.setattr(
            "app.agent_tools.complete_document.render_and_compile",
            lambda *_a, **_k: b"%PDF-1.4 stub\n",
        )
    from app.main import app

    yield TestClient(app)
    get_settings.cache_clear()


def _citizen() -> UUID:
    cid = uuid4()
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute(
            "insert into citizens (id, cnp, nume, prenume, data_nasterii, phone, email, attributes) "
            "values (%s, %s, 'Ionescu', 'Maria', '1985-10-14', '+40712345678', "
            "'maria@example.com', %s::jsonb);",
            (
                str(cid),
                f"2{cid.int % 10**12:012d}",
                json.dumps({"current_address": "Str. Veche 1, Cluj-Napoca"}),
            ),
        )
    return cid


def test_offline_conversation_from_request_to_verified_delivery(client: Any) -> None:
    from app.offline_agent import OFFLINE_NOTICE

    chat = Chat(client, _citizen())

    first = chat.say("vreau să-mi schimb domiciliul")
    assert first["message"].startswith(OFFLINE_NOTICE)
    assert "Schimbare domiciliu" in first["message"]
    assert chat.session().state.value == "confirming_match"

    opened = chat.click("Da", "Completăm")
    assert opened is not None
    assert [t["name"] for t in opened["tool_calls"]][:1] == ["start_procedure"]
    s = chat.session()
    assert s.state.value == "filling"
    doc_id = s.active_document_id

    # Profile values were filled server-side; the agent only asks the rest.
    doc = client.get(f"/documents/{doc_id}", headers=chat.h).json()
    assert doc["fields"]["nume_complet"] == "Maria Ionescu"
    assert doc["fields"]["adresa_curenta"] == "Str. Veche 1, Cluj-Napoca"
    assert "Adresă nouă" in opened["message"]

    chat.say("Str. Lungă 3, Cluj-Napoca")  # typed answer to the question asked
    reviewing = chat.click("proprietar", "Tip proprietate")  # last field → review
    assert reviewing is not None and chat.session().state.value == "reviewing"

    chat.click("Da", "Verifică datele")
    done = chat.click("Salvare PDF", "Cum vrei")
    assert done is not None
    assert chat.session().state.value == "delivered"
    assert "CV-" in done["message"]

    ledger = client.get(f"/documents/{doc_id}/ledger", headers=chat.h).json()
    assert ledger["verified"] is True
    assert [e["event_type"] for e in ledger["entries"]] == [
        "doc_created", "completed_draft", "pdf_generated", "delivered",
    ]


def test_typed_answers_work_without_clicking(client: Any) -> None:
    chat = Chat(client, _citizen())
    chat.say("vreau să-mi schimb domiciliul")
    chat.say("da")
    chat.say("Str. Nouă 7")
    chat.say("chiriaș")  # the option typed instead of clicked
    assert chat.session().state.value == "reviewing"
    chat.say("da")  # confirm the review by typing
    done = chat.say("salvare")
    assert chat.session().state.value == "delivered", done["message"]


def test_review_correction_and_reset(client: Any) -> None:
    chat = Chat(client, _citizen())
    chat.say("vreau să-mi schimb domiciliul")
    chat.say("da")
    chat.say("Str. Nouă 7")
    chat.say("proprietar")
    reply = chat.say("Adresă nouă: Str. Corectată 9")
    assert "Am modificat" in reply["message"]
    doc = client.get(f"/documents/{chat.session().active_document_id}", headers=chat.h).json()
    assert doc["fields"]["adresa_noua"] == "Str. Corectată 9"

    chat.say("renunț")
    assert chat.session().state.value == "exploring"
    assert chat.session().active_document_id is None


def test_out_of_scope_request_is_redirected(client: Any) -> None:
    chat = Chat(client, _citizen())
    reply = chat.say("am nevoie de un medic de familie")
    assert "CNAS" in reply["message"]
    assert chat.session().state.value == "redirected"
    # ...and a real request afterwards still works.
    chat.say("vreau certificat fiscal")
    assert chat.session().state.value == "confirming_match"


def test_ambiguous_request_offers_a_choice(client: Any) -> None:
    chat = Chat(client, _citizen())
    chat.say("certificat de urbanism")
    pending = chat.session().pending_widgets
    assert pending and pending[0].type == "choice" and len(pending[0].options) >= 3
    opened = chat.click(pending[0].options[0])
    assert opened is not None and chat.session().state.value == "filling"


def test_streaming_endpoint_in_offline_mode(client: Any) -> None:
    chat = Chat(client, _citizen())
    r = client.post(
        "/agent/chat/stream", json={"message": "vreau să tai un copac din curte"}, headers=chat.h
    )
    assert r.status_code == 200
    frames = [line.split(": ", 1)[1] for line in r.text.splitlines() if line.startswith("event: ")]
    assert frames[0] == "conversation"
    assert "frontend_event" in frames and frames[-1] == "done"


def test_address_parts_are_prefilled_not_asked(client: Any) -> None:
    """A citizen whose profile address is one string gets street / number /
    locality / county filled from it (app/address.py) instead of being asked."""
    chat = Chat(client, _citizen())
    chat.say("am pierdut buletinul")
    opened = chat.say("da")
    doc = client.get(f"/documents/{chat.session().active_document_id}", headers=chat.h).json()
    assert doc["fields"]["strada"] == "Veche"
    assert doc["fields"]["numar"] == "1"
    assert doc["fields"]["localitate"] == "Cluj-Napoca"
    assert doc["fields"]["judet"] == "Cluj"
    assert "Strada?" not in opened["message"]
