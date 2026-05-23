---
type: module
path: "backend/app/auth.py"
status: active
language: python
purpose: "Identity endpoints — ROeID mock, MRZ lookup, OTP exchange."
depends_on: [config, db, security, models]
used_by: [frontend/app/login]
created: 2026-05-23
updated: 2026-05-23
---

# auth

Three endpoints under `/auth`. All return either a `ChallengeResponse` (challenge_id + phone hint) or, on `/otp`, an `OTPResponse` (JWT + citizen id).

## Routes

| Route | Body | Returns | Notes |
|---|---|---|---|
| `POST /auth/login-roeid` | `{persona_id?: str}` | `ChallengeResponse` | Mocked ROeID. Maps persona to CNP via `PERSONA_TO_CNP`. Default persona is `maria-ionescu`. |
| `POST /auth/login-mrz` | `{cnp, nume, prenume}` | `ChallengeResponse` | Real MRZ path: looks up the citizen by `(cnp, lower(nume), lower(prenume))`. |
| `POST /auth/otp` | `{challenge_id, code}` | `OTPResponse` | Verifies code, mints a JWT. Single-use; expires after 5 minutes. |

## Mock vs real OTP

- `MOCK_OTP=1` → the only valid code is `123456`. No Twilio call. See [[ADR Mock OTP Flag]].
- `MOCK_OTP=0` → calls Twilio Verify (`verifications.create` and `verification_checks.create`). Requires `TWILIO_VERIFY_SERVICE_SID`.

## Storage

OTP challenges live in `otp_challenges` (text PK `ch_<urlsafe>`), with `consumed BOOLEAN` and `expires_at`. The verify step uses `SELECT ... FOR UPDATE` to prevent double-consume races.

## Phone hint

Never returns the full phone. `phone_hint(phone) → "***<last4>"`. The frontend shows this on the OTP screen.

## See also

- [[Flow Login + OTP]] — full sequence diagram
- [[Frontend Auth Flow]] — how the FE stores the token after `/otp`
- [[security]] — token minting
