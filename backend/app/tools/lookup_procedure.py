"""lookup_procedure — kind-agnostic RAG search; returns procedure matches + optional scenario plan."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.embeddings import embed_text, search_top_k_rag
from app.models import (
    ResolvedActeNecesareItem,
    ScenarioPlan,
)
from app.procedures import get_registry
from app.scenarios import build_scenario_plan, resolve_act
from app.tools import ToolContext, register

SCENARIO_THRESHOLD = 0.55


class ProcedureMatch(BaseModel):
    procedure_id: str
    title: str
    score: float
    description: str | None = None
    acte_necesare: list[ResolvedActeNecesareItem] = Field(default_factory=list)


class LookupResult(BaseModel):
    matches: list[ProcedureMatch] = Field(default_factory=list)
    scenario_plan: ScenarioPlan | None = None


@register("lookup_procedure")
async def lookup_procedure(ctx: ToolContext, query: str) -> LookupResult:
    """Find the best primărie unit (procedure or scenario) for a free-text Romanian query.

    Top-1 wins: scenario_plan is populated only when the highest-scoring hit is a
    scenario above SCENARIO_THRESHOLD. Procedure matches are always populated from
    procedure rows in top-K so the agent has fallback options.
    """
    query = (query or "").strip()
    if not query:
        raise ValueError("query cannot be empty")

    embedding = embed_text(query)
    raw = search_top_k_rag(embedding, k=5)

    scenario_plan: ScenarioPlan | None = None
    if raw and raw[0]["score"] >= SCENARIO_THRESHOLD and raw[0]["kind"] == "scenario":
        scenario_plan = build_scenario_plan(raw[0]["id"])

    reg = get_registry()
    matches: list[ProcedureMatch] = []
    for row in raw:
        if row["kind"] != "procedure":
            continue
        proc = reg.get(row["id"])
        if proc is None:
            continue
        matches.append(
            ProcedureMatch(
                procedure_id=row["id"],
                title=proc.title,
                score=float(row["score"]),
                description=proc.description,
                acte_necesare=[resolve_act(a) for a in proc.acte_necesare],
            )
        )
        if len(matches) >= 3:
            break

    return LookupResult(matches=matches, scenario_plan=scenario_plan)
