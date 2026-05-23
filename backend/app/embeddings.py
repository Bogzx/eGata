"""Gemini embedding pipeline for procedure RAG."""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

from google.genai import types as genai_types

from app.db import get_pg_connection
from app.models import Procedure

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768


# Module-level alias kept for monkeypatching in tests — tests still set
# `embeddings._gemini_client = mock_client` to override the real one.
_gemini_client: Any = None


def _client() -> Any:
    """Process-wide cached genai client. Tests can override by assigning
    `_gemini_client` directly; otherwise we defer to app/gemini.py."""
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    from app.gemini import get_genai_client
    return get_genai_client()


def embed_text(text: str) -> list[float]:
    """Embed `text` with Gemini. Cached per (normalized text) so the agent
    re-calling lookup_procedure with the same query in a single session
    doesn't burn a fresh API call."""
    return list(_embed_text_cached(text.strip()))


@lru_cache(maxsize=256)
def _embed_text_cached(text: str) -> tuple[float, ...]:
    """Tuple-typed for hashability so it can sit behind lru_cache."""
    client = _client()
    resp = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=genai_types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    return tuple(resp.embeddings[0].values)


def procedure_source_text(proc: Procedure) -> str:
    parts = [
        proc.title,
        proc.description,
        " ".join(proc.synonyms),
        " ".join(proc.sample_queries),
    ]
    return "\n".join(p for p in parts if p)


def scenario_source_text(sc) -> str:
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
) -> None:
    if len(embedding) != EMBEDDING_DIM:
        raise ValueError(f"Embedding must be {EMBEDDING_DIM}-dim, got {len(embedding)}")
    if kind not in {"procedure", "scenario"}:
        raise ValueError(f"Invalid kind {kind!r}; must be 'procedure' or 'scenario'")
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in embedding) + "]"
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into rag_entries (id, kind, embedding, source_text) "
            "values (%s, %s, %s::vector, %s) "
            "on conflict (id) do update set "
            "kind = excluded.kind, embedding = excluded.embedding, "
            "source_text = excluded.source_text, updated_at = now();",
            (entry_id, kind, vec_literal, source_text),
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
            "from rag_entries "
            "order by embedding <=> %s::vector asc limit %s;",
            (vec_literal, vec_literal, k),
        )
        return [dict(r) for r in cur.fetchall()]


def search_top_k(query_embedding: list[float], k: int = 3) -> list[dict[str, Any]]:
    """Back-compat wrapper for code paths that only want procedure matches."""
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in query_embedding) + "]"
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id as procedure_id, 1 - (embedding <=> %s::vector) as score "
            "from rag_entries where kind = 'procedure' "
            "order by embedding <=> %s::vector asc limit %s;",
            (vec_literal, vec_literal, k),
        )
        return [dict(r) for r in cur.fetchall()]
