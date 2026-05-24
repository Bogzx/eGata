"""Unit tests for app.citizens helpers."""
from __future__ import annotations

from datetime import date

from app.citizens import enrich_citizen_attrs


def test_enrich_merges_top_level_columns_into_attrs():
    citizen = {
        "id": "11111111-1111-1111-1111-111111111111",
        "cnp": "2851014123456",
        "nume": "Ionescu",
        "prenume": "Maria",
        "data_nasterii": date(1985, 3, 14),
        "email": "maria@example.com",
        "phone": "+40712345678",
        "attributes": {"owns_vehicle": True, "current_address": "Str. X 1"},
    }
    out = enrich_citizen_attrs(citizen)
    assert out["cnp"] == "2851014123456"
    assert out["nume"] == "Ionescu"
    assert out["prenume"] == "Maria"
    assert out["email"] == "maria@example.com"
    assert out["phone"] == "+40712345678"
    assert out["nume_complet"] == "Maria Ionescu"
    assert out["owns_vehicle"] is True
    assert out["current_address"] == "Str. X 1"


def test_enrich_handles_null_attributes():
    citizen = {
        "id": "x",
        "cnp": "123",
        "nume": "Test",
        "prenume": "User",
        "attributes": None,
    }
    out = enrich_citizen_attrs(citizen)
    assert out["cnp"] == "123"
    assert out["nume_complet"] == "User Test"


def test_enrich_top_level_overrides_malformed_attrs():
    citizen = {
        "cnp": "RIGHT",
        "nume": "Real",
        "prenume": "Name",
        "attributes": {"cnp": "WRONG"},
    }
    out = enrich_citizen_attrs(citizen)
    assert out["cnp"] == "RIGHT"


def test_enrich_skips_empty_string_columns():
    citizen = {
        "cnp": "123",
        "nume": "Test",
        "prenume": "",
        "email": "",
        "attributes": {},
    }
    out = enrich_citizen_attrs(citizen)
    assert out["cnp"] == "123"
    assert "email" not in out
    assert out["nume_complet"] == "Test"  # prenume empty → just nume
