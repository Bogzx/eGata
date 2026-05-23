---
type: component
status: active
created: 2026-05-23
updated: 2026-05-23
---

# State Recap

A trick specific to the **voice path**. Gemini Live freezes `system_instruction` at connect time, so the agent's "current state / permitted tools / missing fields" preamble grows stale the moment a tool fires.

## The trick

Every `tool_response` sent back to Live carries an extra `_state` key with the current state recap. The system prompt (composed in [[agent_voice]]`._run_inner`) explicitly tells the model to consult `_state` on each tool response instead of trusting the (stale) system preamble.

## Shape

```json
{
  "state": "filling",
  "permitted_tools": ["propose_widget", "set_field"],
  "active_document_id": "...",
  "doc": {
    "procedure_id": "schimbare-domiciliu",
    "status": "draft",
    "fields": {...},
    "missing_required": ["adresa_noua", "tip_proprietate"]
  }
}
```

`missing_required` is computed via [[procedure_state]]`.evaluate_field_states` — applies_if-aware.

## Producer

`VoiceBridgeSession._state_recap()` in [[agent_voice]]. Folded into every `tool_response.output` in `_dispatch_tool()`.

## See also

- [[agent_voice]]
- [[procedure_state]]
- [[ADR Single Live Session Text + Voice]]
- [[ADR Shared Engine For Text + Voice]]
