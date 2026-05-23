---
type: contract
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Frontend Event Schema

Structured UI directives emitted by tools. Carried by SSE `event: frontend_event` and voice WS `{type: "frontend_event", event: {...}}`. Frontend type lives at `frontend/lib/types.ts:FrontendEvent`.

## Union

```ts
type FrontendEvent =
  | { type: "document_opened";  document_id; procedure_id }
  | { type: "widget_proposed";  widget_id; widget_type; question; options; target_field }
  | { type: "field_updated";    document_id; name; value }
  | { type: "document_delivered"; document_id; pdf_url; delivery; ref_number }
  | { type: "redirect";         target; name; url }
  | { type: "lookup_returned";  matches; scenario_plan };
```

## Producers + consumers

| Event | Produced by | FE reaction |
|---|---|---|
| `document_opened` | [[start_procedure]] | `pushPath("/r/<doc_id>")`, fetch procedure, mark `activeDocId` |
| `widget_proposed` | [[propose_widget]] | Append a `WidgetSpec` to the agent's latest message; render inline |
| `field_updated` | [[set_field]] | `setDocument(d => ({...d, fields: {...d.fields, [name]: value}}))` |
| `document_delivered` | [[complete_document]] | Show success pane in the right pane (`DonePane`); navigate the `AuditTimeline` to refresh |
| `redirect` | [[find_redirect]] | Show redirect card in the right pane (`MatchesPane` / dedicated card) |
| `lookup_returned` | [[lookup_procedure]] | Render matches + (optionally) scenario plan in the right pane (`MatchesPane`, `PlanPane`) |

## Why structured events instead of "let the FE read tool_result"

Two reasons:

1. **Decoupling from prompt drift** — the LLM might phrase the result message differently each turn; the FE's UI logic must NOT depend on parsing free text.
2. **Single source of truth** — both transports carry the same event shape, so the FE store handles `frontend_event` identically whether it came from SSE or voice WS.

## See also

- [[Session Snapshot Schema]]
- [[FrontendEvent]] component view
- [[Frontend Session Mirror]]
