---
type: dependency
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Dep: Twilio

Two products:

| Product | Used for |
|---|---|
| Verify | OTP send + check ([[auth]]) |
| Programmable Voice + Media Streams | Phone-call audio bridge ([[twilio_bridge]]) |

Plus a third minor: outbound `messages.create` SMS on document `delivery="send"` ([[documents]]`.send_delivery_sms`).

## Env vars

```
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_VERIFY_SERVICE_SID=   # Verify product
TWILIO_PHONE_NUMBER=          # outbound SMS source
TWILIO_BRIDGE_PUBLIC_URL=     # wss://... for the TwiML <Stream>
MOCK_OTP=1                    # both OTP and SMS off; see ADR
```

## Setup

1. Twilio Verify: create a Service, copy SID into `TWILIO_VERIFY_SERVICE_SID`.
2. Programmable Voice: buy a number (or Twilio-trial number), configure the voice webhook → `POST /voice/twilio/webhook`.
3. Twilio Media Streams (no separate setup; enabled by the TwiML).
4. `TWILIO_BRIDGE_PUBLIC_URL` must be the publicly-reachable wss URL of the backend; the webhook returns this as the `<Stream url>`.

## Kill switch

`MOCK_OTP=1` skips Twilio in:

- [[auth]]`.issue_otp` — no `verifications.create`.
- [[auth]]`.verify_otp_and_consume` — no `verification_checks.create`.
- [[documents]]`.send_delivery_sms` — no `messages.create`.

See [[ADR Mock OTP Flag]].

## TwiML fallback

When `GEMINI_API_KEY` or `TWILIO_BRIDGE_PUBLIC_URL` is missing, `_bridge_is_healthy()` returns false and the webhook returns a `<Say>` apology instead of the `<Stream>`. Phone line stays usable.

## See also

- [[twilio_bridge]]
- [[Flow Phone Call Twilio]]
- [[ADR Mock OTP Flag]]
