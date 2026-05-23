"""list_procedures — catalog browse tool.

`lookup_procedure` is for "I need X, find me the right procedure" — it
takes a query and does semantic RAG. But citizens often ask the open
question "what can you help me with?", which RAG can't answer (the
top-3 matches aren't representative of the catalog).

This tool returns the catalog. Two modes:
  - no args              → all categories, summary view ({category, label,
                           count, procedures}). Agent presents the category
                           names only, not all 26 procedures.
  - `category="<slug>"`  → drill-in. Returns only procedures in that
                           category. The agent enumerates them all (it's
                           bounded — categories have ≤8 items today).

Category matching is tolerant: exact slug (`urbanism-constructii`),
case-insensitive label substring (`Urbanism`, `urbanism`, `construcții`),
or a category slug substring. If the arg doesn't match any category, the
tool returns the same shape as the no-arg call so the agent can recover.

Valid in the same discovery states as lookup_procedure:
EXPLORING, CONFIRMING_MATCH, DELIVERED (scenario continuation), REDIRECTED.
"""
from __future__ import annotations

from app.agent_tools import Tool, ToolContext, ToolResult, register
from app.procedures import get_registry
from app.sessions import Session, SessionState

# Romanian-friendly labels for the bare category slugs used in
# backend/procedures/*.json. Keep in sync as new categories appear.
_CATEGORY_LABELS: dict[str, str] = {
    "asistenta-sociala": "Asistență socială",
    "dizabilitati": "Dizabilități",
    "ecologie-spatii-verzi": "Ecologie și spații verzi",
    "evidenta-persoanelor": "Evidența persoanelor",
    "fiscalitate-locala": "Fiscalitate locală",
    "parcare": "Parcare",
    "premii-evenimente": "Premii și evenimente",
    "siguranta-circulatiei": "Siguranța circulației",
    "stare-civila": "Stare civilă",
    "urbanism-constructii": "Urbanism și construcții",
}


def _category_label(slug: str) -> str:
    return _CATEGORY_LABELS.get(slug, slug.replace("-", " ").capitalize())


def _normalize(s: str) -> str:
    return s.strip().lower().replace("ă", "a").replace("â", "a").replace(
        "î", "i"
    ).replace("ș", "s").replace("ț", "t")


def _resolve_category(arg: str, available_slugs: list[str]) -> str | None:
    """Map a user/agent-supplied category to a real slug or None."""
    if arg in available_slugs:
        return arg
    n = _normalize(arg)
    # Try matching the (normalized) label
    for slug in available_slugs:
        if _normalize(_category_label(slug)) == n:
            return slug
    # Substring match on label
    for slug in available_slugs:
        if n in _normalize(_category_label(slug)):
            return slug
    # Substring match on the slug itself
    for slug in available_slugs:
        if n in _normalize(slug):
            return slug
    return None


async def execute(
    session: Session,  # noqa: ARG001
    ctx: ToolContext,  # noqa: ARG001
    category: str | None = None,
) -> ToolResult:
    reg = get_registry()
    by_cat: dict[str, list[dict[str, str]]] = {}
    for proc in reg.values():
        by_cat.setdefault(proc.category, []).append(
            {
                "procedure_id": proc.id,
                "title": proc.title,
                "description": proc.description,
            }
        )

    all_slugs = sorted(by_cat.keys(), key=lambda s: _category_label(s))

    # Drill-in: one category requested
    if category:
        slug = _resolve_category(category, all_slugs)
        if slug is None:
            return ToolResult(
                output={
                    "category_requested": category,
                    "matched": None,
                    "available_categories": [
                        {"category": s, "label": _category_label(s)}
                        for s in all_slugs
                    ],
                    "note": (
                        f"Nu am găsit categoria '{category}'. Spune-i cetățeanului "
                        "ce categorii sunt disponibile."
                    ),
                },
            )
        items = sorted(by_cat[slug], key=lambda p: p["title"])
        return ToolResult(
            output={
                "category": slug,
                "label": _category_label(slug),
                "procedures": items,
                "count": len(items),
            },
        )

    # Overview: all categories, summary view
    categories = [
        {
            "category": slug,
            "label": _category_label(slug),
            "count": len(by_cat[slug]),
            "procedures": sorted(by_cat[slug], key=lambda p: p["title"]),
        }
        for slug in all_slugs
    ]
    return ToolResult(
        output={
            "total": sum(c["count"] for c in categories),
            "categories": categories,
        },
    )


register(
    Tool(
        name="list_procedures",
        description=(
            "Returnează catalogul primăriei. Fără argument: lista categoriilor "
            "(folosește când cetățeanul întreabă deschis 'cu ce mă poți "
            "ajuta?'). Cu argument `category` (ex: 'urbanism-constructii', "
            "'fiscalitate-locala'): toate procedurile din acea categorie "
            "(folosește când cetățeanul cere o categorie anume: 'spune-mi "
            "despre urbanism', 'ce ține de fiscalitate')."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "Slug categorie (ex: 'urbanism-constructii'). Lasă gol "
                        "pentru overview pe categorii."
                    ),
                },
            },
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
