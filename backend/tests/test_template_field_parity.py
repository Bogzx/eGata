"""Every procedure's field schema must match its LaTeX template's placeholders.

This is the test that would have caught the `schimbare-domiciliu` blocker:
the procedure pointed at `preschimbare-ci.tex`, so all four substantive
fields the citizen typed were silently dropped (pdf.py substitutes "" for
unknown placeholders) while ten unrelated placeholders rendered blank.

Two directions matter and both are asserted:

  * field without placeholder  -> what the citizen typed never reaches the PDF
  * placeholder without field  -> the PDF renders a blank where data belongs

`KNOWN_COSMETIC_GAPS` holds the three pre-existing one-field gaps that are
cosmetic (the value is collected for routing/eligibility, not printed).
Anything else is a bug. Do not grow this list without a written reason.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROCEDURES_DIR = BACKEND_DIR / "procedures"
TEMPLATES_DIR = BACKEND_DIR / "templates"

# Must stay in sync with app.pdf._PLACEHOLDER_RE.
PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# procedure_id -> field names collected but deliberately not printed.
KNOWN_COSMETIC_GAPS: dict[str, set[str]] = {
    # Address is already printed via the itemised strada/numar/... fields.
    "abonament-parcare-strada": {"adresa_domiciliu"},
    # Email is used for the delivery notification, not shown on the form.
    "preschimbare-ci": {"email"},
    # Eligibility category drives `applies_if`, the printed form has a
    # pre-printed tick list instead.
    "tichete-alimente": {"categoria_eligibilitate"},
}

PROCEDURE_FILES = sorted(PROCEDURES_DIR.glob("*.json"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_procedure_files_are_discovered() -> None:
    """Guard against the glob silently matching nothing."""
    assert len(PROCEDURE_FILES) >= 23, f"only found {len(PROCEDURE_FILES)} procedures"


@pytest.mark.parametrize("proc_path", PROCEDURE_FILES, ids=lambda p: p.stem)
def test_template_placeholders_match_field_schema(proc_path: Path) -> None:
    proc = _load(proc_path)
    procedure_id = proc["id"]
    template_name = proc["template"]

    template_path = TEMPLATES_DIR / template_name
    assert template_path.exists(), (
        f"{procedure_id}: template {template_name!r} does not exist in templates/"
    )

    fields = {f["name"] for f in proc.get("fields", [])}
    placeholders = set(PLACEHOLDER_RE.findall(template_path.read_text(encoding="utf-8")))
    allowed_gaps = KNOWN_COSMETIC_GAPS.get(procedure_id, set())

    fields_without_placeholder = fields - placeholders - allowed_gaps
    placeholders_without_field = placeholders - fields

    assert not fields_without_placeholder, (
        f"{procedure_id} -> {template_name}: the citizen fills "
        f"{sorted(fields_without_placeholder)} but the template never prints them "
        f"(pdf.py drops them silently)"
    )
    assert not placeholders_without_field, (
        f"{procedure_id} -> {template_name}: template expects "
        f"{sorted(placeholders_without_field)} which the schema never collects "
        f"(pdf.py substitutes an empty string, leaving a blank on the form)"
    )


@pytest.mark.parametrize("proc_path", PROCEDURE_FILES, ids=lambda p: p.stem)
def test_each_procedure_uses_its_own_template(proc_path: Path) -> None:
    """A procedure pointing at another procedure's template is the exact
    class of bug that produced the wrong-document blocker. Templates are
    named after their procedure, so require the two to agree."""
    proc = _load(proc_path)
    assert proc["template"] == f"{proc['id']}.tex", (
        f"{proc['id']} renders {proc['template']} — a template belonging to a "
        f"different procedure. Expected {proc['id']}.tex"
    )


def test_no_orphan_templates() -> None:
    """Every .tex in templates/ is referenced by some procedure (base.tex aside)."""
    referenced = {_load(p)["template"] for p in PROCEDURE_FILES}
    on_disk = {p.name for p in TEMPLATES_DIR.glob("*.tex")} - {"base.tex"}
    orphans = on_disk - referenced
    assert not orphans, f"templates referenced by no procedure: {sorted(orphans)}"


KNOWN_COSMETIC_GAP_IDS = set(KNOWN_COSMETIC_GAPS)


def test_allowlist_has_no_stale_entries() -> None:
    """If a gap gets fixed, the allowlist entry must be removed too."""
    ids = {_load(p)["id"] for p in PROCEDURE_FILES}
    stale = KNOWN_COSMETIC_GAP_IDS - ids
    assert not stale, f"allowlist references non-existent procedures: {sorted(stale)}"
