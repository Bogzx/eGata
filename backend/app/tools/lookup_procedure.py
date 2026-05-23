"""lookup_procedure — RAG search over the procedure registry."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.embeddings import embed_text, search_top_k
from app.procedures import REDIRECT_THRESHOLD, get_registry, guess_redirect_target
from app.tools import ToolContext, register


class ActeNecesareItem(BaseModel):
    denumire: str
    emitent: str | None = None
    emitent_id: str | None = None
    obligatoriu: bool = True
    observatie: str | None = None


class ProcedureMatch(BaseModel):
    procedure_id: str
    title: str
    score: float
    description: str | None = None
    acte_necesare: list[ActeNecesareItem] = Field(default_factory=list)


class LookupResult(BaseModel):
    matches: list[ProcedureMatch] = Field(default_factory=list)
    redirect_candidate: str | None = None


@register("lookup_procedure")
async def lookup_procedure(ctx: ToolContext, query: str) -> LookupResult:
    """Find the best primărie procedure for a free-text Romanian query.

    Returns up to 3 matches ordered by similarity. When the top score is below
    the redirect threshold, ``redirect_candidate`` is set to ANAF/CNAS/DRPCIV
    based on keyword hints (or None).
    """
    query = (query or "").strip()
    if not query:
        raise ValueError("query cannot be empty")

    embedding = embed_text(query)
    raw = search_top_k(embedding, k=3)
    reg = get_registry()

    matches: list[ProcedureMatch] = []
    for row in raw:
        pid = row["procedure_id"]
        proc = reg.get(pid)
        if proc is None:
            continue
        matches.append(
            ProcedureMatch(
                procedure_id=pid,
                title=proc.title,
                score=float(row["score"]),
                description=proc.description,
                acte_necesare=[
                    ActeNecesareItem(
                        denumire=a.denumire,
                        emitent=a.emitent,
                        emitent_id=a.emitent_id,
                        obligatoriu=a.obligatoriu,
                        observatie=a.observatie,
                    )
                    for a in proc.acte_necesare
                ],
            )
        )

    top_score = matches[0].score if matches else 0.0
    redirect_candidate: str | None = None
    if top_score < REDIRECT_THRESHOLD:
        redirect_candidate = guess_redirect_target(query)

    return LookupResult(matches=matches, redirect_candidate=redirect_candidate)
