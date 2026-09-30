"""Institutions catalog loads, all expected IDs present."""
from app.institutions import get_institutions_registry

EXPECTED_IDS = {
    "notariat",
    "ocpi-ancpi",
    "auditor-energetic",
    "drpciv",
    "anaf",
    "cnas",
    "spclep-mai",
    "ajofm",
    "casa-pensii",
    "instanta",
    "diriginte-santier",
    "dgaspc",
    "onrc",
    "anevar",
    "banca",
    "spital-medic",
    "stare-civila",
}


def test_registry_loads_all_institutions() -> None:
    reg = get_institutions_registry()
    assert set(reg.keys()) == EXPECTED_IDS


def test_each_institution_has_required_fields() -> None:
    reg = get_institutions_registry()
    for inst_id, inst in reg.items():
        assert inst.id == inst_id, f"{inst_id} id mismatch"
        assert inst.nume_scurt, f"{inst_id} missing nume_scurt"
        assert inst.nume_complet, f"{inst_id} missing nume_complet"
        assert inst.scope, f"{inst_id} missing scope"


def test_procedure_emitent_ids_all_resolve() -> None:
    """Every emitent_id in any procedure JSON must exist in the registry."""
    from app.procedures import get_registry as get_procedure_registry
    reg = get_institutions_registry()
    procs = get_procedure_registry()
    unresolved: list[str] = []
    for proc in procs.values():
        for act in proc.acte_necesare:
            if act.emitent_id and act.emitent_id not in reg:
                unresolved.append(f"{proc.id}::{act.emitent_id}")
    assert unresolved == [], f"Unresolved emitent_id references: {unresolved}"
