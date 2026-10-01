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

# Words that name each delivery, matched as prefixes of diacritic-folded
# words: "salvează"/"Salvare"/"save", "descarcă"/"download", "tipărește"/
# "printează"/"imprimă-l"/"Imprimare", "SMS". "trimite" counts only as the
# imperative ("trimite-mi"): "trimit" ("I send") is how citizens talk about
# filing the form themselves ("ce trebuie să trimit?").
_DELIVERY_PREFIXES: dict[str, tuple[str, ...]] = {
    "download": ("descarc", "download"),
    "save": ("salv", "save"),
    "send": ("sms",),
    "print": ("tipar", "print", "imprim"),
}
_SEND_IMPERATIVES = frozenset({"trimite", "trimiteti"})
# "nu salva", "fără SMS", "nu vreau pe SMS": a negation covers the rest of
# its clause. A clause ends at punctuation or at a word that turns the
# sentence ("nu SMS, ci salvează", "fără SMS doar salvează").
_NEGATIONS = frozenset({"nu", "fara", "no", "not", "without"})
_CLAUSE_TURNS = frozenset({"ci", "dar", "doar", "insa", "but", "just", "only"})


def fold(text: str) -> str:
    """Lowercase, strip diacritics and punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9: ]+", " ", text)).strip()


def _delivery_of(word: str) -> str | None:
    if word in _SEND_IMPERATIVES:
        return "send"
    for delivery, prefixes in _DELIVERY_PREFIXES.items():
        if word.startswith(prefixes):
            return delivery
    return None


def delivery_from_text(text: str) -> str | None:
    """The one delivery a citizen's message asks for, or None.

    None, so the choice is asked again, when the message is a question,
    names no delivery, or names more than one it does not negate:
    "nu salva, tipărește" is print, "salvează și tipărește" is None.
    """
    if "?" in (text or ""):
        return None
    named: set[str] = set()
    for clause in re.split(r"[,.;:!\n]", text or ""):
        negated = False
        for word in fold(clause).split():
            if word in _CLAUSE_TURNS:
                negated = False
            elif word in _NEGATIONS:
                negated = True
            elif not negated and (delivery := _delivery_of(word)) is not None:
                named.add(delivery)
    return named.pop() if len(named) == 1 else None
