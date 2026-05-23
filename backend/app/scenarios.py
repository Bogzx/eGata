"""Scenarios catalog + plan builder + GET /scenarios/{id}.

A scenario links several existing procedures (in-scope) and external institution
steps (CivicAI cannot complete) into a coherent multi-step plan for a real-life
situation like "buying an apartment".
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.institutions import get_institutions_registry
from app.models import (
    ResolvedActeNecesareItem,
    ResolvedExternalStep,
    ResolvedInScopeStep,
    Scenario,
    ScenarioPlan,
)


class ScenarioSummary(BaseModel):
    id: str
    title: str
    description: str
    complexitate: str | None = None
    applies_if: str | None = None

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@lru_cache(maxsize=1)
def get_scenarios_registry() -> dict[str, Scenario]:
    out: dict[str, Scenario] = {}
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        sc = Scenario.model_validate(data)
        if sc.id != path.stem:
            raise ValueError(f"Scenario id {sc.id!r} does not match filename {path.stem!r}")
        out[sc.id] = sc
    if not out:
        raise RuntimeError(f"No scenarios found in {SCENARIOS_DIR}")
    return out


def resolve_act(act) -> ResolvedActeNecesareItem:
    """Enrich an ActNecesar with institution name + ai-cannot-complete note when applicable."""
    institutie_nume: str | None = None
    note_ai: str | None = None
    if act.emitent_id:
        inst = get_institutions_registry().get(act.emitent_id)
        if inst is not None:
            institutie_nume = inst.nume_complet
            note_ai = inst.note_ai_cannot_complete
    return ResolvedActeNecesareItem(
        denumire=act.denumire,
        emitent=act.emitent,
        emitent_id=act.emitent_id,
        institutie_nume=institutie_nume,
        note_ai_cannot_complete=note_ai,
        format=act.format,
        observatie=act.observatie,
        obligatoriu=act.obligatoriu,
        alternative=list(act.alternative),
    )


def build_scenario_plan(scenario_id: str) -> ScenarioPlan | None:
    from app.procedures import get_registry as get_procedures_registry

    sc = get_scenarios_registry().get(scenario_id)
    if sc is None:
        return None

    procs = get_procedures_registry()
    insts = get_institutions_registry()

    resolved_in_scope: list[ResolvedInScopeStep] = []
    for step in sc.in_scope_steps:
        proc = procs.get(step.procedure_id)
        if proc is None:
            continue
        resolved_in_scope.append(
            ResolvedInScopeStep(
                ordine=step.ordine,
                procedure_id=step.procedure_id,
                procedure_title=proc.title,
                deadline_days=step.deadline_days,
                note=step.note,
                acte_necesare=[resolve_act(a) for a in proc.acte_necesare],
            )
        )

    resolved_external: list[ResolvedExternalStep] = []
    for step in sc.external_steps:
        inst = insts.get(step.institutie_id)
        if inst is None:
            continue
        resolved_external.append(
            ResolvedExternalStep(
                institutie_id=inst.id,
                institutie_nume=inst.nume_complet,
                scope=inst.scope,
                url=inst.url,
                phone=inst.phone,
                obligatoriu=step.obligatoriu,
                note=step.note,
                note_ai_cannot_complete=inst.note_ai_cannot_complete,
            )
        )

    return ScenarioPlan(
        scenario_id=sc.id,
        title=sc.title,
        summary=sc.description,
        complexitate=sc.complexitate,
        termen_total=sc.termen_total,
        in_scope_steps=resolved_in_scope,
        external_steps=resolved_external,
    )


@router.get("", response_model=list[ScenarioSummary])
def list_scenarios() -> list[ScenarioSummary]:
    return [
        ScenarioSummary(
            id=sc.id,
            title=sc.title,
            description=sc.description,
            complexitate=sc.complexitate,
            applies_if=sc.applies_if,
        )
        for sc in get_scenarios_registry().values()
    ]


@router.get("/{scenario_id}", response_model=ScenarioPlan)
def get_scenario_plan_endpoint(scenario_id: str) -> ScenarioPlan:
    plan = build_scenario_plan(scenario_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id!r} not found")
    return plan
