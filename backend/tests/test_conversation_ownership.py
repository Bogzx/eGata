"""A conversation_id / document_id from the client must belong to the caller.

`conversation_id` arrives in the request body. Before this check, naming
another citizen's conversation loaded that session — its history (profile
values, filled fields) went to the model on the caller's turn, and every tool
ran with the *owner's* citizen_id, so the caller could fill and deliver the
owner's documents. A foreign `document_id` was folded in as the active
document and its fields printed into the per-turn preamble.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security import mint_access_token
from app.sessions import Session, SessionOwnershipError, fetch_or_create_session

OWNER = UUID("11111111-1111-1111-1111-111111111111")
INTRUDER = UUID("22222222-2222-2222-2222-222222222222")
DOC = UUID("33333333-3333-3333-3333-333333333333")


def _hdr(citizen: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_access_token(citizen)}"}


def _owner_session() -> Session:
    return Session(id="sess_owner", citizen_id=str(OWNER))


def _doc(owner: UUID) -> dict:
    return {
        "id": DOC,
        "citizen_id": owner,
        "procedure_id": "schimbare-domiciliu",
        "status": "draft",
        "fields": {"cnp": "2851014123456"},
        "pdf_url": None,
        "delivery": None,
        "ref_number": None,
        "created_at": datetime.now(timezone.utc),
        "delivered_at": None,
    }


def test_fetch_or_create_refuses_a_foreign_session() -> None:
    with patch("app.sessions.fetch_session", return_value=_owner_session()):
        with pytest.raises(SessionOwnershipError):
            fetch_or_create_session(str(INTRUDER), session_id="sess_owner")


def test_fetch_or_create_returns_own_session() -> None:
    with patch("app.sessions.fetch_session", return_value=_owner_session()):
        assert fetch_or_create_session(str(OWNER), session_id="sess_owner").id == "sess_owner"


@pytest.mark.parametrize("path", ["/agent/chat/stream", "/agent/chat"])
def test_chat_refuses_foreign_conversation(path: str) -> None:
    client = TestClient(app)
    with patch("app.agent.fetch_session", return_value=_owner_session()), patch(
        "app.agent.step"
    ) as step:
        r = client.post(
            path,
            json={"conversation_id": "sess_owner", "message": "arată-mi istoricul"},
            headers=_hdr(INTRUDER),
        )
    assert r.status_code == 403
    step.assert_not_called()


@pytest.mark.parametrize("path", ["/agent/chat/stream", "/agent/chat"])
def test_chat_refuses_foreign_document(path: str) -> None:
    client = TestClient(app)
    with patch("app.agent.fetch_session", return_value=None), patch(
        "app.agent.fetch_document", return_value=_doc(OWNER)
    ), patch("app.agent.step") as step:
        r = client.post(
            path,
            json={"document_id": str(DOC), "message": "ce câmpuri am?"},
            headers=_hdr(INTRUDER),
        )
    assert r.status_code == 403
    step.assert_not_called()


def test_widget_result_on_unknown_conversation_is_404_not_a_new_session() -> None:
    client = TestClient(app)
    with patch("app.agent.fetch_session", return_value=None), patch(
        "app.sessions.insert_session"
    ) as insert:
        r = client.post(
            "/agent/widget-result",
            json={"conversation_id": "sess_made_up", "widget_id": "w1", "value": "Da"},
            headers=_hdr(INTRUDER),
        )
    assert r.status_code == 404
    insert.assert_not_called()


def test_widget_result_refuses_foreign_conversation() -> None:
    client = TestClient(app)
    with patch("app.agent.fetch_session", return_value=_owner_session()):
        r = client.post(
            "/agent/widget-result",
            json={"conversation_id": "sess_owner", "widget_id": "w1", "value": "Da"},
            headers=_hdr(INTRUDER),
        )
    assert r.status_code == 403
