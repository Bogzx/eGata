"""find_redirect — recognize out-of-primărie scope and route the citizen."""
from __future__ import annotations

from pydantic import BaseModel

from app.tools import ToolContext, register

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

# Lowercase keyword → target. Order: more specific first.
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


class RedirectInfo(BaseModel):
    target: str | None
    name: str | None = None
    url: str | None = None
    phone: str | None = None
    scope: str | None = None
    explanation: str | None = None


@register("find_redirect")
async def find_redirect(
    ctx: ToolContext, query: str, target: str | None = None
) -> RedirectInfo:
    """Decide if a query is out of primărie scope and where to send the citizen."""
    if target and target in REDIRECT_TARGETS:
        info = REDIRECT_TARGETS[target]
        return RedirectInfo(
            target=target,
            **info,
            explanation=f"{info['scope']} Această cerere se face la {info['name']}.",
        )

    q = (query or "").lower()
    for kw, tgt in _KEYWORDS:
        if kw in q:
            info = REDIRECT_TARGETS[tgt]
            return RedirectInfo(
                target=tgt,
                **info,
                explanation=f"{info['scope']} Această cerere se face la {info['name']}.",
            )
    return RedirectInfo(target=None)
