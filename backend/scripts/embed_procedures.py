"""Embed all procedures and upsert into pgvector. Run after Supabase is migrated."""
from __future__ import annotations

import sys

from app.embeddings import embed_text, procedure_source_text, upsert_procedure_embedding
from app.procedures import get_registry


def main() -> int:
    reg = get_registry()
    for pid, proc in reg.items():
        src = procedure_source_text(proc)
        print(f"Embedding {pid}...")
        emb = embed_text(src)
        upsert_procedure_embedding(pid, src, emb)
    print(f"Done. Upserted {len(reg)} procedures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
