---
type: module
path: "backend/app/text_hygiene.py"
status: active
language: python
purpose: "Strip <thinking>, <scratchpad>, chain-of-thought leakage from agent text."
depends_on: []
used_by: [session_engine]
created: 2026-05-23
updated: 2026-05-23
---

# text_hygiene

A small utility. `strip_thinking(text)` removes any `<thinking>...</thinking>`, `<scratchpad>...</scratchpad>` blocks the model might emit despite the system-prompt instruction not to. Called per loop-iteration in [[session_engine]] before the text is folded into Gemini history — chain-of-thought never re-enters the context.

## Why it exists

Even with `thinking_config(thinking_budget=0)` and a strong prompt rule, some Gemini turns leak thinking-style preamble. Stripping at the engine boundary keeps:

1. The user from seeing "let me think about this..." in their bubble.
2. The history clean so the model doesn't reinforce the pattern on the next turn.
