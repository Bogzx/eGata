---
type: module
path: "backend/app/prompts.py"
status: active
language: python
purpose: "Romanian system prompts — conversational + phone + a11y directives."
depends_on: []
used_by: [session_engine, agent_voice, twilio_bridge]
created: 2026-05-23
updated: 2026-05-23
---

# prompts

Three prompt blocks + a builder.

```python
build_system_prompt(variant="conversational"|"phone", simple_language=bool, voice_only=bool) -> str
```

## Variants

- **CONVERSATIONAL_SYSTEM** — the main browser/chat prompt. 14 rules. Hot ones:
  - **Rule 0** (absolute): always reply in Romanian, even if transcript is garbled / wrong language.
  - **Rule 1**: in-scope = primărie. Out-of-scope → use [[find_redirect]].
  - **Rule 2/2a/2b**: distinguish `lookup_procedure` (semantic search for a need) from `list_procedures` (catalog browse for "what can you help me with?").
  - **Rule 5**: never read CNPs aloud.
  - **Rule 6**: read `acte_necesare` faithfully — never invent documents.
  - **Rule 10**: use `propose_widget` instead of listing options in prose.
  - **Rule 11**: under 15 words. No `<thinking>`. No "let me think...".
  - **Rule 12**: long content lives in the right pane via tools, not in chat.
  - **Rule 13–14**: for scenario plans, summarise in 1–2 sentences and let the user pick.

- **PHONE_SYSTEM** — 7 rules. Phone agent never completes documents; tells the citizen what they need and sends them to civicai.ro. No CNPs aloud. Voice-friendly cadence.

- **SIMPLE_LANGUAGE_DIRECTIVE** — appended when `simple_language=true`. "Speak like to a 6th-grader. Replace 'domiciliu fiscal' with 'adresa unde plătești impozite'."

- **VOICE_ONLY_DIRECTIVE** — appended when `voice_only=true`. "User isn't looking at a screen — numerate lists, confirm every field aloud, read back values."

## Where the variant is picked

| Caller | Variant | Source |
|---|---|---|
| [[session_engine]] | `conversational` | Defaulted via `build_system_instruction()` |
| [[agent_voice]] | `conversational` + per-call `simple_language`/`voice_only` from the WS `start` frame | Indirectly through `build_system_instruction()` |
| [[twilio_bridge]] | `phone` | Hardcoded — never any other variant |

## See also

- [[Flow Agent Text Turn]]
- [[Flow Phone Call Twilio]]
- [[Flow Voice Browser Turn]]
