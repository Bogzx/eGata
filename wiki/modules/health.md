---
type: module
path: "backend/app/health.py"
status: active
language: python
purpose: "Liveness + dependency check endpoints."
depends_on: [config, db]
used_by: [Railway healthcheck (/health on main), monitoring]
created: 2026-05-23
updated: 2026-05-23
---

# health

Two endpoints:

| Route | Behavior |
|---|---|
| `GET /health` | Defined in [[main]] (not this file). Returns `{"status":"ok","service":"civicai-backend"}` always. Used by Railway healthcheck. |
| `GET /healthz` | Defined here. **Always returns 200** so probes succeed; the body's `ok` flag is the real signal. |

## `/healthz` checks

```json
{
  "ok": true,
  "checks": {
    "supabase": true,    // psycopg connect + "select 1;"
    "gemini_key": true,  // settings.gemini_api_key is non-empty
    "twilio_token": true // settings.twilio_auth_token is non-empty
  }
}
```

`ok` is `all(checks.values())`. The endpoint reads from `Settings` (which honors `.env` via pydantic-settings), not raw `os.environ`, so the check doesn't lie when only `.env` is set.

## Why two endpoints

`/health` is **always-200** for Railway's restart logic — we don't want a Gemini quota issue to restart the dyno. `/healthz` is the **truth** view for human/dashboard checks.
