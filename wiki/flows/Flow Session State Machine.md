---
type: flow
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Flow: Session State Machine

The six states a `Session` can be in, who triggers each transition, and which tools are available in each.

## States

```
                  ┌─────────────┐
   user resets ───┤  EXPLORING  │◄─── any state can reset
                  └──────┬──────┘
                         │ lookup_procedure
                         ▼
                  ┌──────────────────┐
   user cancels ◄─┤ CONFIRMING_MATCH │── find_redirect ──► REDIRECTED
                  └──────┬───────────┘
                         │ start_procedure / confirm widget
                         ▼
                  ┌─────────────┐
                  │   FILLING   │◄────────┐
                  └──────┬──────┘         │
                         │ set_field      │ set_field (applies_if
                         │ (all required  │  re-enables a field)
                         │  satisfied)    │
                         ▼                │
                  ┌─────────────┐         │
                  │  REVIEWING  ├─────────┘
                  └──────┬──────┘
                         │ complete_document
                         ▼
                  ┌─────────────┐
                  │  DELIVERED  │
                  └──────┬──────┘
                         │ start_procedure (next scenario step)
                         │ lookup_procedure (new request)
                         ▼
                       (FILLING or CONFIRMING_MATCH)
```

Plus `REDIRECTED` (out-of-primărie) which only goes back to `EXPLORING`.

## Allowed transitions (`backend/app/sessions.py:_TRANSITIONS`)

| From | To |
|---|---|
| EXPLORING | EXPLORING, CONFIRMING_MATCH, FILLING (legacy doc-injection), REDIRECTED |
| CONFIRMING_MATCH | CONFIRMING_MATCH, EXPLORING, FILLING, REDIRECTED |
| FILLING | FILLING, REVIEWING, EXPLORING, REDIRECTED |
| REVIEWING | REVIEWING, FILLING (applies_if regression), DELIVERED, EXPLORING |
| DELIVERED | DELIVERED, EXPLORING, CONFIRMING_MATCH, FILLING (scenario step 2) |
| REDIRECTED | REDIRECTED, EXPLORING |

Any other move raises `IllegalTransitionError`. Tools that *request* an illegal transition still succeed; the warning surfaces as `output.warnings` (see [[agent_tools]] dispatcher).

## Permitted tools per state

See [[agent_tools]]. Two patterns matter:

- `find_redirect` and `lookup_procedure` are **OFF during FILLING / REVIEWING** — see [[ADR State-Gated Tool Surface]].
- `set_field` and `propose_widget` overlap in FILLING — the agent uses propose_widget for structured questions and falls through to set_field when the user answers.

## Where state lives

- In memory: `Session.state` (Python enum).
- In DB: `sessions.state` TEXT with a check constraint mirroring the enum.
- On the wire: `SessionSnapshot.state` ([[Session Snapshot Schema]]).
- In the FE store: `session.state` in the Zustand mirror.

## See also

- [[sessions]]
- [[ADR State Machine Over Free-Form Agent]]
- [[Session Aggregate]]
