from __future__ import annotations

import pytest

from app.embeddings import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    cosine_similarity,
    procedure_source_text,
)
from app.models import Procedure, ProcedureField


def _make_proc() -> Procedure:
    return Procedure(
        id="x",
        title="Schimbare domiciliu",
        description="Înscrierea mențiunii de stabilire a domiciliului.",
        scope="primarie",
        category="evidenta-persoanelor",
        synonyms=["mutare", "schimbat adresa"],
        sample_queries=["vreau să-mi schimb domiciliul", "m-am mutat"],
        fields=[ProcedureField(name="a", label="A", source="ask", required=True)],
        template="x.tex",
        next_steps=[],
    )


def test_embedding_model_constants() -> None:
    assert EMBEDDING_MODEL == "text-embedding-004"
    assert EMBEDDING_DIM == 768


def test_procedure_source_text_includes_all_signals() -> None:
    src = procedure_source_text(_make_proc())
    assert "Schimbare domiciliu" in src
    assert "Înscrierea mențiunii" in src
    assert "mutare" in src
    assert "vreau să-mi schimb domiciliul" in src


def test_cosine_similarity() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 1.0], [1.0, 0.0]) == pytest.approx(0.7071, abs=1e-3)


def test_registry_loads_seven_procedures() -> None:
    from app.procedures import get_registry
    reg = get_registry()
    assert set(reg.keys()) == {
        "schimbare-domiciliu", "adeverinta-venit", "certificat-fiscal",
        "certificat-nastere-copie", "inregistrare-casatorie", "ajutor-social",
        "preschimbare-ci",
    }


def test_registry_validates_against_pydantic_model() -> None:
    from app.procedures import get_registry
    reg = get_registry()
    p = reg["schimbare-domiciliu"]
    assert p.id == "schimbare-domiciliu"
    assert p.scope == "primarie"
    assert any(f.name == "adresa_noua" for f in p.fields)
