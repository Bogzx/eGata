"""Gemini embedding pipeline for procedure RAG."""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

from google import genai
from google.genai import types as genai_types

from app.config import get_settings
from app.db import get_pg_connection
from app.models import Procedure

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768


@lru_cache(maxsize=1)
def _get_client() -> Any:
    return genai.Client(api_key=get_settings().gemini_api_key)


# Module-level alias kept for monkeypatching in tests
_gemini_client: Any = None


def _client() -> Any:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = _get_client()
    return _gemini_client


def embed_text(text: str) -> list[float]:
    client = _client()
    resp = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=genai_types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    return list(resp.embeddings[0].values)


def procedure_source_text(proc: Procedure) -> str:
    parts = [
        proc.title,
        proc.description,
        " ".join(proc.synonyms),
        " ".join(proc.sample_queries),
    ]
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


def upsert_procedure_embedding(procedure_id: str, source_text: str, embedding: list[float]) -> None:
    if len(embedding) != EMBEDDING_DIM:
        raise ValueError(f"Embedding must be {EMBEDDING_DIM}-dim, got {len(embedding)}")
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in embedding) + "]"
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into procedures_embeddings (procedure_id, embedding, source_text) "
            "values (%s, %s::vector, %s) "
            "on conflict (procedure_id) do update set "
            "embedding = excluded.embedding, source_text = excluded.source_text, updated_at = now();",
            (procedure_id, vec_literal, source_text),
        )
        conn.commit()


def search_top_k(query_embedding: list[float], k: int = 3) -> list[dict[str, Any]]:
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in query_embedding) + "]"
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select procedure_id, 1 - (embedding <=> %s::vector) as score "
            "from procedures_embeddings "
            "order by embedding <=> %s::vector asc limit %s;",
            (vec_literal, vec_literal, k),
        )
        return [dict(r) for r in cur.fetchall()]
