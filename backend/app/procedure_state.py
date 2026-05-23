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

from dataclasses import dataclass, field
from typing import Any, Mapping

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
    per_field: dict[str, "PerFieldState"] = field(default_factory=dict)


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


def validate_field_value(procedure: Procedure, name: str, value: Any) -> None:
    """Raise FieldValidationError if the value violates the procedure schema."""
    fld = find_field(procedure, name)
    if fld is None:
        raise FieldValidationError(
            f"Câmp necunoscut '{name}' pentru procedura '{procedure.id}'."
        )
    if fld.options is not None and isinstance(value, str):
        if value not in fld.options:
            raise FieldValidationError(
                f"Valoare invalidă pentru '{name}': "
                f"{value!r} nu este în {fld.options}."
            )
