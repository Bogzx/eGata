---
type: module
path: "backend/app/citizens.py"
status: active
language: python
purpose: "Citizen profile read + attribute patch."
depends_on: [db, security, models]
used_by: [frontend home page, agent (reads attributes for context preamble)]
created: 2026-05-23
updated: 2026-05-23
---

# citizens

Two endpoints under `/citizens`:

| Route | Returns | Notes |
|---|---|---|
| `GET /citizens/me` | `CitizenResponse` | Pulls the row keyed by JWT `sub`. |
| `PATCH /citizens/me/attributes` | `CitizenResponse` | Shallow `jsonb \|\| jsonb` merge — adds or overwrites keys but doesn't clobber the whole object. |

## Citizen attributes

`citizens.attributes` is `jsonb`. The schema is loose — fields the system understands (and uses in `applies_if`):

```
owns_vehicle        boolean
marital_status      "necăsătorit" | "căsătorit" | "divorțat" | "văduv"
has_children        boolean
employer            string
medic_familie       string
preferred_language  "ro" | "en"
current_address     string
accessibility       { voice_only?, simple_language?, large_text? }
```

Anything else is allowed via `model_config = ConfigDict(extra="allow")` on `CitizenAttributes` ([[models]]).

## Why attributes drive everything

The agent uses these in three places:

1. **Auto-fill** — `nume_complet`, `cnp`, `current_address` come from here without asking.
2. **Conditional fields** — `applies_if: "owns_vehicle == true"` on a `next_step` decides whether to write a DRPCIV reminder ([[Flow Reminders Worker]]).
3. **Accessibility modes** — `accessibility.voice_only` flips the agent into `voice_only` mode via the chat `preferences` arg.

## See also

- [[applies_if]]
- [[Flow Reminders Worker]]
