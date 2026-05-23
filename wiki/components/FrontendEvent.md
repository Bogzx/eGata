---
type: component
status: active
created: 2026-05-23
updated: 2026-05-23
---

# FrontendEvent

A structured UI directive emitted by a tool. Decouples the FE from the model's free-text output. See [[Frontend Event Schema]] for the wire shape.

## Sources

| Event | Tool | Module |
|---|---|---|
| `document_opened` | start_procedure | [[start_procedure]] |
| `widget_proposed` | propose_widget | [[propose_widget]] |
| `field_updated` | set_field | [[set_field]] |
| `document_delivered` | complete_document | [[complete_document]] |
| `redirect` | find_redirect | [[find_redirect]] |
| `lookup_returned` | lookup_procedure | [[lookup_procedure]] |

## Wire transport

- SSE frame: `event: frontend_event` + JSON body
- Voice WS frame: `{"type":"frontend_event","event":{...}}`

The FE's `sessionStore` has one `applyFrontendEvent(e)` handler — same code path for both transports.

## See also

- [[Frontend Event Schema]]
- [[Frontend Session Mirror]]
