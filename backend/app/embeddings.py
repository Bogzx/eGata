"""Embedding pipeline for procedure RAG.

Two embedders, one 768-d vector space shape:

- azure: the Azure OpenAI embedding deployment, reduced to 768d via the
  `dimensions` parameter.
- local: app.local_embeddings — deterministic, offline, lexical. Used when
  there is no Azure key, so the procedure search works from a bare
  `docker compose up`.

Vectors from different models are not comparable, so every row records the
model that built it (migrations/012) and search only looks at rows from the
current one. Re-run `scripts.index_rag` whenever the Azure deployment changes.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

from openai import AzureOpenAI

from app import local_embeddings
from app.config import get_settings, resolved_embeddings_backend
from app.db import get_pg_connection
from app.models import Procedure, Scenario

EMBEDDING_DIM = 768


@lru_cache(maxsize=1)
def _client() -> AzureOpenAI:
    s = get_settings()
    if not s.azure_openai_api_key:
        raise RuntimeError(
            "AZURE_OPENAI_API_KEY not set — embeddings require it."
        )
    return AzureOpenAI(
        api_key=s.azure_openai_api_key,
        azure_endpoint=s.azure_openai_endpoint,
        api_version=s.azure_openai_api_version,
    )


def embedding_model_id() -> str:
    """The tag stored with (and searched by) every vector — see migrations/012."""
    if resolved_embeddings_backend() == "local":
        return local_embeddings.MODEL_ID
    return "azure"


def embed_text(text: str) -> list[float]:
    if resolved_embeddings_backend() == "local":
        return local_embeddings.embed(text)
    s = get_settings()
    resp = _client().embeddings.create(
        model=s.azure_openai_embed_deployment,
        input=text,
        dimensions=EMBEDDING_DIM,
    )
    return list(resp.data[0].embedding)


def procedure_source_text(proc: Procedure) -> str:
    parts = [
        proc.title,
        proc.description,
        " ".join(proc.synonyms),
        " ".join(proc.sample_queries),
    ]
    return "\n".join(p for p in parts if p)


def scenario_source_text(sc: Scenario) -> str:
    """Authored summary + synonyms + sample queries — never chunked."""
    parts = [sc.summary_for_rag, " ".join(sc.synonyms), " ".join(sc.sample_queries)]
    return "\n".join(p for p in parts if p)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def upsert_rag_entry(
    *,
    entry_id: str,
    kind: str,
    source_text: str,
    embedding: list[float],
    model: str | None = None,
) -> None:
    if len(embedding) != EMBEDDING_DIM:
        raise ValueError(f"Embedding must be {EMBEDDING_DIM}-dim, got {len(embedding)}")
    if kind not in {"procedure", "scenario"}:
        raise ValueError(f"Invalid kind {kind!r}; must be 'procedure' or 'scenario'")
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in embedding) + "]"
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into rag_entries (id, kind, embedding, source_text, embedding_model) "
            "values (%s, %s, %s::vector, %s, %s) "
            "on conflict (id, embedding_model) do update set "
            "kind = excluded.kind, embedding = excluded.embedding, "
            "source_text = excluded.source_text, updated_at = now();",
            (entry_id, kind, vec_literal, source_text, model or embedding_model_id()),
        )
        conn.commit()


def upsert_procedure_embedding(procedure_id: str, source_text: str, embedding: list[float]) -> None:
    """Back-compat shim — existing callers use this name + signature."""
    upsert_rag_entry(
        entry_id=procedure_id, kind="procedure", source_text=source_text, embedding=embedding
    )


def search_top_k_rag(query_embedding: list[float], k: int = 5) -> list[dict[str, Any]]:
    """Top-K across rag_entries regardless of kind. Each row: {id, kind, score}."""
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in query_embedding) + "]"
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, kind, 1 - (embedding <=> %s::vector) as score "
            "from rag_entries where embedding_model = %s "
            "order by embedding <=> %s::vector asc limit %s;",
            (vec_literal, embedding_model_id(), vec_literal, k),
        )
        return [dict(r) for r in cur.fetchall()]


def search_top_k(query_embedding: list[float], k: int = 3) -> list[dict[str, Any]]:
    """Back-compat wrapper for code paths that only want procedure matches."""
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in query_embedding) + "]"
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id as procedure_id, 1 - (embedding <=> %s::vector) as score "
            "from rag_entries where kind = 'procedure' and embedding_model = %s "
            "order by embedding <=> %s::vector asc limit %s;",
            (vec_literal, embedding_model_id(), vec_literal, k),
        )
        return [dict(r) for r in cur.fetchall()]
