"""Procedure registry loader + RAG lookup endpoint."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from app.embeddings import embed_text, search_top_k
from app.models import (
    Procedure,
    ProcedureLookupRequest,
    ProcedureLookupResponse,
    ProcedureMatch,
    ResolvedProcedure,
)
from app.security import current_citizen_id

PROCEDURES_DIR = Path(__file__).resolve().parent.parent / "procedures"
REDIRECT_THRESHOLD = 0.55

REDIRECT_HINTS: dict[str, list[str]] = {
    "ANAF": ["anaf", "taxe", "fisc", "impozit pe venit", "declarație fiscală"],
    "CNAS": ["cnas", "medic de familie", "card de sănătate", "asigurare sănătate"],
    "DRPCIV": ["drpciv", "înmatricul", "permis", "auto", "talon", "mașin"],
}

router = APIRouter(prefix="/procedures", tags=["procedures"])


@lru_cache(maxsize=1)
def get_registry() -> dict[str, Procedure]:
    out: dict[str, Procedure] = {}
    for path in sorted(PROCEDURES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        proc = Procedure.model_validate(data)
        if proc.id != path.stem:
            raise ValueError(f"Procedure id {proc.id!r} does not match filename {path.stem!r}")
        out[proc.id] = proc
    if not out:
        raise RuntimeError(f"No procedures found in {PROCEDURES_DIR}")
    return out


def guess_redirect_target(query: str) -> str | None:
    q = query.lower()
    for target, keywords in REDIRECT_HINTS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}", q):
                return target
    return None


@router.get("", response_model=list[Procedure])
def list_procedures() -> list[Procedure]:
    return list(get_registry().values())


@router.get("/{procedure_id}", response_model=ResolvedProcedure)
def get_procedure(procedure_id: str) -> ResolvedProcedure:
    from app.scenarios import resolve_act  # lazy: avoid cyclic imports at module load

    reg = get_registry()
    proc = reg.get(procedure_id)
    if proc is None:
        raise HTTPException(status_code=404, detail=f"Procedure '{procedure_id}' not found")

    return ResolvedProcedure(
        id=proc.id,
        title=proc.title,
        description=proc.description,
        scope=proc.scope,
        category=proc.category,
        synonyms=list(proc.synonyms),
        sample_queries=list(proc.sample_queries),
        acte_necesare=[resolve_act(a) for a in proc.acte_necesare],
        fields=list(proc.fields),
        template=proc.template,
        next_steps=list(proc.next_steps),
    )


@router.get("/{procedure_id}/preview-pdf")
def preview_pdf(
    procedure_id: str,
    citizen_id: UUID = Depends(current_citizen_id),
) -> Response:
    """Render the procedure's LaTeX template populated with the citizen's
    profile (and `default_from` chains) so the user can see exactly what
    PDF they would get at the end of the conversation. Used by
    the "Vezi documentul" preview popup in MatchesPane.
    """
    from app.citizens import fetch_citizen_by_id
    from app.pdf import render_and_compile

    proc = get_registry().get(procedure_id)
    if proc is None:
        raise HTTPException(status_code=404, detail=f"Procedure '{procedure_id}' not found")

    citizen = fetch_citizen_by_id(citizen_id)
    attrs = citizen.get("attributes") or {}

    # Build a sample fields dict the same way auto-fill does at chat time:
    # direct profile match → default_from chain → suggest_default → blank.
    sample: dict[str, str] = {}
    for fld in proc.fields:
        value = attrs.get(fld.name)
        if not value and fld.default_from:
            value = attrs.get(fld.default_from) or sample.get(fld.default_from)
        if not value and fld.suggest_default:
            value = fld.suggest_default
        sample[fld.name] = str(value) if value is not None else ""

    pdf_bytes = render_and_compile(proc.template, sample)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{procedure_id}-preview.pdf"',
            # Carries the citizen's name, CNP and address — same rule as
            # /files/pdf: no shared or disk cache may keep it.
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/lookup", response_model=ProcedureLookupResponse)
def lookup(
    req: ProcedureLookupRequest,
    _citizen_id: UUID = Depends(current_citizen_id),
) -> ProcedureLookupResponse:
    reg = get_registry()
    embedding = embed_text(req.query)
    raw = search_top_k(embedding, k=3)

    matches: list[ProcedureMatch] = []
    for row in raw:
        pid = row["procedure_id"]
        proc = reg.get(pid)
        if proc is None:
            continue
        matches.append(
            ProcedureMatch(procedure_id=pid, title=proc.title, score=float(row["score"]))
        )

    top_score = matches[0].score if matches else 0.0
    redirect_candidate: str | None = None
    if top_score < REDIRECT_THRESHOLD:
        redirect_candidate = guess_redirect_target(req.query)

    return ProcedureLookupResponse(matches=matches, redirect_candidate=redirect_candidate)
