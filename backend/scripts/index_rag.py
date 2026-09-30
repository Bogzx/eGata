"""Re-index all procedures + scenarios into rag_entries.

Idempotent. Safe to run after every JSON change.

    python -m scripts.index_rag            # the embedder the app will use
    python -m scripts.index_rag --local    # the offline embedder, no API key

With an Azure key configured (AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT +
AZURE_OPENAI_EMBED_DEPLOYMENT) the default is the Azure deployment (~28
embedding calls). Without one it is app/local_embeddings.py, which
`scripts.bootstrap_local_db` also runs on every start, so a fresh
`docker compose up` already has a searchable index.
"""
from __future__ import annotations

import argparse
import logging
from collections.abc import Iterator
from typing import Any

from app import local_embeddings
from app.embeddings import procedure_source_text, scenario_source_text
from app.procedures import get_registry as get_procedures_registry
from app.scenarios import get_scenarios_registry

log = logging.getLogger("index_rag")


def iter_entries() -> Iterator[tuple[str, str, str]]:
    """(id, kind, source_text) for everything the agent can look up."""
    for proc in get_procedures_registry().values():
        yield proc.id, "procedure", procedure_source_text(proc)
    for sc in get_scenarios_registry().values():
        yield sc.id, "scenario", scenario_source_text(sc)


def index_local(conn: Any) -> int:
    """Build the offline index over an open psycopg connection.

    Takes the connection rather than reading app settings so the migrate step
    can run it without JWT_SIGNING_SECRET and friends.
    """
    n = 0
    with conn.cursor() as cur:
        for entry_id, kind, text in iter_entries():
            vec = "[" + ",".join(f"{x:.7f}" for x in local_embeddings.embed(text)) + "]"
            cur.execute(
                "insert into rag_entries (id, kind, embedding, source_text, embedding_model) "
                "values (%s, %s, %s::vector, %s, %s) "
                "on conflict (id, embedding_model) do update set "
                "kind = excluded.kind, embedding = excluded.embedding, "
                "source_text = excluded.source_text, updated_at = now();",
                (entry_id, kind, vec, text, local_embeddings.MODEL_ID),
            )
            n += 1
    return n


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Re-index procedures + scenarios for RAG.")
    ap.add_argument("--local", action="store_true", help="use the offline embedder")
    args = ap.parse_args(argv)

    if args.local:
        from app.db import get_pg_connection

        with get_pg_connection() as conn:
            n = index_local(conn)
            conn.commit()
        log.info("Done. %d entries indexed with %s.", n, local_embeddings.MODEL_ID)
        return

    from app.embeddings import embed_text, embedding_model_id, upsert_rag_entry

    model = embedding_model_id()
    n = 0
    for entry_id, kind, text in iter_entries():
        upsert_rag_entry(
            entry_id=entry_id, kind=kind, source_text=text, embedding=embed_text(text), model=model
        )
        log.info("  %s %s", kind, entry_id)
        n += 1
    log.info("Done. %d entries indexed with %s.", n, model)


if __name__ == "__main__":
    main()
