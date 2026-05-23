---
type: decision
status: active
created: 2026-05-23
updated: 2026-05-23
---

# ADR: Shared Engine For Text + Voice

## Decision

One agent loop — `session_engine.step()` — drives both the SSE text transport and the voice WebSocket transport. The transports are dumb pipes that wrap a typed Event stream for their wire format.

## Why

Three properties become trivial:

1. **Tool inventory parity** — adding `set_reminder` once means both modes get it.
2. **State preamble parity** — the same `build_system_instruction` builds the system prompt for both transports.
3. **Test surface** — testing `step()` covers 90% of the actual agent behavior; transport tests are just SSE / WS framing.

## Cost

Voice has constraints text doesn't (system prompt locked at connect, tools locked at connect). We accept slightly worse voice-side ergonomics — see [[State Recap]] and [[ADR State-Gated Tool Surface]] for how we work around them.

## The transport layer is *very* thin

- [[agent]] = `step()` → SSE frames. ~30 lines of meaningful adapter code.
- [[agent_voice]] = `step()`'s prompt builder + Gemini Live audio pumps + the same `agent_tools.dispatch`. The actual model loop is *Gemini Live's*, not `step()` — but the system prompt, tool registry, and dispatcher are shared.

> [!key-insight]
> The text path reuses `step()` directly because text mode lets us re-pick tools per turn. The voice path uses Gemini Live's own loop because we want native audio + barge-in, but it reuses everything *around* the loop.

## See also

- [[session_engine]]
- [[agent]]
- [[agent_voice]]
- [[State Recap]]
