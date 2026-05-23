---
type: module
path: "backend/app/config.py"
status: active
language: python
purpose: "Pydantic Settings — all env vars in one place."
depends_on: []
used_by: [main, db, auth, security, embeddings, documents, ledger, agent, agent_voice, twilio_bridge, demo, health, storage]
created: 2026-05-23
updated: 2026-05-23
---

# config

Single Pydantic `BaseSettings` class. Read via `get_settings()` which is `lru_cache(maxsize=1)` — a settings instance is created once per process.

## Settings groups

| Group | Vars | Purpose |
|---|---|---|
| Supabase | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL` | DB + storage + auth metadata |
| Twilio | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_VERIFY_SERVICE_SID`, `TWILIO_PHONE_NUMBER`, `MOCK_OTP` | OTP delivery + phone bridge |
| Gemini | `GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-2.5-flash`), `GEMINI_VOICE_MODEL` (default `gemini-3.1-flash-live-preview`), `GEMINI_VOICE_NAME` (default `Aoede`) | LLM + embeddings + Live voice |
| JWT | `JWT_SIGNING_SECRET`, `JWT_ALGORITHM` (HS256), `JWT_EXPIRES_SECONDS` (86400), `JWT_AUDIENCE`, `JWT_ISSUER` | Bearer auth |
| HTTP | `ALLOW_ORIGINS` (csv), `PUBLIC_BASE_URL`, `TWILIO_BRIDGE_PUBLIC_URL` | CORS + Twilio TwiML |
| Ledger | `LEDGER_GENESIS_HASH` | Hash chain root |

## Gotchas

> [!gotcha] `allow_origins` is csv, not a list
> Pydantic Settings reads it as a string; [[main]] splits on `,` and trims. `ALLOW_ORIGINS=*` works but `allow_credentials=True` is incompatible — see comment in `config.py:45`.

> [!gotcha] `MOCK_OTP` doubles as the "skip Twilio costs" flag
> [[documents]]`.send_delivery_sms` and [[auth]] both check it. In production this MUST be 0.

## See also

- [[Deployment Railway]] — which vars need to be set in Railway's dashboard
- [[ADR Mock OTP Flag]] — why we have a mock-mode switch
