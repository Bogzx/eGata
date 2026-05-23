---
type: contract
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Procedure JSON Schema

`backend/procedures/*.json` files. Loaded by [[procedures]]`.get_registry`. Validated by Pydantic `Procedure` model ([[models]]).

## Shape

```yaml
id: "schimbare-domiciliu"          # must equal filename (without .json)
title: "Schimbare domiciliu"
description: "Înscrierea mențiunii de stabilire a domiciliului pe cartea de identitate."
scope: "primarie" | "external"
category: "evidenta-persoanelor"
synonyms: ["mutare", "schimbat adresa", ...]
sample_queries: ["vreau să-mi schimb domiciliul", ...]

acte_necesare:                      # physical / external documents the user must bring
  - denumire: "Cerere Anexa 1"
    emitent: "primarie" | "user" | "extern"  # OR omit + use emitent_id
    emitent_id: "ocpi-ancpi"                 # references institutions/<id>.json
    format: "original" | ...
    observatie: "Cu prezența proprietarului spațiului"
    obligatoriu: true                       # default true
    alternative: ["declarație notarială..."]

fields:                              # what we fill in the document
  - name: "tip_proprietate"
    label: "Tip proprietate"
    source: "id_scan|profile|ask"
    required: true
    options: ["proprietar", "chiriaș", "găzduit"]   # optional enum
    suggest_default: "Schimbare loc de muncă"
    redact_in_voice: true | false
    applies_if: "owns_vehicle == true"              # optional conditional

template: "preschimbare-ci.tex"      # backend/templates/<this>

next_steps:                          # reminders fired by the worker after delivery
  - kind: "in_scope_procedure" | "external_redirect"
    procedure_id: "preschimbare-ci"  # in_scope only
    redirect_target: "DRPCIV"         # external only
    deadline_days: 15
    title: "..."
    applies_if: "owns_vehicle == true"   # optional
```

## Invariants

1. **Filename matches `id`**: `get_registry` raises otherwise.
2. **`template` exists** under `backend/templates/`. [[pdf]] reads it via `TEMPLATES_DIR / template`.
3. **Every `applies_if` parses** — see [[applies_if]] for the grammar.
4. **Every `emitent_id` resolves** in [[institutions]].
5. **`options`-enum fields are validated** by `set_field` ([[procedure_state]]).

## How fields drive the document lifecycle

- `source` is a hint to the agent: which fields can be auto-filled from the citizen profile / ID scan, which must be asked.
- `applies_if` decides whether the field is **required** under the current context. See [[procedure_state]] for the state vocabulary.
- `redact_in_voice` tells the voice agent never to read the value aloud (CNP, IBAN, etc.).

## See also

- [[procedures]]
- [[procedure_state]]
- [[lookup_procedure]]
- [[Flow Document Lifecycle]]
