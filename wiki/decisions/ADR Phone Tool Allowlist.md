---
type: decision
status: active
created: 2026-05-23
updated: 2026-05-23
---

# ADR: Phone Tool Allowlist

## Decision

The Twilio phone bridge restricts the agent to two tools:

```python
PHONE_TOOL_ALLOWLIST = {"lookup_procedure", "find_redirect"}
```

Anything else is rejected with `{"error":"tool_not_available_on_phone"}` returned to the model.

## Why

The phone agent is **anonymous** — no JWT, no citizen identity, no authorization. So it cannot:

- Open or modify a document (no citizen to attribute it to).
- Generate a PDF or deliver (same).
- Propose widgets (no FE to render them).

What it *can* do: read out what a procedure requires, and tell the caller where to go for things the primărie doesn't handle. Both via the two RAG tools.

## Why a separate allowlist instead of state-gating

State-gating ([[ADR State-Gated Tool Surface]]) already prevents document writes when there's no `active_document_id`. The allowlist is **belt + suspenders** — even if a future tool decides "ah, the session is empty, let me create an anonymous doc", the phone bridge still won't let it.

## What happens when the agent tries an excluded tool

```python
fr_parts.append(FunctionResponse(
    id=call_id, name=fc.name,
    response={"error": "tool_not_available_on_phone"},
))
```

The model gets the response. The phone prompt ([[prompts]]`.PHONE_SYSTEM`) already tells it to send the caller to civicai.ro for anything beyond information.

## See also

- [[twilio_bridge]]
- [[Flow Phone Call Twilio]]
- [[prompts]]
