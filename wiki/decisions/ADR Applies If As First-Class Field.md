---
type: decision
status: active
created: 2026-05-23
updated: 2026-05-23
---

# ADR: Applies If As First-Class Field

## Decision

Conditional requirements use a **declarative `applies_if` expression** on the schema (`ProcedureField.applies_if`, `NextStep.applies_if`), evaluated against `{**citizen.attrs, **doc.fields}`. **Not** branches in the procedure JSON. **Not** prompt logic.

## Why

Two cases motivated this:

- A `schimbare-domiciliu` field `anexa_2_signer` is only required when `tip_proprietate == "găzduit"`. With branches, you'd duplicate the JSON; with prompt logic, the agent's reliability decides whether the field gets asked.
- The DRPCIV next_step reminder is only applicable when `owns_vehicle == true`. With prompt logic, the reminders worker (which never sees the prompt) can't make this decision.

## Mechanism

A tiny boolean DSL ([[applies_if]]):

```
expr := or_expr | and_expr | not_expr | comparison
comparison := IDENT op value
op := "==" | "!="
value := true | false | STRING | NUMBER
```

Recursive-descent parser, ~200 lines. Tested. Used in three places:

1. **Field state evaluation** ([[procedure_state]]).
2. **Required-set transitions** ([[set_field]], [[complete_document]]).
3. **Reminder selection** ([[reminders]]`._select_applicable_steps`).

## Trade-offs

- **No function calls** — can't say `applies_if: "age(data_nasterii) >= 65"`. Trade simplicity for safety. Add a synthetic attribute (`is_senior`) when truly needed.
- **No NULL-safe access** — `attrs.get("foo")` returns `None`, which always compares unequal. This is documented behavior.

## Why not jsonpath / jsonlogic / a real expression lib

- jsonpath is a query DSL; we want predicates.
- jsonlogic embeds in JSON which is unreadable.
- A custom DSL is 200 lines, parseable, easy to test, and the syntax matches what the prompt rules already use ("when `owns_vehicle` is true").

## See also

- [[applies_if]]
- [[procedure_state]]
- [[Flow Reminders Worker]]
