---
type: module
path: "backend/app/main.py"
status: active
language: python
purpose: "FastAPI entrypoint — assembles routers, CORS, lifespan, Sentry."
depends_on: [config, auth, citizens, procedures, scenarios, documents, agent, agent_voice, reminders, twilio_bridge, demo, health, worker]
used_by: [Procfile, Dockerfile, railway.json]
created: 2026-05-23
updated: 2026-05-23
---

# main

App entrypoint. Imports every router and registers them on a single FastAPI instance. Lifespan starts and stops the in-process [[worker]].

## What it does

1. Reads [[config]] settings.
2. Initializes Sentry **only if** `SENTRY_DSN` is set in the env — keeps the import optional so missing the dep doesn't crash the app.
3. Builds `FastAPI(title="CivicAI", version="0.1.0", lifespan=lifespan)`.
4. Adds CORS middleware. **`allow_origins` is a comma-separated list from `ALLOW_ORIGINS`**, never a wildcard with `allow_credentials=True` because Chrome refuses that combo (see [[config]]).
5. Includes 10 routers in this order:

   `auth → citizens → procedures → scenarios → documents → agent → agent_voice → reminders → twilio → demo → health`

6. Adds a top-level `GET /health` that returns `{"status":"ok","service":"civicai-backend"}` — Railway's healthcheck hits this.

## Lifespan

`@asynccontextmanager async def lifespan` calls `init_worker()` on startup and `shutdown_worker()` on shutdown. See [[worker]].

## Why every router lives in its own module

Easier to track which router owns which routes and to spin up isolated tests with `TestClient(app.include_router(only_one))`. Also lets [[agent]] and [[agent_voice]] keep separate prefixes (`/agent/chat*` vs `/agent/voice/*`) even though they share infrastructure.

## See also

- [[HTTP API Surface]] — every route this module exposes
- [[Deployment Railway]] — `Procfile` and `railway.json` launch `uvicorn app.main:app`
