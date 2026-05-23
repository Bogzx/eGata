---
type: flow
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Flow: Widget Round-Trip

A widget is born when the agent calls `propose_widget`. It dies when the user clicks an option (or submits a date/confirm).

## Wire-level sequence

```
agent text turn                      FE                      backend
        │                              │                          │
        │  propose_widget(...)         │                          │
        │ ────────────────────────────►│ frontend_event:          │
        │                              │  widget_proposed         │
        │                              │ store: add to            │
        │                              │   session.pendingWidgets │
        │                              │                          │
        │                              │ user clicks "proprietar" │
        │                              │                          │
        │                              │ HTTP path                │
        │                              ├─ POST /agent/widget-result
        │                              │                          ▼
        │                              │                  resolve_pending_widget(id)
        │                              │                  if target_field:
        │                              │                    dispatch set_field
        │                              │                    append synth history
        │                              │                    return snapshot,
        │                              │                      requires_chat_followup:false
        │                              │                  else:
        │                              │                    pop widget; persist
        │                              │                    return requires_chat_followup:true
        │                              │                          │
        │                              │  ◄─── snapshot ──────────│
        │                              │                          │
        │                              │ if requires_chat_followup:
        │                              │   streamChat({message: user_visible}, ...)
        │                              │   ──────────────► /agent/chat/stream
        │                              │                          ▼
        │                              │                  step() — model decides next move
```

## Two endpoints

| Path | Endpoint | When |
|---|---|---|
| Text mode | `POST /agent/widget-result` ([[agent]]`.widget_result`) | All chat sessions, even ones that opened a voice WS but it's not handling this submit. |
| Voice mode | WS frame `{"type":"widget_submission", widget_id, value}` ([[agent_voice]]`._handle_widget_submission`) | Active Live session — keeps the answer inside the Live conversation. |

Both paths have the same two-mode behavior (direct vs signal).

## Direct mode (target_field set)

1. Resolve `PendingWidget(widget_id)` and pop from `session.pending_widgets`.
2. Coerce confirm "Da"/"Nu" to bool (`_coerce_widget_value`).
3. Dispatch `set_field` with the resolved field.
4. Append a synthetic history entry: `[răspuns widget <field>] <value>` so the model has transcript continuity.
5. Voice path additionally pushes a synthetic system note to Live with `turn_complete=False` so Live absorbs the context without responding.

## Signal mode (no target_field, typical confirm in CONFIRMING_MATCH)

1. Resolve + pop.
2. Persist `session` (widget gone).
3. Return `requires_chat_followup: true`.
4. FE follows up with `streamChat({message: user_visible})` — the answer goes through the normal turn pipeline so the model can decide (`start_procedure`, abandon, etc.).

Voice signal mode: forward the answer as a real turn to Live (`turn_complete=True`).

## Why this exists at all

Skipping the model round-trip for "click an option" is faster, cheaper, and avoids parsing errors ("proprietar", "the first one", "uhh that one"). The widget IS the answer schema; the user click already has the resolved value. See [[ADR State-Gated Tool Surface]] + [[propose_widget]].

## See also

- [[propose_widget]]
- [[set_field]]
- [[PendingWidget]]
- [[agent]]
- [[agent_voice]]
