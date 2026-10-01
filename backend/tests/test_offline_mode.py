"""Offline mode without a database: backend selection, the local embedder's
retrieval quality on the real catalogue, and the agent's text parsing.

The full conversation against real SQL is in test_offline_agent_postgres.py.
"""
from __future__ import annotations

import pytest

from app import local_embeddings
from app.config import Settings, resolved_agent_backend, resolved_embeddings_backend
from app.embeddings import cosine_similarity, procedure_source_text, scenario_source_text
from app.offline_agent import _is_greeting, _is_no, _is_yes
from app.procedures import get_registry
from app.scenarios import get_scenarios_registry


def _settings(**kw: object) -> Settings:
    base = {"supabase_db_url": "postgresql://x", "jwt_signing_secret": "x", "azure_openai_api_key": ""}
    return Settings(**{**base, **kw})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kw", "agent", "emb"),
    [
        ({}, "offline", "local"),
        ({"azure_openai_api_key": "k"}, "azure", "azure"),
        ({"azure_openai_api_key": "k", "agent_backend": "offline"}, "offline", "azure"),
        ({"embeddings_backend": "local", "azure_openai_api_key": "k"}, "azure", "local"),
    ],
)
def test_backend_resolution(kw: dict, agent: str, emb: str) -> None:
    s = _settings(**kw)
    assert resolved_agent_backend(s) == agent
    assert resolved_embeddings_backend(s) == emb


def test_unknown_backend_fails_loudly() -> None:
    with pytest.raises(RuntimeError):
        resolved_agent_backend(_settings(agent_backend="gpt"))


def test_local_embedding_is_deterministic_and_normalized() -> None:
    a = local_embeddings.embed("Schimbare domiciliu — Cluj-Napoca")
    assert a == local_embeddings.embed("Schimbare domiciliu — Cluj-Napoca")
    assert len(a) == local_embeddings.DIM == 768
    assert abs(sum(x * x for x in a) - 1.0) < 1e-9
    assert all(x == 0 for x in local_embeddings.embed("bună ziua"))  # stopwords only


# Phrasings a citizen would type, and the entry that should rank first.
QUERIES = {
    "vreau să-mi schimb domiciliul": "schimbare-domiciliu",
    "m-am mutat la o adresă nouă": "schimbare-domiciliu",
    "am pierdut buletinul": "preschimbare-ci",
    "mi-a expirat cartea de identitate": "preschimbare-ci",
    "vreau să tai un copac din curte": "taiere-arbore-curte-privata",
    "am nevoie de certificat fiscal": "certificat-fiscal",
    "vreau să cumpăr un apartament": "sc-cumparare-apartament",
    "vând apartamentul": "sc-vanzare-apartament",
    "loc de parcare pe stradă": "abonament-parcare-strada",
    "am o clădire nouă de declarat": "declarare-cladire",
    "bunica împlinește 100 de ani": "premiu-100-ani",
    "am văzut ambrozie pe un teren": "sesizare-ambrozia",
    "vreau să construiesc o casă": "sc-autorizatie-construire",
    "plăcuță cu numărul casei": "placuta-numar-postal",
    "card de parcare pentru persoane cu handicap": "card-parcare-dizabilitati",
    "tichete de masă pentru pensionari": "tichete-alimente",
    "ce datorii am la primărie": "situatie-debite",
}


def _index() -> list[tuple[str, list[float]]]:
    out = [(p.id, local_embeddings.embed(procedure_source_text(p))) for p in get_registry().values()]
    out += [
        (s.id, local_embeddings.embed(scenario_source_text(s)))
        for s in get_scenarios_registry().values()
    ]
    return out


def test_local_retrieval_finds_the_right_procedure() -> None:
    index = _index()
    misses = []
    for query, expected in QUERIES.items():
        q = local_embeddings.embed(query)
        best = max(index, key=lambda e: cosine_similarity(q, e[1]))[0]
        if best != expected:
            misses.append((query, best))
    assert not misses, misses


def test_off_topic_requests_stay_under_the_match_threshold() -> None:
    from app.agent_tools.lookup_procedure import MATCH_THRESHOLD

    index = _index()
    for query in ["bună ziua", "vreau medic de familie", "cât e ceasul"]:
        q = local_embeddings.embed(query)
        assert max(cosine_similarity(q, v) for _, v in index) < MATCH_THRESHOLD, query


@pytest.mark.parametrize("text", ["Da", "da, sigur", "OK", "confirm", "Începe"])
def test_yes(text: str) -> None:
    assert _is_yes(text)


@pytest.mark.parametrize("text", ["Nu", "nu e bine", "Str. Lungă 3", "da și nu"])
def test_not_yes(text: str) -> None:
    assert not _is_yes(text)


def test_no_and_greeting() -> None:
    assert _is_no("Nu") and _is_no("nu, altceva")
    assert _is_greeting("Bună ziua!") and _is_greeting("")
    assert not _is_greeting("bună, vreau certificat fiscal")
