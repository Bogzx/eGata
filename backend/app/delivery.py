"""How the citizen gets their completed form, and reading that from their words.

eGata files nothing with the primărie: every choice here is about the
citizen's own copy ("send" texts them the reference). The offline agent asks
with these exact labels, and `complete_document` only delivers what the
citizen's own message names (see its docstring), so both read choices the
same way, through `delivery_from_text`.

Standalone on purpose: agent tools and the offline agent both import it.
"""
from __future__ import annotations

import re
import unicodedata

DELIVERY_QUESTION = "Cum vrei să primești cererea completată?"
DELIVERY_OPTIONS = ["Salvare PDF", "Confirmare pe SMS", "Tipărire", "Descarcă PDF"]

# First match wins: "Descarcă PDF" is a download, not a save.
_DELIVERY_BY_KEYWORD = [
    ("descarc", "download"),
    ("salv", "save"),
    ("trimit", "send"),
    ("sms", "send"),
    ("tipar", "print"),
    ("print", "print"),
]


def fold(text: str) -> str:
    """Lowercase, strip diacritics and punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9: ]+", " ", text)).strip()


def delivery_from_text(text: str) -> str | None:
    """The delivery a citizen's message asks for, or None if it names none."""
    folded = fold(text)
    for keyword, delivery in _DELIVERY_BY_KEYWORD:
        if keyword in folded:
            return delivery
    return None
