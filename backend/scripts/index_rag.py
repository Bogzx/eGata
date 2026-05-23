"""Re-index all procedures + scenarios into rag_entries.

Idempotent. Safe to run after every JSON change. Requires Supabase DB env vars
plus AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT + an embedding deployment
(set via AZURE_OPENAI_EMBED_DEPLOYMENT, default text-embedding-3-small).
"""
from __future__ import annotations

import logging

from app.embeddings import (
    embed_text,
    procedure_source_text,
    scenario_source_text,
    upsert_rag_entry,
)
from app.institutions import get_institutions_registry
from app.procedures import get_registry as get_procedures_registry
from app.scenarios import get_scenarios_registry

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("index_rag")


def main() -> None:
    insts = get_institutions_registry()
    log.info("Institutions loaded: %d", len(insts))

    procs = get_procedures_registry()
    log.info("Procedures loaded: %d — indexing...", len(procs))
    for proc in procs.values():
        text = procedure_source_text(proc)
        embedding = embed_text(text)
        upsert_rag_entry(entry_id=proc.id, kind="procedure", source_text=text, embedding=embedding)
        log.info("  procedure %s", proc.id)

    scs = get_scenarios_registry()
    log.info("Scenarios loaded: %d — indexing...", len(scs))
    for sc in scs.values():
        text = scenario_source_text(sc)
        embedding = embed_text(text)
        upsert_rag_entry(entry_id=sc.id, kind="scenario", source_text=text, embedding=embedding)
        log.info("  scenario %s", sc.id)

    log.info("Done. Total entries indexed: %d", len(procs) + len(scs))


if __name__ == "__main__":
    main()
