---
type: decision
status: active
created: 2026-05-23
updated: 2026-05-23
---

# ADR: State Machine Over Free-Form Agent

## Decision

The conversation is **always** in one of six explicit states (EXPLORING, CONFIRMING_MATCH, FILLING, REVIEWING, DELIVERED, REDIRECTED). Every state transition goes through `sessions.transition()` which raises on illegal moves. Every tool declares which states it's valid in.

## Why

A pure ReAct agent free to call any tool at any time, with all behavior driven by prompt rules, fails in three repeated ways:

1. **Mid-fill RAG pivots** — the agent sees "vreau și impozit" and helpfully calls `lookup_procedure` again, abandoning a half-filled document.
2. **Premature PDF generation** — the model decides "looks complete" and skips the review step.
3. **Tool storms** — Gemini's auto-thinking sometimes loops on the same tool.

The state machine makes these errors **impossible** at the dispatcher layer, not "discouraged by the prompt". The model can still produce text about ANAF mid-fill, it just can't fire the tool that mutates state.

## Cost

- A new state needs a column entry in `_TRANSITIONS` + a migration to the `sessions.state` check constraint + per-tool `valid_states` updates.
- The "legacy doc-injection" path (frontend posts `/documents` then chats with a `document_id`) has to be folded into the machine — see [[agent]]`._resolve_session` which transitions `EXPLORING/CONFIRMING_MATCH → FILLING`.

## See also

- [[sessions]]
- [[agent_tools]]
- [[Flow Session State Machine]]
- [[ADR State-Gated Tool Surface]]
