"""Romanian address parsing (app/address.py) and its use in autofill."""
from __future__ import annotations

import pytest

from app.address import parse_ro_address


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Str. Avram Iancu 5, Cluj-Napoca",
            {"strada": "Avram Iancu", "numar": "5", "localitate": "Cluj-Napoca", "judet": "Cluj"},
        ),
        (
            "Strada Memorandumului nr. 12, bl. B2, sc. 1, et. 3, ap. 12, Cluj-Napoca, jud. Cluj",
            {"strada": "Memorandumului", "numar": "12", "bloc": "B2", "scara": "1", "etaj": "3",
             "apartament": "12", "localitate": "Cluj-Napoca", "judet": "Cluj"},
        ),
        (
            "Bd. 21 Decembrie 1989 nr. 104, ap. 7B, Cluj-Napoca 400124",
            {"strada": "Bd. 21 Decembrie 1989", "numar": "104", "apartament": "7B",
             "localitate": "Cluj-Napoca", "judet": "Cluj", "cod_postal": "400124"},
        ),
        (
            "Calea Moșilor 211, sector 2, București",
            {"strada": "Calea Moșilor", "numar": "211", "sector": "2",
             "localitate": "București", "judet": "București"},
        ),
        (
            "Str. Horea 8, com. Florești, județul Cluj",
            {"strada": "Horea", "numar": "8", "localitate": "Florești", "judet": "Cluj"},
        ),
        (
            "Aleea Azuga 3 bl. A1 ap. 4, Timișoara",
            {"strada": "Aleea Azuga", "numar": "3", "bloc": "A1", "apartament": "4",
             "localitate": "Timișoara", "judet": "Timiș"},
        ),
        # Street names that start like a label are still street names.
        (
            "Str. Aprodului 3, Iași",
            {"strada": "Aprodului", "numar": "3", "localitate": "Iași", "judet": "Iași"},
        ),
        (
            "Str. Blajului 10, Dej",  # not a county seat: no county guessed
            {"strada": "Blajului", "numar": "10", "localitate": "Dej"},
        ),
    ],
)
def test_parses_common_formats(text: str, expected: dict[str, str]) -> None:
    assert parse_ro_address(text) == expected


@pytest.mark.parametrize("text", [None, "", "   "])
def test_empty(text: str | None) -> None:
    assert parse_ro_address(text) == {}


def test_nothing_is_guessed_from_free_text() -> None:
    assert parse_ro_address("lângă gară") == {}
    assert parse_ro_address("Cluj-Napoca") == {"localitate": "Cluj-Napoca", "judet": "Cluj"}
    assert parse_ro_address("sat Luna de Sus") == {"localitate": "Luna de Sus"}
    assert "numar" not in parse_ro_address("Str. Fără Număr, Cluj-Napoca")


# ---- profile integration --------------------------------------------------

from app.citizens import ADDRESS_PARTS_KEY, profile_attributes  # noqa: E402
from app.procedure_state import autofill_candidates  # noqa: E402
from app.procedures import get_registry  # noqa: E402

MARIA = {
    "cnp": "2851014123456", "nume": "Ionescu", "prenume": "Maria",
    "email": "maria@example.com", "phone": "+40712345678",
    "attributes": {"current_address": "Str. Avram Iancu 5, Cluj-Napoca", "apartament": "3"},
}


def test_profile_exposes_address_parts_and_aliases() -> None:
    attrs = profile_attributes(MARIA)
    assert (attrs["strada"], attrs["numar"], attrs["localitate"], attrs["judet"]) == (
        "Avram Iancu", "5", "Cluj-Napoca", "Cluj",
    )
    assert attrs["strada_domiciliu"] == "Avram Iancu" and attrs["nr_domiciliu"] == "5"
    assert attrs["adresa_domiciliu"] == "Str. Avram Iancu 5, Cluj-Napoca"
    assert ADDRESS_PARTS_KEY not in attrs


def test_explicit_attributes_win_over_parsed_ones() -> None:
    row = {**MARIA, "attributes": {**MARIA["attributes"], "strada": "Avram Iancu (corectat)"}}
    assert profile_attributes(row)["strada"] == "Avram Iancu (corectat)"


def test_stale_stored_parts_are_ignored_after_an_address_change() -> None:
    attrs = {
        "current_address": "Str. Nouă 9, Timișoara",
        ADDRESS_PARTS_KEY: {"from": "Str. Veche 1, Cluj-Napoca", "parts": {"strada": "Veche"}},
    }
    out = profile_attributes({**MARIA, "attributes": attrs})
    assert (out["strada"], out["judet"]) == ("Nouă", "Timiș")


def test_autofill_now_fills_the_address_of_an_id_card_request() -> None:
    proc = get_registry()["preschimbare-ci"]
    filled = autofill_candidates(proc, {}, profile_attributes(MARIA))
    for field, value in {"strada": "Avram Iancu", "numar": "5", "localitate": "Cluj-Napoca",
                         "judet": "Cluj", "apartament": "3", "cnp": "2851014123456"}.items():
        assert filled.get(field) == value, field
