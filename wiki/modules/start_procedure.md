---
type: module
path: "backend/app/agent_tools/start_procedure.py"
status: active
language: python
purpose: "Agent tool: create a Document, jump session to FILLING."
depends_on: [documents, ledger, procedures, sessions]
used_by: [session_engine, agent_voice, twilio_bridge]
valid_states: [EXPLORING, CONFIRMING_MATCH, DELIVERED]
created: 2026-05-23
updated: 2026-05-23
---

# start_procedure

Open a document. Replaces the FE's "Începe" button click. In voice-only mode this is the **only** path to open a doc.

## Parameters

```json
{ "procedure_id": "string (required)" }
```

## Behavior

1. Validate `procedure_id` exists in the registry.
2. `insert_document(citizen_id, procedure_id)`.
3. `append_ledger(... doc_created ...)` with `{document_id, procedure_id}`.
4. `session.active_document_id = doc_id`.
5. Emit `frontend_event: document_opened` and request `transition_to=FILLING`.

## Frontend reaction

`document_opened` → the FE's `sessionStore` does `pushPath("/r/" + doc_id)` (route to the request page) and fetches the procedure schema. Subsequent `field_updated` events update the form preview live.

## Valid states + why

| State | Reason it's valid |
|---|---|
| EXPLORING | Skip-confirmation: agent is confident enough to open without a confirm widget. |
| CONFIRMING_MATCH | Normal path after `lookup_procedure` + a `propose_widget(type=confirm)`. |
| DELIVERED | Start the next procedure in a scenario chain. |

## See also

- [[Flow Document Lifecycle]]
- [[Flow Session State Machine]]
