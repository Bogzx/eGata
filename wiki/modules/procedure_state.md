---
type: module
path: "backend/app/procedure_state.py"
status: active
language: python
purpose: "applies_if-aware field-state evaluator + validator + coercer."
depends_on: [applies_if, models]
used_by: [agent_tools/set_field, agent_tools/complete_document, agent_voice (state recap), session_engine (doc state lines)]
created: 2026-05-23
updated: 2026-05-23
---

# procedure_state

The state machine for a single document's field set. Given a procedure + filled fields + citizen attributes, decides for every field whether it's `applicable / required / satisfied / missing / dropped`.

## Why this exists separately

[[documents]] has a simpler `_all_required_present` that ignores `applies_if`. The agent path needs the smart version so it doesn't keep asking for a field that no longer applies (e.g. `anexa_2_signer` after `tip_proprietate` changed from `găzduit` back to `proprietar`).

## Per-field state vocabulary

| State | Meaning |
|---|---|
| `applicable` | `applies_if` is true or unset |
| `required` | applicable AND `required: true` |
| `satisfied` | applicable AND value is non-empty |
| `missing` | required AND NOT satisfied |
| `dropped` | NOT applicable AND value is non-empty (lingering value, ignore) |

We never delete dropped values — keeping them stable across applies_if flips makes the state transitions clean.

## Merged context

```python
ctx = {**citizen_attrs, **doc_fields}
```

Doc fields **shadow** citizen attrs (a doc-level `current_address` overrides the citizen one). Useful for cases like `tip_proprietate == "găzduit"` triggering the `anexa_2_signer` field.

## Public API

| Function | Use |
|---|---|
| `evaluate_field_states(procedure, doc_fields, citizen_attrs) → FieldStates` | Full snapshot; consumed by the agent preamble and [[State Recap]] |
| `all_required_satisfied(...) → bool` | The gate for FILLING → REVIEWING transition |
| `validate_field_value(procedure, name, value)` | Raises `FieldValidationError` on unknown field or out-of-options |
| `coerce_field_value(procedure, name, value)` | Maps "true"/"da"/"adevărat" → `True`; leaves option-bound fields untouched |

## Why the coercer exists

Gemini's `function_declarations` cap `value` at JSON-schema **STRING**. Booleans arrive as `"true"` / `"da"`, and `applies_if` expressions like `owns_vehicle == true` would never match. The coercer handles this transparently before the validator runs.

> [!gotcha] Numeric coercion is intentionally out of scope
> Strings like `"1234567"` might be ints OR CNPs/IBANs that must stay strings. We don't guess.

## See also

- [[applies_if]]
- [[set_field]]
- [[complete_document]]
