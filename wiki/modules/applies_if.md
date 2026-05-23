---
type: module
path: "backend/app/applies_if.py"
status: active
language: python
purpose: "Tiny boolean-expression evaluator for procedure next_steps + conditional fields."
depends_on: []
used_by: [procedure_state, reminders]
created: 2026-05-23
updated: 2026-05-23
---

# applies_if

A 200-line recursive-descent parser for a tiny boolean DSL.

## Grammar

```
expr      := or_expr
or_expr   := and_expr ("or" and_expr)*
and_expr  := not_expr ("and" not_expr)*
not_expr  := "not" not_expr | atom
atom      := "(" expr ")" | comparison
comparison := IDENT op value
op        := "==" | "!="
value     := "true" | "false" | STRING | NUMBER
```

## Example expressions in the wild

```python
"owns_vehicle == true"
"tip_proprietate == \"găzduit\""
"marital_status == \"căsătorit\" and has_children == true"
```

## Semantics

- Missing attribute → resolves to `None`, compares unequal to any literal.
- Empty / null expression → returns `True` (default: applies).
- Identifiers in the literal position only resolve to `true` / `false` — anything else is a ParseError to catch typos.
- Strings support `\"` and `\\` escapes; everything else (incl. Unicode) is literal.

## Where it runs

1. **Conditional fields** ([[procedure_state]]) — `ProcedureField.applies_if`, evaluated against `{**citizen.attrs, **doc.fields}`. Field becomes inapplicable, no longer required.
2. **Conditional reminders** ([[reminders]]) — `NextStep.applies_if`, evaluated against `citizen.attrs` alone (`_select_applicable_steps`).

## See also

- tests/test_applies_if.py — coverage of grammar edge cases
