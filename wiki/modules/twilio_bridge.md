---
type: module
path: "backend/app/twilio_bridge.py"
status: active
language: python
purpose: "Twilio Media Streams ↔ Gemini Live bridge for phone calls."
depends_on: [agent_tools, config, prompts, sessions]
used_by: [Twilio webhook in production]
created: 2026-05-23
updated: 2026-05-23
---

# twilio_bridge

A second voice bridge — same shape as [[agent_voice]] but for the **phone** path. Twilio Programmable Voice → Media Streams → this WS → Gemini Live.

## Endpoints

| Route | Returns | Notes |
|---|---|---|
| `POST /voice/twilio/webhook` | TwiML | Returns either the `<Connect><Stream>` TwiML pointing at `TWILIO_BRIDGE_PUBLIC_URL` (when healthy) or a fallback `<Say>` apology. |
| `WSS /voice/twilio` | binary + JSON | Twilio Media Streams sends `{event, streamSid, media:{payload}}` envelopes; backend transcodes and proxies to Gemini Live. |

## Audio transcode

Phone audio is **μ-law 8 kHz mono**, base64 in a JSON envelope.

- Inbound: `mulaw → pcm16_8k → pcm16_16k` (`audioop.ulaw2lin` + `audioop.ratecv`).
- Outbound: `pcm16_24k → pcm16_8k → mulaw` (reverse).

Gemini Live expects PCM16/16k in and emits PCM16/24k out.

## Phone-mode constraints

- **Ephemeral session** — no Postgres row, no persistence. `citizen_id = "phone-anonymous"`. No JWT (Twilio is trusted on the WS side).
- **Restricted tool allowlist**:

  ```python
  PHONE_TOOL_ALLOWLIST = {"lookup_procedure", "find_redirect"}
  ```

  No document writes from phone. See [[ADR Phone Tool Allowlist]].

- **Phone system prompt** — `prompts.PHONE_SYSTEM`. Tells the model: read `acte_necesare` aloud, send the citizen to civicai.ro for completion, never read CNPs aloud.

## TwiML fallback

If `GEMINI_API_KEY` is missing or `TWILIO_BRIDGE_PUBLIC_URL` is not set, the webhook returns:

> Bună ziua. Asistentul vocal este indisponibil momentan. Vă rugăm să vizitați civicai.ro pentru asistență completă.

Keeps the phone line from breaking when Gemini quota drains.

## See also

- [[Flow Phone Call Twilio]]
- [[Twilio WS Frame Schema]]
- [[Dep Twilio]]
- [[prompts]]
