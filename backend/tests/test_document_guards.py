"""Offline checks for the document guards (the real-DB flow is in
test_api_postgres.py)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.agent_tools import ToolContext
from app.agent_tools.set_field import execute as set_field
from app.documents import _require_draft, _validated_patch
from app.procedure_state import MAX_FIELD_LENGTH
from app.sessions import Session, SessionState

CITIZEN = "11111111-1111-1111-1111-111111111111"


def test_patch_rejects_unknown_fields() -> None:
    with pytest.raises(HTTPException) as exc:
        _validated_patch("schimbare-domiciliu", {"is_admin": True})
    assert exc.value.status_code == 422


def test_patch_rejects_values_outside_the_options() -> None:
    with pytest.raises(HTTPException) as exc:
        _validated_patch("schimbare-domiciliu", {"tip_proprietate": "castel"})
    assert exc.value.status_code == 422


def test_patch_normalizes_option_case() -> None:
    assert _validated_patch("schimbare-domiciliu", {"tip_proprietate": "Proprietar"}) == {
        "tip_proprietate": "proprietar"
    }


@pytest.mark.parametrize("bad", ["x" * (MAX_FIELD_LENGTH + 1), {"nested": 1}, [1, 2]])
def test_patch_rejects_oversized_or_structured_values(bad: object) -> None:
    with pytest.raises(HTTPException):
        _validated_patch("schimbare-domiciliu", {"adresa_noua": bad})


def test_finalized_documents_are_frozen() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_draft({"status": "finalized", "ref_number": "CV-1234"})
    assert exc.value.status_code == 409
    _require_draft({"status": "draft"})


def test_agent_cannot_edit_a_finalized_document() -> None:
    session = Session(
        id="s", citizen_id=CITIZEN, state=SessionState.REVIEWING, active_document_id=
        "44444444-4444-4444-4444-444444444444",
    )
    doc = {
        "id": UUID(session.active_document_id),
        "citizen_id": UUID(CITIZEN),
        "procedure_id": "schimbare-domiciliu",
        "status": "finalized",
        "fields": {},
        "created_at": datetime.now(timezone.utc),
    }
    with patch("app.agent_tools.set_field.fetch_document", return_value=doc), patch(
        "app.agent_tools.set_field.update_document_fields"
    ) as update:
        result = asyncio.run(
            set_field(session, ToolContext(citizen_id=CITIZEN), name="adresa_noua", value="x")
        )
    assert result.error
    update.assert_not_called()


def test_ref_numbers_do_not_collide_at_realistic_volume() -> None:
    from uuid import uuid4

    from app.documents import generate_ref_number

    refs = {generate_ref_number(uuid4()) for _ in range(20_000)}
    assert len(refs) == 20_000  # 4 hex digits collided within a few hundred
    assert generate_ref_number(UUID("3b66227a-2d74-422e-ba0d-fd6063d7e95d")) == "CV-3B66-227A"
