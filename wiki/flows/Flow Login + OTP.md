---
type: flow
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Flow: Login + OTP

The bootstrap path. Two entry points (ROeID mock vs MRZ), one verification step, one resulting JWT.

## Diagram

```
Frontend                          Backend                              DB / Twilio
   │                                 │                                     │
   │  POST /auth/login-roeid {pid}   │                                     │
   │────────────────────────────────►│ fetch_citizen_by_persona_id          │
   │                                 │ → citizens row                       │
   │                                 │ issue_otp(citizen_id, phone)         │
   │                                 │  ├─ MOCK_OTP=1 → skip Twilio         │
   │                                 │  └─ else → twilio.verifications.create
   │                                 │ insert otp_challenges row            │
   │  {challenge_id, phone_hint}    ◄│                                     │
   │◄────────────────────────────────│                                     │
   │                                 │                                     │
   │  POST /auth/otp {chal, code}    │                                     │
   │────────────────────────────────►│ verify_otp_and_consume               │
   │                                 │  ├─ MOCK_OTP=1 → require "123456"    │
   │                                 │  └─ else → twilio.verification_checks│
   │                                 │ UPDATE otp_challenges SET consumed=t │
   │                                 │ mint_access_token(citizen_id)        │
   │  {access_token, citizen_id}     │                                     │
   │◄────────────────────────────────│                                     │
   │                                 │                                     │
   │  localStorage.set(session)      │                                     │
```

## Two entry forms

- **ROeID mock** (`POST /auth/login-roeid {persona_id}`) — hackathon shortcut. Maps `maria-ionescu` / `andrei-popa` / `elena-dumitru` to a hardcoded CNP, then to a seeded citizen row.
- **MRZ** (`POST /auth/login-mrz {cnp, nume, prenume}`) — citizens scan/paste their ID card MRZ; the frontend extracts `cnp, nume, prenume` and posts. Backend looks up by all three fields (case-insensitive on names) — defends against typos AND lookup-by-CNP-alone harvesting.

Both paths return the same `ChallengeResponse {challenge_id, phone_hint}`.

## Why `phone_hint` not `phone`

The full phone is private; the hint `***1234` is enough for the user to recognize "yes, that's my phone" without exposing the full number on screen.

## OTP storage

`otp_challenges` is a tiny table:

```
id TEXT PK              -- "ch_..."
citizen_id UUID FK
phone TEXT
twilio_sid TEXT NULL    -- only when MOCK_OTP=0
expires_at TIMESTAMPTZ  -- 5 min default
consumed BOOLEAN        -- prevents replay
```

The verify step uses `SELECT ... FOR UPDATE` so two concurrent OTP submissions don't both succeed.

## Frontend post-OTP

`api.otp(...)` returns `{access_token, citizen_id}`. The FE writes `{access_token, citizen_id}` to `localStorage` under `civicai:session`. Every subsequent `request()` in `lib/api.ts` reads it and attaches `Authorization: Bearer <token>`.

## See also

- [[auth]] — code
- [[security]] — JWT minting
- [[Frontend Auth Flow]]
- [[ADR Mock OTP Flag]]
