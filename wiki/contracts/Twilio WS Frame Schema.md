---
type: contract
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Twilio WS Frame Schema

`WSS /voice/twilio`. Twilio Media Streams envelopes — JSON over WS, audio as base64 inside.

## Inbound (Twilio → backend)

```json
{ "event": "connected", "protocol":"Call", "version":"..." }
{ "event": "start",     "streamSid":"MZ...", "start": { ...callSid, mediaFormat, etc... } }
{ "event": "media",     "streamSid":"MZ...", "media": { "track":"inbound", "payload":"<b64 μ-law>" } }
{ "event": "stop",      "streamSid":"MZ..." }
```

`parse_twilio_frame(msg)` ([[twilio_bridge]]) extracts `(event, stream_sid, audio_mulaw)`. Only `media` carries audio.

## Outbound (backend → Twilio)

```json
{ "event": "media", "streamSid": "MZ...", "media": { "payload": "<b64 μ-law>" } }
```

Stream SID must echo the inbound one (saved in `stream_sid_holder`).

## Audio codec

μ-law 8 kHz on the wire. We transcode to/from PCM16 16k for Gemini Live (see [[twilio_bridge]] + [[Flow Phone Call Twilio]]).

## TwiML webhook contract

`POST /voice/twilio/webhook` returns one of:

**Bridge active:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="wss://<TWILIO_BRIDGE_PUBLIC_URL>" />
  </Connect>
</Response>
```

**Fallback** (when `_bridge_is_healthy()` is false):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="ro-RO">Bună ziua. Asistentul vocal este indisponibil momentan. Vă rugăm să vizitați civicai.ro pentru asistență completă. Mulțumim.</Say>
</Response>
```

## See also

- [[twilio_bridge]]
- [[Flow Phone Call Twilio]]
- [[Dep Twilio]]
