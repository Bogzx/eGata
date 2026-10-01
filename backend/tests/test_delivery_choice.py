"""Reading the citizen's delivery choice from their own words.

complete_document only delivers what the citizen's message names
(app/delivery.py), so a misread here either blocks a real choice or, worse,
delivers one the citizen did not make. When in doubt the answer is None and
the choice is asked again.
"""
from __future__ import annotations

import pytest

from app.delivery import DELIVERY_OPTIONS, delivery_from_text


@pytest.mark.parametrize(
    ("text", "delivery"),
    [
        # The four buttons, as clicked.
        ("Salvare PDF", "save"),
        ("Confirmare pe SMS", "send"),
        ("Tipărire", "print"),
        ("Descarcă PDF", "download"),
        # Typed, in the words people use.
        ("salvează-l", "save"),
        ("salveaza", "save"),
        ("imprimă-l", "print"),
        ("Imprimare", "print"),
        ("printează", "print"),
        ("tipărește-l te rog", "print"),
        ("descarcă-l", "download"),
        ("trimite-mi pe SMS", "send"),
        ("trimite-mi-l", "send"),
        ("save", "save"),
        ("download", "download"),
        ("print it", "print"),
        # The review pane's buttons (frontend ReviewPane.requestDelivery).
        ("Te rog generează PDF-ul și finalizează documentul cu Salvează.", "save"),
        ("Te rog generează PDF-ul și finalizează documentul cu Trimite-mi pe SMS.", "send"),
        ("Te rog generează PDF-ul și finalizează documentul cu Printează.", "print"),
    ],
)
def test_reads_a_single_choice(text: str, delivery: str) -> None:
    assert delivery_from_text(text) == delivery


@pytest.mark.parametrize(
    ("text", "delivery"),
    [
        ("nu salva, tipărește", "print"),
        ("nu salva. tipărește-l", "print"),
        ("fără SMS, doar salvează", "save"),
        ("fără SMS doar salvează", "save"),
        ("nu SMS, ci descarcă", "download"),
        ("nu, salvează-l", "save"),  # "nu" answers something else; the clause ends
        ("no sms, just save", "save"),
    ],
)
def test_a_negated_choice_does_not_count(text: str, delivery: str) -> None:
    assert delivery_from_text(text) == delivery


@pytest.mark.parametrize(
    "text",
    [
        "",
        "da",
        "nu știu",
        "nu vreau pe SMS",  # only a refusal
        "fără tipărire",
        # A question is not a choice.
        "ce trebuie să trimit?",
        "pot să-l salvez?",
        # "trimit" ("I send") is about filing it, not about an SMS.
        "îl trimit eu la ghișeu",
        # Two choices at once: ask again rather than pick one.
        "salvează și tipărește",
        "descarcă sau trimite-mi pe SMS",
    ],
)
def test_no_single_choice_is_none(text: str) -> None:
    assert delivery_from_text(text) is None


def test_every_offered_option_reads_as_its_own_delivery() -> None:
    read = [delivery_from_text(option) for option in DELIVERY_OPTIONS]
    assert read == ["save", "send", "print", "download"]
