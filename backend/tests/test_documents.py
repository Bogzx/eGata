"""Unit tests for app.documents pure helpers (no DB required)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

from app.documents import generate_ref_number, generate_submit_ref_number


def test_generate_ref_number_legacy_format():
    """Legacy CV-XXXX format used by the /deliver endpoint."""
    doc_id = UUID("3b66227a-2d74-422e-ba0d-fd6063d7e95d")
    ref = generate_ref_number(doc_id)
    assert ref == "CV-3B66"


def test_generate_submit_ref_number_format():
    doc_id = UUID("3b66227a-2d74-422e-ba0d-fd6063d7e95d")
    ref = generate_submit_ref_number(doc_id)
    expected_year = datetime.now(timezone.utc).year
    assert ref == f"REG-{expected_year}-3B66227A"


def test_generate_submit_ref_number_is_deterministic():
    """Same doc → same ref (so the 409 path can return the original)."""
    doc_id = UUID("11111111-2222-3333-4444-555555555555")
    assert generate_submit_ref_number(doc_id) == generate_submit_ref_number(doc_id)


def test_generate_submit_ref_number_matches_spec():
    doc_id = UUID("3b66227a-2d74-422e-ba0d-fd6063d7e95d")
    ref = generate_submit_ref_number(doc_id)
    assert re.match(r"^REG-\d{4}-[0-9A-F]{8}$", ref)
