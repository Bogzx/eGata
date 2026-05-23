"""lookup_procedure — RAG over procedures + scenarios.

Valid states: EXPLORING, CONFIRMING_MATCH, DELIVERED (for scenario
continuation), REDIRECTED (user pivoted back). After a successful match,
the dispatcher transitions the session to CONFIRMING_MATCH so the agent
can ask "Do you want to proceed with X?" before opening a doc.
"""
from __future__ import annotations

from app.agent_tools import Tool, ToolContext, ToolResult, register
from app.embeddings import embed_text, search_top_k_rag
from app.procedures import get_registry
from app.scenarios import build_scenario_plan, resolve_act
from app.sessions import Session, SessionState

SCENARIO_THRESHOLD = 0.55
MATCH_THRESHOLD = 0.45  # below this, no confidence — stay EXPLORING


async def execute(session: Session, ctx: ToolContext, query: str) -> ToolResult:
    query = (query or "").strip()
    if not query:
        return ToolResult(error="Întrebarea nu poate fi goală.")

    embedding = embed_text(query)
    raw = search_top_k_rag(embedding, k=5)

    scenario_plan = None
    if raw and raw[0]["score"] >= SCENARIO_THRESHOLD and raw[0]["kind"] == "scenario":
        scenario_plan = build_scenario_plan(raw[0]["id"])

    reg = get_registry()
    matches = []
    for row in raw:
        if row["kind"] != "procedure":
            continue
        proc = reg.get(row["id"])
        if proc is None:
            continue
        matches.append(
            {
                "procedure_id": row["id"],
                "title": proc.title,
                "score": float(row["score"]),
                "description": proc.description,
                "acte_necesare": [
                    resolve_act(a).model_dump(mode="json") for a in proc.acte_necesare
                ],
            }
        )
        if len(matches) >= 3:
            break

    top_score = matches[0]["score"] if matches else 0.0
    transition_to = None
    if top_score >= MATCH_THRESHOLD or scenario_plan is not None:
        transition_to = SessionState.CONFIRMING_MATCH

    return ToolResult(
        output={
            "matches": matches,
            "scenario_plan": scenario_plan.model_dump(mode="json")
            if scenario_plan
            else None,
        },
        transition_to=transition_to,
    )


register(
    Tool(
        name="lookup_procedure",
        description=(
            "Caută procedura primăriei sau planul scenariu pentru o cerere "
            "în limba română. Folosește acest tool când cetățeanul descrie "
            "o nevoie generală."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {"query": {"type": "STRING"}},
            "required": ["query"],
        },
        valid_states={
            SessionState.EXPLORING,
            SessionState.CONFIRMING_MATCH,
            SessionState.DELIVERED,
            SessionState.REDIRECTED,
        },
        execute=execute,
    )
)
