"""Unit tests for app.procedure_state — applies_if field gating + validation."""
from __future__ import annotations

import pytest

from app.models import Procedure, ProcedureField
from app.procedure_state import (
    FieldValidationError,
    all_required_satisfied,
    compute_profile_prefill,
    evaluate_field_states,
    find_field,
    validate_field_value,
)


def _proc(fields: list[ProcedureField]) -> Procedure:
    return Procedure(
        id="test",
        title="Test",
        description="d",
        scope="primarie",
        category="x",
        synonyms=[],
        sample_queries=[],
        acte_necesare=[],
        fields=fields,
        template="x.tex",
        next_steps=[],
    )


def _field(
    name: str,
    *,
    required: bool = True,
    options: list[str] | None = None,
    applies_if: str | None = None,
) -> ProcedureField:
    return ProcedureField(
        name=name,
        label=name.replace("_", " ").title(),
        source="ask",
        required=required,
        options=options,
        applies_if=applies_if,
    )


def test_all_fields_required_and_empty_is_all_missing():
    proc = _proc([_field("nume"), _field("cnp")])
    states = evaluate_field_states(proc, doc_fields={}, citizen_attrs={})
    assert states.missing == ["nume", "cnp"]
    assert states.satisfied == []


def test_satisfied_when_value_present():
    proc = _proc([_field("nume")])
    states = evaluate_field_states(
        proc, doc_fields={"nume": "Maria Ionescu"}, citizen_attrs={}
    )
    assert states.satisfied == ["nume"]
    assert states.missing == []


def test_empty_string_is_not_satisfied():
    proc = _proc([_field("nume")])
    states = evaluate_field_states(proc, doc_fields={"nume": "   "}, citizen_attrs={})
    assert states.satisfied == []
    assert states.missing == ["nume"]


def test_applies_if_gates_required():
    """A field with applies_if = 'tip_proprietate == "găzduit"' is only
    required when tip_proprietate is 'găzduit'."""
    proc = _proc([
        _field("tip_proprietate", options=["proprietar", "chiriaș", "găzduit"]),
        _field("anexa_2_signer", applies_if='tip_proprietate == "găzduit"'),
    ])
    # not gazduit → anexa_2_signer NOT required
    states = evaluate_field_states(
        proc, doc_fields={"tip_proprietate": "proprietar"}, citizen_attrs={}
    )
    assert "anexa_2_signer" not in states.required
    assert "anexa_2_signer" not in states.applicable

    # gazduit → anexa_2_signer IS required
    states = evaluate_field_states(
        proc, doc_fields={"tip_proprietate": "găzduit"}, citizen_attrs={}
    )
    assert "anexa_2_signer" in states.required
    assert "anexa_2_signer" in states.missing


def test_applies_if_from_citizen_attributes():
    proc = _proc([
        _field("vehicle_plate", applies_if="owns_vehicle == true"),
    ])
    states = evaluate_field_states(
        proc, doc_fields={}, citizen_attrs={"owns_vehicle": True}
    )
    assert "vehicle_plate" in states.missing

    states = evaluate_field_states(
        proc, doc_fields={}, citizen_attrs={"owns_vehicle": False}
    )
    assert "vehicle_plate" not in states.required


def test_field_dropped_when_applies_if_flips_false():
    """A previously-set value becomes 'dropped' (lingers but is ignored)."""
    proc = _proc([
        _field("tip_proprietate", options=["proprietar", "găzduit"]),
        _field("anexa_2_signer", applies_if='tip_proprietate == "găzduit"'),
    ])
    # set anexa_2_signer while gazduit, then change tip_proprietate
    states = evaluate_field_states(
        proc,
        doc_fields={"tip_proprietate": "proprietar", "anexa_2_signer": "Mama"},
        citizen_attrs={},
    )
    assert "anexa_2_signer" in states.dropped
    assert "anexa_2_signer" not in states.required


def test_doc_field_shadows_citizen_attr():
    """Document fields override citizen attributes in the merged context."""
    proc = _proc([
        _field("explicit", applies_if='status == "owner"'),
    ])
    # citizen says status=tenant but doc says status=owner — doc wins
    states = evaluate_field_states(
        proc,
        doc_fields={"status": "owner"},
        citizen_attrs={"status": "tenant"},
    )
    assert "explicit" in states.applicable


def test_all_required_satisfied_true_when_no_missing():
    proc = _proc([_field("nume")])
    assert all_required_satisfied(proc, {"nume": "X"}, {})


def test_all_required_satisfied_false_when_missing():
    proc = _proc([_field("nume"), _field("cnp")])
    assert not all_required_satisfied(proc, {"nume": "X"}, {})


def test_all_required_satisfied_ignores_inapplicable():
    """An applies_if-gated required field shouldn't block completion when inapplicable."""
    proc = _proc([
        _field("tip_proprietate", options=["proprietar", "găzduit"]),
        _field("anexa_2_signer", applies_if='tip_proprietate == "găzduit"'),
    ])
    assert all_required_satisfied(
        proc, {"tip_proprietate": "proprietar"}, {}
    )
    assert not all_required_satisfied(
        proc, {"tip_proprietate": "găzduit"}, {}
    )


def test_validate_field_value_unknown_field_raises():
    proc = _proc([_field("nume")])
    with pytest.raises(FieldValidationError):
        validate_field_value(proc, "necunoscut", "x")


def test_validate_field_value_options_enforced():
    proc = _proc([_field("tip", options=["a", "b"])])
    validate_field_value(proc, "tip", "a")  # ok
    with pytest.raises(FieldValidationError):
        validate_field_value(proc, "tip", "c")


def test_validate_field_value_free_string_passes():
    proc = _proc([_field("nume", options=None)])
    validate_field_value(proc, "nume", "anything goes")


def test_find_field_returns_none_on_miss():
    proc = _proc([_field("nume")])
    assert find_field(proc, "nume") is not None
    assert find_field(proc, "missing") is None


def _profile_field(name: str, source: str = "profile") -> ProcedureField:
    return ProcedureField(
        name=name,
        label=name.title(),
        source=source,
        required=True,
    )


def test_compute_profile_prefill_pulls_profile_values():
    proc = _proc(
        [
            _profile_field("cnp"),
            _profile_field("nume_complet", source="id_scan|profile"),
            _field("scop"),  # source="ask" → ignored
        ]
    )
    citizen_attrs = {
        "cnp": "2851014123456",
        "nume_complet": "Maria Ionescu",
        "scop": "should be ignored — not profile-sourced",
        "owns_vehicle": True,
    }
    out = compute_profile_prefill(proc, citizen_attrs)
    assert out == {"cnp": "2851014123456", "nume_complet": "Maria Ionescu"}


def test_compute_profile_prefill_skips_missing_attrs():
    proc = _proc([_profile_field("cnp"), _profile_field("email")])
    out = compute_profile_prefill(proc, {"cnp": "123"})
    assert out == {"cnp": "123"}


def test_compute_profile_prefill_skips_empty_string_attrs():
    proc = _proc([_profile_field("cnp"), _profile_field("email")])
    out = compute_profile_prefill(proc, {"cnp": "123", "email": "   "})
    assert out == {"cnp": "123"}


def test_compute_profile_prefill_ignores_non_profile_sources():
    proc = _proc(
        [
            _profile_field("cnp"),
            _field("scop"),  # source="ask"
            ProcedureField(name="other", label="Other", source="id_scan", required=False),
        ]
    )
    citizen_attrs = {"cnp": "X", "scop": "Y", "other": "Z"}
    out = compute_profile_prefill(proc, citizen_attrs)
    assert out == {"cnp": "X"}
