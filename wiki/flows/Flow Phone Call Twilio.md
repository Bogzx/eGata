---
type: flow
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Flow: Phone Call Twilio

Citizen calls a phone number → Twilio answers with TwiML → Twilio opens a Media Streams WS to our backend → backend bridges to Gemini Live → audio loops back over the phone.

## Sequence

```
Citizen phone        Twilio                          Backend                       Gemini Live
     │                  │                               │                              │
     │  ☎ ───────────►  │ POST /voice/twilio/webhook   │                              │
     │                  │ ────────────────────────────►│ _bridge_is_healthy?          │
     │                  │ ◄── TwiML <Connect><Stream>  │  ya → return bridge TwiML    │
     │                  │                               │  nu → fallback <Say>         │
     │                  │  WSS /voice/twilio open ────►│                              │
     │                  │  {event:"start", streamSid}  │                              │
     │   speak  ───────► │                               │                              │
     │                  │  {event:"media", mulaw b64}  │                              │
     │                  │ ────────────────────────────►│ mulaw → pcm16 16k            │
     │                  │                               │ send_realtime_input  ───────►│
     │                  │                               │                              │ audio out
     │                  │                               │ ◄────── pcm16 24k ──────────│
     │                  │                               │ pcm 24k → mulaw 8k          │
     │                  │  ◄── {event:"media", mulaw}  │                              │
     │   hear  ◄─────── │                               │                              │
     │                  │                               │ tool_call                    │
     │                  │                               │ ◄ function_calls            ─│
     │                  │                               │ allowlist check + dispatch  │
     │                  │                               │ send_tool_response   ───────►│
```

## Endpoints

| Route | Verb | Returns |
|---|---|---|
| `/voice/twilio/webhook` | POST | TwiML (`<Connect><Stream url=...>` or fallback `<Say>`) |
| `/voice/twilio` | WSS | Binary + JSON over the Twilio Media Streams envelope |

## Audio codec

Phone audio is **μ-law 8 kHz**. Gemini Live wants **PCM16 16 kHz**. Transcoding via `audioop` ([[twilio_bridge]]):

| Direction | Steps |
|---|---|
| Twilio → Gemini | μ-law → linear PCM16 8k → resample to 16k |
| Gemini → Twilio | PCM16 24k → resample to 8k → linear → μ-law |

## Ephemeral session

No JWT (Twilio is the trusted client). No Postgres row. `Session(state=EXPLORING, citizen_id="phone-anonymous")` lives in memory for the call's duration. No history persistence.

## Phone tool allowlist

```python
PHONE_TOOL_ALLOWLIST = {"lookup_procedure", "find_redirect"}
```

Anything else (`set_field`, `start_procedure`, `complete_document`, ...) returns `{"error":"tool_not_available_on_phone"}` to the model. See [[ADR Phone Tool Allowlist]].

## Phone prompt

`prompts.PHONE_SYSTEM`:

- Read `acte_necesare` aloud, marking obligatorii vs. opționale.
- Always close with "vizitați civicai.ro pentru completare online".
- Never read CNPs aloud.
- Replies under 30s.

## TwiML fallback

`_bridge_is_healthy()` checks `GEMINI_API_KEY` AND `TWILIO_BRIDGE_PUBLIC_URL`. If either is missing → return a `<Say>` apology in Romanian. Keeps the line from breaking when Gemini quota drains.

## See also

- [[twilio_bridge]]
- [[Twilio WS Frame Schema]]
- [[Dep Twilio]]
- [[ADR Phone Tool Allowlist]]
