"""find_redirect — detect out-of-primărie scope, transition to REDIRECTED.

Valid only when the citizen is NOT actively filling a document — mid-fill
mentions ("vreau și impozit cândva") shouldn't blow away the half-filled
doc. To exit a fill, the user has to explicitly abandon. Transition to
REDIRECTED is requested only when a target is found.
"""
from __future__ import annotations

from app.agent_tools import Tool, ToolContext, ToolResult, register
from app.sessions import Session, SessionState

REDIRECT_TARGETS: dict[str, dict[str, str]] = {
    "ANAF": {
        "name": "ANAF — Agenția Națională de Administrare Fiscală",
        "url": "https://www.anaf.ro",
        "phone": "031 403 9160",
        "scope": "Impozite, taxe, fiscalitate, domiciliu fiscal.",
    },
    "CNAS": {
        "name": "CNAS — Casa Națională de Asigurări de Sănătate",
        "url": "https://cnas.ro",
        "phone": "0800 800 950",
        "scope": "Medic de familie, asigurare medicală, card de sănătate.",
    },
    "DRPCIV": {
        "name": "DRPCIV — Direcția Regim Permise de Conducere și Înmatriculare a Vehiculelor",
        "url": "https://drpciv.ro",
        "phone": "021 9665",
        "scope": "Talon auto, permis de conducere, înmatriculare.",
    },
}

_KEYWORDS: list[tuple[str, str]] = [
    ("medic de familie", "CNAS"),
    ("medicul de familie", "CNAS"),
    ("card de sănătate", "CNAS"),
    ("asigurare medical", "CNAS"),
    ("cnas", "CNAS"),
    ("talon", "DRPCIV"),
    ("permis de conducere", "DRPCIV"),
    ("înmatricul", "DRPCIV"),
    ("inmatricul", "DRPCIV"),
    ("mașin", "DRPCIV"),
    ("masin", "DRPCIV"),
    ("drpciv", "DRPCIV"),
    ("impozit", "ANAF"),
    ("taxă", "ANAF"),
    ("taxa", "ANAF"),
    ("fiscal", "ANAF"),
    ("anaf", "ANAF"),
    ("declaraț", "ANAF"),
]


async def execute(
    session: Session,
    ctx: ToolContext,
    query: str,
    target: str | None = None,
) -> ToolResult:
    info = None
    chosen_target = None
    if target and target in REDIRECT_TARGETS:
        chosen_target = target
        info = REDIRECT_TARGETS[target]
    else:
        q = (query or "").lower()
        for kw, tgt in _KEYWORDS:
            if kw in q:
                chosen_target = tgt
                info = REDIRECT_TARGETS[tgt]
                break

    if info is None or chosen_target is None:
        return ToolResult(output={"target": None})

    return ToolResult(
        output={
            "target": chosen_target,
            **info,
            "explanation": f"{info['scope']} Această cerere se face la {info['name']}.",
        },
        transition_to=SessionState.REDIRECTED,
        frontend_event={
            "type": "redirect",
            "target": chosen_target,
            "name": info["name"],
            "url": info["url"],
        },
    )


register(
    Tool(
        name="find_redirect",
        description=(
            "Decide dacă cererea cetățeanului este în afara primăriei "
            "(ANAF, CNAS, DRPCIV) și unde să fie redirecționată."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING"},
                "target": {"type": "STRING"},
            },
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
