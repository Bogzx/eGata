---
type: module
path: "backend/app/agent_tools/propose_widget.py"
status: active
language: python
purpose: "Agent tool: emit a structured UI widget the FE renders inline."
depends_on: [sessions]
used_by: [session_engine, agent_voice]
valid_states: [FILLING, CONFIRMING_MATCH]
created: 2026-05-23
updated: 2026-05-23
---

# propose_widget

Send a structured question instead of plain prose. The FE renders an inline widget; the user's answer round-trips as a structured submission, never as parsed text.

## Parameters

```json
{
  "type": "choice|confirm|date",
  "question": "string",
  "options": ["..."],           // required for type=choice
  "target_field": "string"      // required for type=choice/date
}
```

## Behavior

1. Validate the type and the per-type required args (choice → ≥2 options + target_field, date → target_field).
2. `widget_id = uuid4().hex[:12]`.
3. `session.add_pending_widget(PendingWidget(...))`.
4. Return the widget metadata in `output` AND emit `frontend_event: widget_proposed`.

The PendingWidget is removed from `session.pending_widgets` when the user clicks an option, via [[agent]]`.widget_result` (text) or [[agent_voice]]`._handle_widget_submission` (voice).

## Widget types in use

| Type | When | Example |
|---|---|---|
| `choice` | A field with a fixed `options` list | `tip_proprietate` → ["proprietar","chiriaș","găzduit"] |
| `confirm` | After a `lookup_procedure` match in CONFIRMING_MATCH | "Confirmi că vrei să-ți schimbi domiciliul?" |
| `date` | A date field that's awkward to type | `data_emitere_ci` |

Confirm widgets typically have **no `target_field`** — the answer is a *signal* the agent reacts to (start_procedure / abandon), not a field set. See [[Flow Widget Round-Trip]].

## See also

- [[Flow Widget Round-Trip]]
- [[PendingWidget]]
- [[sessions]]
