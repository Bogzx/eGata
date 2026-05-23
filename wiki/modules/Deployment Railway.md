---
type: module
path: "backend/railway.json + Dockerfile + Procfile"
status: active
created: 2026-05-23
updated: 2026-05-23
---

# Deployment Railway

Backend ships to Railway (or any Docker host). The Dockerfile builds an image with Python 3.12 + texlive; Railway runs uvicorn.

## railway.json

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": { "builder": "DOCKERFILE", "dockerfilePath": "Dockerfile" },
  "deploy": {
    "startCommand": "sh -c \"uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}\"",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

Healthcheck hits `/health` which is the **always-200** version (not `/healthz`). Railway must not restart on Gemini-quota issues.

## Procfile (Heroku-compat fallback)

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Same command, different runner. Used if you deploy to Heroku or any Procfile-aware platform.

## Env vars required

See [[config]] for the full list. Copy `.env.example` and set each:

| Required | Notes |
|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL` | Backend uses service role |
| `GEMINI_API_KEY` | From Google AI Studio |
| `JWT_SIGNING_SECRET` | `openssl rand -hex 32` |
| `ALLOW_ORIGINS` | Comma-separated origin list; NEVER `*` with credentials |
| `LEDGER_GENESIS_HASH` | Don't change between runs of the same DB |

| Optional |
|---|
| `TWILIO_*` (when `MOCK_OTP=0`) |
| `TWILIO_BRIDGE_PUBLIC_URL` (wss://...; required for phone bridge) |
| `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `APP_ENV` |
| `DEMO_RESET_TOKEN` (for `/demo/reset`) |
| `MOCK_OTP=0` for production |

## First-deploy checklist

1. Create Supabase project (EU region) → fill SUPABASE_* envs.
2. `python backend/scripts/apply_migrations.py` (locally against the prod DB).
3. `python backend/scripts/embed_procedures.py`.
4. `python backend/scripts/index_rag.py`.
5. Set all Railway env vars.
6. `railway up` (or `git push` if you've linked GitHub).
7. Smoke test: `curl https://<your>.up.railway.app/health` → `{"status":"ok",...}`.
8. Phone (if used): set Twilio voice webhook to `POST https://<your>.up.railway.app/voice/twilio/webhook` and `TWILIO_BRIDGE_PUBLIC_URL` to `wss://<your>.up.railway.app/voice/twilio`.

## Smoke commands

```bash
curl https://<host>/health
curl https://<host>/healthz | jq .
curl -H "X-Demo-Token: $DEMO_RESET_TOKEN" -d '{}' https://<host>/demo/reset
```

## See also

- [[Dockerfile]]
- [[Migrations]]
- [[health]]
- backend/RUNBOOK.md
