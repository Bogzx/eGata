---
type: decision
status: active
created: 2026-05-23
updated: 2026-05-23
---

# ADR: Mock OTP Flag

## Decision

A single env flag `MOCK_OTP` controls two things:

1. When `1`, `/auth/otp` accepts the hardcoded code `123456` and skips Twilio.
2. When `1`, `documents.send_delivery_sms` skips outbound SMS too.

## Why

Hackathon ergonomics. Each Twilio Verify call burns credits; each outbound SMS too. During dev + demo dry-runs we'd burn through a free tier in an afternoon. The flag is the kill-switch.

## Cost

- The doubled-up meaning is non-obvious. A reader of `send_delivery_sms` sees `if settings.mock_otp: return` and might assume it's a bug.
- Production deploys MUST set `MOCK_OTP=0` (documented in [[Deployment Railway]] + the .env.example).

## Why not two flags

Considered `MOCK_OTP` + `MOCK_SMS`. Rejected because in practice they're always toggled together. The names are out of sync but the operational reality is "Twilio off" vs "Twilio on".

## What this protects against

The flag is the **only** difference between dev-Twilio and prod-Twilio. Forgetting it on prod sends `123456` to anyone who tries to log in. Tested behavior: with `MOCK_OTP=0`, attempting code `123456` on a real challenge calls `verification_checks.create` which returns `status != "approved"` → `401 invalid code`.

## See also

- [[auth]]
- [[documents]]
- [[Deployment Railway]]
