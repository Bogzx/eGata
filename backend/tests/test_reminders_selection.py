"""KEY tests for the reminders selection logic (pure, no DB).

Covers `_select_applicable_steps` — the core decision the background worker
uses to decide which next_steps spawn reminders for a given citizen.
"""
from app.reminders import _select_applicable_steps, _step_identity


PROCEDURE_STEPS = [
    {
        "kind": "in_scope_procedure",
        "procedure_id": "preschimbare-ci",
        "deadline_days": 15,
        "title": "Preschimbare carte de identitate",
    },
    {
        "kind": "external_redirect",
        "redirect_target": "DRPCIV",
        "deadline_days": 30,
        "title": "Actualizare certificat înmatriculare auto",
        "applies_if": "owns_vehicle == true",
    },
    {
        "kind": "external_redirect",
        "redirect_target": "CNAS",
        "title": "Actualizare medic de familie",
    },
    {
        "kind": "external_redirect",
        "redirect_target": "ANAF",
        "title": "Notificare schimbare domiciliu fiscal",
    },
]


def test_no_applies_if_always_selected():
    steps = _select_applicable_steps(PROCEDURE_STEPS, {})
    titles = [s["title"] for s in steps]
    assert "Preschimbare carte de identitate" in titles
    assert "Actualizare medic de familie" in titles
    assert "Notificare schimbare domiciliu fiscal" in titles


def test_applies_if_true_includes_step():
    steps = _select_applicable_steps(PROCEDURE_STEPS, {"owns_vehicle": True})
    titles = [s["title"] for s in steps]
    assert "Actualizare certificat înmatriculare auto" in titles


def test_applies_if_false_excludes_step():
    steps = _select_applicable_steps(PROCEDURE_STEPS, {"owns_vehicle": False})
    titles = [s["title"] for s in steps]
    assert "Actualizare certificat înmatriculare auto" not in titles


def test_missing_attribute_excludes_conditional_step():
    steps = _select_applicable_steps(PROCEDURE_STEPS, {})
    titles = [s["title"] for s in steps]
    assert "Actualizare certificat înmatriculare auto" not in titles


def test_unconditional_steps_count():
    steps = _select_applicable_steps(PROCEDURE_STEPS, {})
    assert len(steps) == 3


def test_step_identity_uses_procedure_id_then_redirect_target():
    in_scope = {"kind": "in_scope_procedure", "procedure_id": "x", "title": "t"}
    external = {"kind": "external_redirect", "redirect_target": "ANAF", "title": "t"}
    assert _step_identity(in_scope) == ("in_scope_procedure", "x")
    assert _step_identity(external) == ("external_redirect", "ANAF")
