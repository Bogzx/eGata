---
type: component
status: active
created: 2026-05-23
updated: 2026-05-23
---

# PendingWidget

Server-side record of an unanswered widget. Lives in `session.pending_widgets`.

## Shape

```python
@dataclass
class PendingWidget:
    widget_id: str             # uuid4().hex[:12]
    type: str                  # "choice" | "confirm" | "date"
    question: str
    target_field: str | None   # None for confirm-in-CONFIRMING_MATCH
    options: list[str]         # only meaningful for choice
```

Persisted as jsonb. Rehydrated by [[sessions]]`._row_to_session` as a list of dataclasses.

## Lifecycle

1. **Created** by [[propose_widget]] — `session.add_pending_widget(widget)`. Pushed to FE via `frontend_event: widget_proposed`.
2. **Mirrored** by FE in `session.pendingWidgets`. UI renders an inline widget on the agent's bubble.
3. **Resolved** by user click → frontend posts `/agent/widget-result` (text) or sends WS `widget_submission` (voice).
4. **Popped** server-side via `session.resolve_pending_widget(widget_id)`.
5. **Persisted** via `update_session(session)`.

Snapshots that follow no longer carry the widget; the FE store reconciles and drops the inline widget.

## See also

- [[propose_widget]]
- [[Flow Widget Round-Trip]]
- [[Session Snapshot Schema]]
