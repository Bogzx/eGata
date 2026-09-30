"""Field-state evaluation for procedures with first-class applies_if.

Given a `Procedure`, the citizen's attributes, and the document's current
fields, this module computes for each procedure field whether it is:

  - APPLICABLE  (applies_if is true or unset)
  - REQUIRED    (applicable AND `required: true`)
  - SATISFIED   (the document has a non-empty value)
  - MISSING     (REQUIRED AND NOT SATISFIED)
  - DROPPED     (was previously required, no longer applicable; value
                 still present but irrelevant)

It also provides `validate_field_value(procedure, name, value)` which the
agent's `set_field` tool calls before writing. Validation checks:
  - field exists in the procedure
  - if `options` is defined, value must be one of them (string match)

The merged context for applies_if is `{**citizen_attrs, **doc_fields}`.
Document fields shadow attributes when keys collide — useful for cases
like `tip_proprietate == 'găzduit'` triggering an `anexa_2_signer` field.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.applies_if import evaluate
from app.models import Procedure, ProcedureField


class FieldValidationError(ValueError):
    """Raised by validate_field_value when a value violates the schema."""


@dataclass
class FieldStates:
    """Snapshot of every field's status under the current context."""
    applicable: list[str] = field(default_factory=list)
    required: list[str] = field(default_factory=list)
    satisfied: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    # full per-field map for callers that need detail
    per_field: dict[str, PerFieldState] = field(default_factory=dict)


@dataclass
class PerFieldState:
    name: str
    applicable: bool
    required: bool
    satisfied: bool
    missing: bool
    dropped: bool
    value: Any


def _merged_context(
    citizen_attrs: Mapping[str, Any],
    doc_fields: Mapping[str, Any],
) -> dict[str, Any]:
    """Doc fields shadow citizen attrs when keys collide."""
    return {**citizen_attrs, **doc_fields}


def _is_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def evaluate_field_states(
    procedure: Procedure,
    doc_fields: Mapping[str, Any],
    citizen_attrs: Mapping[str, Any] | None = None,
) -> FieldStates:
    """Compute the applicable / required / satisfied state for every field."""
    ctx = _merged_context(citizen_attrs or {}, doc_fields)
    out = FieldStates()
    for fld in procedure.fields:
        applicable = evaluate(fld.applies_if, ctx)
        value = doc_fields.get(fld.name)
        satisfied = applicable and _is_nonempty(value)
        required = applicable and fld.required
        missing = required and not satisfied
        # Was set but no longer applies — value lingers, but UI/agent should
        # ignore it. (We never *delete* values to keep transitions clean.)
        dropped = (not applicable) and _is_nonempty(value)

        state = PerFieldState(
            name=fld.name,
            applicable=applicable,
            required=required,
            satisfied=satisfied,
            missing=missing,
            dropped=dropped,
            value=value,
        )
        out.per_field[fld.name] = state
        if applicable:
            out.applicable.append(fld.name)
        if required:
            out.required.append(fld.name)
        if satisfied:
            out.satisfied.append(fld.name)
        if missing:
            out.missing.append(fld.name)
        if dropped:
            out.dropped.append(fld.name)
    return out


def all_required_satisfied(
    procedure: Procedure,
    doc_fields: Mapping[str, Any],
    citizen_attrs: Mapping[str, Any] | None = None,
) -> bool:
    """True when every applicable+required field has a non-empty value."""
    return not evaluate_field_states(
        procedure, doc_fields, citizen_attrs
    ).missing


def find_field(procedure: Procedure, name: str) -> ProcedureField | None:
    for fld in procedure.fields:
        if fld.name == name:
            return fld
    return None


# Longest value a single form field may hold. The longest legitimate values
# (a free-text "scop" or an address) are a few hundred characters; this only
# stops a runaway model or client from writing megabytes into a form.
MAX_FIELD_LENGTH = 2000


