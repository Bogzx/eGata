"""Scenarios catalog + plan resolution + endpoint."""
from fastapi.testclient import TestClient

from app.scenarios import build_scenario_plan, get_scenarios_registry

EXPECTED_SCENARIO_IDS = {
    "sc-cumparare-apartament",
    "sc-vanzare-apartament",
    "sc-certificat-fiscal",
    "sc-autorizatie-construire",
    "sc-persoana-dizabilitati",
}


def test_registry_loads_all_scenarios():
    reg = get_scenarios_registry()
    assert set(reg.keys()) == EXPECTED_SCENARIO_IDS


def test_scenario_in_scope_procedure_ids_all_resolve():
    """Every in_scope_steps[].procedure_id must exist in the procedure registry."""
    from app.procedures import get_registry as get_procedures
    procs = get_procedures()
    unresolved: list[str] = []
    for sc in get_scenarios_registry().values():
        for step in sc.in_scope_steps:
            if step.procedure_id not in procs:
                unresolved.append(f"{sc.id}::{step.procedure_id}")
    assert unresolved == []


def test_scenario_institutie_ids_all_resolve():
    """Every external_steps[].institutie_id must exist in the institutions registry."""
    from app.institutions import get_institutions_registry
    insts = get_institutions_registry()
    unresolved: list[str] = []
    for sc in get_scenarios_registry().values():
        for step in sc.external_steps:
            if step.institutie_id not in insts:
                unresolved.append(f"{sc.id}::{step.institutie_id}")
    assert unresolved == []


def test_build_scenario_plan_resolves_all_refs():
    plan = build_scenario_plan("sc-cumparare-apartament")
    assert plan is not None
    assert plan.scenario_id == "sc-cumparare-apartament"
    assert plan.title == "Cumpărare apartament"
    assert len(plan.in_scope_steps) == 3
    for step in plan.in_scope_steps:
        assert step.procedure_title, f"missing procedure_title for {step.procedure_id}"
    titles = {s.institutie_nume for s in plan.external_steps}
    assert "Notariat public (oricare birou notarial)" in titles
    assert "Oficiul de Cadastru și Publicitate Imobiliară (ANCPI)" in titles


def test_build_scenario_plan_returns_none_for_unknown():
    assert build_scenario_plan("sc-does-not-exist") is None


def test_scenario_with_no_external_steps():
    plan = build_scenario_plan("sc-certificat-fiscal")
    assert plan is not None
    assert plan.external_steps == []
    assert len(plan.in_scope_steps) == 1


def test_endpoint_returns_plan():
    from app.main import app
    client = TestClient(app)
    res = client.get("/scenarios/sc-cumparare-apartament")
    assert res.status_code == 200
    body = res.json()
    assert body["scenario_id"] == "sc-cumparare-apartament"
    assert len(body["in_scope_steps"]) == 3


def test_endpoint_404_unknown():
    from app.main import app
    client = TestClient(app)
    res = client.get("/scenarios/sc-does-not-exist")
    assert res.status_code == 404
