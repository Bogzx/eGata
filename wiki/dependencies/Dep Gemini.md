---
type: dependency
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Dep: Gemini

Google's LLM. Three surface areas:

| Surface | Model | Used by |
|---|---|---|
| Text generation | `gemini-2.5-flash` (env `GEMINI_MODEL`) | [[session_engine]] (text agent loop) |
| Voice (audio in + out, native) | `gemini-3.1-flash-live-preview` (env `GEMINI_VOICE_MODEL`) | [[agent_voice]], [[twilio_bridge]] |
| Embeddings | `gemini-embedding-001` (constant in [[embeddings]]) | RAG over procedures + scenarios |

Voice voice: `Aoede` (env `GEMINI_VOICE_NAME`). Language: `ro-RO`.

## Env

```
GEMINI_API_KEY=<key from aistudio.google.com>
GEMINI_MODEL=gemini-2.5-flash
GEMINI_VOICE_MODEL=gemini-3.1-flash-live-preview
GEMINI_VOICE_NAME=Aoede
```

## Quirks we work around

1. **Auto-thinking returns empty parts**. Solution: `thinking_config=ThinkingConfig(thinking_budget=0)` ([[session_engine]]). Wants tool calls + text, not chain-of-thought.
2. **Live freezes `system_instruction` at connect**. Solution: embed a `_state` recap in every tool response. See [[State Recap]] + [[ADR Single Live Session Text + Voice]].
3. **Live freezes `tools` at connect**. Solution: send all 7 tools; dispatcher refuses out-of-state calls. See [[ADR State-Gated Tool Surface]].
4. **`value` capped at STRING in function declarations**. Solution: `coerce_field_value` ([[procedure_state]]) maps "true"/"da" → `True` before validation.

## Client

`from google import genai` (google-genai >=2.0). Singleton client per worker (`lru_cache` in [[embeddings]]; module-level singleton in [[session_engine]]).

## Cost shape

- Text turns: per input + output token. Cheap with `gemini-2.5-flash`.
- Voice: per session-minute. Live is the expensive part — keep WS connections short.
- Embeddings: per call. We embed once per query (no caching layer yet).

## See also

- [[session_engine]]
- [[agent_voice]]
- [[twilio_bridge]]
- [[embeddings]]
- [[Flow Voice Browser Turn]]
