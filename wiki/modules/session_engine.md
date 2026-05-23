---
type: module
path: "backend/app/session_engine.py"
status: active
language: python
purpose: "The shared Gemini text loop. One step() drives both SSE and voice transports."
depends_on: [agent_tools, citizens, config, documents, procedures, prompts, sessions, text_hygiene]
used_by: [agent, agent_voice (only for build_system_instruction)]
created: 2026-05-23
updated: 2026-05-23
---

# session_engine

The actual agent loop. One `step()` per user turn. Yields typed events to the caller; the caller wraps them for its transport.

## Event vocabulary

| Event | Data | When |
|---|---|---|
| `delta` | `{text: full_so_far}` | Agent text grew. Carries the cumulative transcript-so-far, not the delta — UI just replaces. |
| `tool_call` | `{name, arguments}` | Model emitted a function_call. |
| `tool_result` | `{name, output, error}` | Dispatcher returned. |
| `frontend_event` | `{...}` | Tool surfaced a UI directive (e.g. `document_opened`). |
| `session_snapshot` | snapshot dict | Pushed after every state mutation. |
| `done` | `{message, tool_calls}` | Turn complete. |
| `error` | `{detail}` | Fatal — Gemini call failed or unhandled exception. |

[[SSE Frame Schema]] documents how the text transport maps these to wire frames; the voice WS uses the same events under different JSON envelopes ([[Voice WS Frame Schema]]).

## Loop structure

1. **Rehydrate** `session.history` into Gemini `Content` objects.
2. **Append** the user's message as a `user` Content.
3. **Persist user turn now** into `session.history` so a mid-stream crash doesn't lose it.
4. **Yield initial `session_snapshot`** (state at turn start).
5. **For up to 5 iterations** (`_MAX_TOOL_LOOP_ITERATIONS`):
   - Build a `GenerateContentConfig` with state-filtered `function_declarations` ([[agent_tools]]`.permitted_tools`) and the per-turn system prompt.
   - Open a streaming call: `client.aio.models.generate_content_stream(...)`.
   - Pump chunks → emit `delta` events as text accumulates.
   - On `function_call` parts → dispatch via `agent_tools.dispatch`, emit `tool_call` + `tool_result` + optional `frontend_event` + post-mutation `session_snapshot`. Append a `function_response` Content. Loop again.
   - Text-only chunk → no function calls → break out, emit `done`.
6. **Persist final history** into `session.history`. Caller commits.

## System prompt assembly

`build_system_instruction(session, citizen_attrs, *, simple_language, voice_only)` glues together:

- The base prompt ([[prompts]]) variant (conversational or phone, plus optional a11y directives).
- A citizen profile preamble.
- A doc state preamble ([[procedure_state]]`.evaluate_field_states`) so the model always sees the *current* missing-required set.
- `Stare sesiune: <state>` + `Tool-uri permise: [...]` — the model knows what it can do this turn.

This is also called by [[agent_voice]] to build the system prompt sent at Gemini Live connect time (Live freezes system_instruction; see [[ADR Shared Engine For Text + Voice]] + [[State Recap]]).

## Thinking budget = 0

```python
thinking_config=genai_types.ThinkingConfig(thinking_budget=0)
```

Gemini 2.5 Flash defaults to "auto" thinking. On some turns it produces only `thought=True` parts which the SDK filters out, leaving an empty response. We disable it: we want tool calls + text, not chain-of-thought.

## Text hygiene

Each iteration's text runs through `strip_thinking()` ([[text_hygiene]]) so leaked `<thinking>` tags or chain-of-thought never re-enters Gemini history.

## Persistence contract

`step()` **mutates** `session.history` in place but does NOT call `update_session()`. The caller persists at the transport edge, in a `finally`-block. This avoids double-write storms when both transports fire on the same conversation.

## See also

- [[Flow Agent Text Turn]]
- [[Flow Voice Browser Turn]]
- [[ADR Shared Engine For Text + Voice]]