def validate_field_value(procedure: Procedure, name: str, value: Any) -> None:
    """Raise FieldValidationError if the value violates the procedure schema."""
    fld = find_field(procedure, name)
    if fld is None:
        raise FieldValidationError(
            f"Câmp necunoscut '{name}' pentru procedura '{procedure.id}'."
        )
    if value is not None and not isinstance(value, (str, bool, int, float)):
        raise FieldValidationError(
            f"Valoare invalidă pentru '{name}': se acceptă doar text, număr sau da/nu."
        )
    if isinstance(value, str) and len(value) > MAX_FIELD_LENGTH:
        raise FieldValidationError(
            f"Valoarea pentru '{name}' depășește {MAX_FIELD_LENGTH} de caractere."
        )
    if fld.options is not None and isinstance(value, str) and value not in fld.options:
        raise FieldValidationError(
            f"Valoare invalidă pentru '{name}': "
            f"{value!r} nu este în {fld.options}."
        )


_TRUE_TOKENS = {"true", "adevărat", "adevarat", "da", "yes"}
_FALSE_TOKENS = {"false", "fals", "nu", "no"}


def coerce_field_value(procedure: Procedure, name: str, value: Any) -> Any:
    """Coerce a raw value (typically a STRING from the model's function-call
    schema) into the likely Python type expected by the field.

    Why: the model's function_declarations cap us at JSON-schema STRING for
    `value`, so booleans arrive as "true"/"da" and never compare equal to
    Python `True` in applies_if expressions like `owns_vehicle == true`.
    The model also paraphrases enum options ("Pierdere / furt" instead of
    canonical "pierdere"), so we normalize before the validator runs.

    Rules:
      - non-strings pass through (already typed)
      - "true"/"da"/"adevărat" → True; "false"/"nu"/"fals" → False
      - if the field has `options`, try to map the raw value back to the
        canonical option via case-insensitive + token-split match. Falls
        through unchanged if nothing matches — the validator will reject
        and the model can retry.
      - everything else stays a string (numeric coercion is intentionally
        out of scope — we don't know if "1234567" is an int field or a
        CNP/IBAN that must stay a string)
    """
    if not isinstance(value, str):
        return value
    fld = find_field(procedure, name)
    if fld is None:
        return value
    if fld.options is None:
        v = value.strip().lower()
        if v in _TRUE_TOKENS:
            return True
        if v in _FALSE_TOKENS:
            return False
        return value
    # Field has enum options — try to recover from model paraphrasing.
    raw = value.strip()
    if raw in fld.options:
        return raw
    lowered = raw.lower()
    by_lower = {opt.lower(): opt for opt in fld.options}
    if lowered in by_lower:
        return by_lower[lowered]
    # Token split on common separators a model uses when bundling options
    # ("Pierdere / furt", "expirat, pierdere", "schimbare-domiciliu").
    import re

    tokens = [t.strip() for t in re.split(r"[\\/,;]+", lowered) if t.strip()]
    for tok in tokens:
        if tok in by_lower:
            return by_lower[tok]
    # No match — return the original so the validator surfaces the exact
    # mismatch to the model for a deliberate retry.
    return value


def autofill_candidates(
    procedure: Procedure,
    doc_fields: Mapping[str, Any],
    citizen_attrs: Mapping[str, Any],
) -> dict[str, Any]:
    """Values the platform already knows for the document's empty fields.

    Two sources, in order: a profile attribute with the field's exact name
    (cnp, nume_complet, email, adresa_curenta, ...), then `default_from`
    (a field that copies another field's value, resolved against profile +
    fields, including values filled earlier in this same pass). Candidates
    that would not pass `validate_field_value` (e.g. a profile value that is
    not one of the field's options) are left out.
    """
    out: dict[str, Any] = {}
    for fld in procedure.fields:
        if _is_nonempty(doc_fields.get(fld.name)):
            continue
        value = citizen_attrs.get(fld.name)
        if not _is_nonempty(value) and fld.default_from:
            value = {**citizen_attrs, **doc_fields, **out}.get(fld.default_from)
        if not _is_nonempty(value):
            continue
        value = coerce_field_value(procedure, fld.name, value)
        try:
            validate_field_value(procedure, fld.name, value)
        except FieldValidationError:
            continue
        out[fld.name] = value
    return out
