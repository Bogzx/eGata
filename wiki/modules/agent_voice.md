---
type: module
path: "backend/app/agent_voice.py"
status: active
language: python
purpose: "Browser ↔ Gemini Live voice WebSocket bridge."
depends_on: [agent_tools, citizens, config, prompts, security, sessions, session_engine]
used_by: [frontend/lib/voiceWs.ts, frontend/lib/useVoiceAgentBridge.ts]
created: 2026-05-23
updated: 2026-05-23
---

# agent_voice

The voice transport. Mirrors [[agent]] but over a single bidirectional WebSocket carrying PCM audio + JSON control frames.

## Endpoint

```
WSS /agent/voice/ws
```

## Lifecycle

```
1. Browser opens WS.
2. Browser sends `{type:"start", token, document_id?, conversation_id?, preferences?}` as the first JSON frame.
3. Backend decodes the JWT, resolves or creates the Session.
4. Backend opens a `client.aio.live.connect(model=gemini-3.1-flash-live-preview, config=...)`.
5. Backend sends `{type:"ready", conversation_id}` + initial `{type:"session_snapshot", snapshot}`.
6. Backend re-seeds Live with prior session.history (turn_complete=False).
7. Three concurrent pumps (asyncio.gather):
     • mic → Gemini Live (PCM16/16k)
     • Gemini → client (audio bytes + JSON control frames for transcripts, tool calls, snapshots)
     • client → bridge (audio chunks, text frames, widget submissions, interrupt)
8. On close: update_session(session) under the conv lock.
```

## Why the conv lock spans the whole call

`async with session_lock(self.conv_id): await self._run_locked()` — the lock is held for the **entire WS lifetime**. Prevents a concurrent text turn on the same conversation from overwriting `session.history` while audio is in flight. See [[sessions]]`.session_lock`.

## Why all 7 tools are sent (not state-filtered)

```python
def _browser_function_declarations():
    return [t.function_declaration() for t in TOOLS_REGISTRY.values()]
```

Gemini Live **locks tools at connect time**. We can't filter per turn the way the text path does. So we send all 7 and the dispatcher refuses out-of-state calls — the model gets an error result it can apologize about. See [[ADR State-Gated Tool Surface]].

## The `_state` recap trick

Gemini Live also **freezes `system_instruction` at connect time**, so the model's preamble grows stale the moment a tool fires. Fix: every `tool_response` carries a `_state` key with:

```yaml
state: filling
permitted_tools: [propose_widget, set_field]
active_document_id: ...
doc:
  procedure_id: schimbare-domiciliu
  status: draft
  fields: {...}
  missing_required: [adresa_noua, tip_proprietate]
```

The system prompt explicitly tells the model to consult `_state` on every tool response (see [[prompts]] + the prompt extension in `agent_voice.py:215`). See [[State Recap]].

## Widget submission

The browser can submit a widget answer during an active voice call. Two paths mirror [[agent]]`.widget_result`:

- `target_field` set: dispatch `set_field`, send a synthetic system note to Live with `turn_complete=False` so the model knows the field was answered without responding.
- No `target_field`: forward the user's choice as a real turn (`turn_complete=True`) so the model picks the next action.

## Transcript persistence

User and agent transcripts are appended to `session.history` **in memory** as they finalize (`_flush_role`). Persisted to DB once on shutdown / disconnect — keeping the WS hot path light.

## TwiML / Twilio is a different module

This bridge is for **browser** voice. The Twilio Programmable Voice bridge ([[twilio_bridge]]) is a separate WS endpoint with its own audio codec (μ-law 8k) and a phone-specific tool allowlist.

## See also

- [[Flow Voice Browser Turn]]
- [[Voice WS Frame Schema]]
- [[ADR Single Live Session Text + Voice]]
- [[State Recap]]
- [[Frontend Voice Bridge]]
