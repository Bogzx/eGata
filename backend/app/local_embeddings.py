"""Deterministic, offline text embeddings for procedure retrieval.

Used when no Azure OpenAI key is configured (EMBEDDINGS_BACKEND=local, or
`auto` with no key), so `docker compose up` gives a working procedure search
with no paid API. This is lexical matching, not semantics: a hashed bag of
diacritic-folded words, 5-letter stems and character trigrams, projected
into the same 768 dimensions as the Azure vectors so the pgvector column and
cosine search are unchanged.

It handles the phrasing citizens actually use for these 23 procedures
("vreau să-mi schimb domiciliul", "am pierdut buletinul", "tai un copac din
curte") because the procedure JSONs carry synonyms and sample queries. It
will not map a paraphrase with no word in common to the right form — that is
what the Azure embeddings are for.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata

DIM = 768
MODEL_ID = "local-ngram-v1"

# Words that occur in almost every request and carry no signal about which
# procedure is meant.
_STOPWORDS = frozenset(
    """
    a ai al ale am ar as au avea buna ca care ce cel cea cei cele cum cu da
    de dar despre din doresc este eu fi fie iar il imi in insa intr intre
    la le lui ma mai mea meu mi mie mult ne nu o pe pentru prin sa sau se si
    sunt ta tau te un una unei unui va vreau vrea vrem zi ziua noi voi
    """.split()
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _features(text: str) -> list[tuple[str, float]]:
    feats: list[tuple[str, float]] = []
    for word in _WORD_RE.findall(_fold(text)):
        if len(word) < 2 or word in _STOPWORDS:
            continue
        feats.append(("w:" + word, 1.0))
        if len(word) > 5:
            # Crude stemming: Romanian inflects at the end
            # (domiciliu/domiciliul/domiciliului share "domic").
            feats.append(("s:" + word[:5], 1.0))
        padded = f" {word} "
        feats.extend(("t:" + padded[i : i + 3], 0.35) for i in range(len(padded) - 2))
    return feats


def _slot(feature: str) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    n = int.from_bytes(digest, "big")
    return n % DIM, (1.0 if (n >> 63) & 1 else -1.0)


def embed(text: str) -> list[float]:
    vec = [0.0] * DIM
    for feature, weight in _features(text):
        idx, sign = _slot(feature)
        vec[idx] += sign * weight
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]
