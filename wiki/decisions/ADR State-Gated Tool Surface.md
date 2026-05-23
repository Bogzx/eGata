---
type: decision
status: active
created: 2026-05-23
updated: 2026-05-23
---

# ADR: State-Gated Tool Surface

## Decision

Each tool declares `valid_states: set[SessionState]`. The dispatcher (`agent_tools.dispatch`) refuses out-of-state calls and returns an error result to the model. **This is a hard guarantee, not a prompt hint.**

The text transport additionally **filters** the `function_declarations` passed to Gemini per turn: only permitted tools are even visible. Voice cannot filter (Live locks tools at connect time) — there we send all 7 and rely on the dispatcher to refuse.

## Why

Three failure modes the prompt-only approach cannot prevent:

1. **`find_redirect` mid-fill** — model decides the user wants ANAF, fires the tool, session jumps to REDIRECTED, half-filled doc abandoned.
2. **`lookup_procedure` mid-fill** — model wants to "double-check" the procedure, fires lookup, transitions to CONFIRMING_MATCH, doc lost.
3. **`complete_document` in FILLING** — model decides looks done, fires it, gets a PDF with empty fields.

All three are blocked at the dispatcher layer with a single-line check. The prompt rules are still there (rule 12 in [[prompts]] etc.) but they're belt+suspenders, not the safety net.

## Cost

- A new tool needs `valid_states` set explicitly. Forgetting it = `set()` = never callable. Cheap mistake to catch.
- The voice path has to deal with model apologies ("Îmi pare rău, nu pot să..."). Acceptable — the user typically gets a sane recovery line.
- Adding a state requires reviewing every tool's `valid_states` — there are only 7 tools.

## Why error-result not exception

A returned error feeds back to the model as a function response with `{"error": "..."}`. The model can apologize, suggest an alternative, recover. An exception would tear down the turn — worse UX.

## See also

- [[agent_tools]]
- [[Flow Session State Machine]]
- [[ADR State Machine Over Free-Form Agent]]
