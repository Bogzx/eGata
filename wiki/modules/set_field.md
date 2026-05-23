---
type: module
path: "backend/app/agent_tools/set_field.py"
status: active
language: python
purpose: "Agent tool: write one field on the active document with full validation."
depends_on: [documents, procedure_state, procedures, sessions]
used_by: [session_engine, agent_voice, agent (widget_result)]
valid_states: [FILLING, REVIEWING]
created: 2026-05-23
updated: 2026-05-23
---

# set_field

Write a single document field. Validates against the procedure schema (incl. options enum), coerces booleans, and decides whether the state should flip.

## Parameters

```json
{ "name": "string (required)", "value": "string (required)" }
```

> [!gotcha] `value` is always STRING in Gemini's function_declarations
> Booleans arrive as `"true"` / `"da"`. The `coerce_field_value` step in [[procedure_state]] turns them into Python bools so `applies_if` can compare correctly.

## Behavior

1. Resolve `active_document_id`. Owner check.
2. Look up the procedure. Reject unknown fields.
3. `coerce_field_value` → maybe map `"true"`/`"da"`/`"adevărat"` to `True`.
4. `validate_field_value` → raise on unknown field or out-of-options value.
5. `update_document_fields(doc_id, {name: coerced})` — `jsonb || jsonb` merge.
6. Recompute applies_if-aware required satisfaction:
   - In FILLING and all-required-satisfied → transition to REVIEWING.
   - In REVIEWING and now-incomplete (applies_if turned a non-required field required) → transition back to FILLING.
7. Emit `frontend_event: field_updated`.

## Why two transitions

A user can edit a field in review and re-trigger an `applies_if` clause. Example: in `schimbare-domiciliu`, switching `tip_proprietate` from `proprietar` to `găzduit` adds `anexa_2_signer` as a required field — REVIEWING regresses to FILLING.

## See also

- [[procedure_state]]
- [[Flow Document Lifecycle]]
- [[Flow Widget Round-Trip]]
