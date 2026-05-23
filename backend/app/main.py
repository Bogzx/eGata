"""FastAPI app entrypoint."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent import router as agent_router
from app.agent_voice import router as agent_voice_router
from app.auth import router as auth_router
from app.citizens import router as citizens_router
from app.config import get_settings
from app.demo import router as demo_router
from app.documents import router as documents_router
from app.health import router as health_router
from app.procedures import router as procedures_router
from app.scenarios import router as scenarios_router
from app.reminders import router as reminders_router
from app.twilio_bridge import router as twilio_router
from app.worker import init_worker, shutdown_worker

log = logging.getLogger(__name__)
settings = get_settings()


# Sentry init (Plan 4). Guarded by SENTRY_DSN so missing dep is a no-op.
_SENTRY_DSN = os.environ.get("SENTRY_DSN")
if _SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            environment=os.environ.get("APP_ENV", "production"),
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            integrations=[FastApiIntegration()],
            send_default_pii=False,
        )
        log.info("Sentry initialized for backend")
    except ImportError:
        log.warning("sentry-sdk not installed — error reporting disabled")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_worker()
    try:
        yield
    finally:
        shutdown_worker()


app = FastAPI(
    title="CivicAI",
    description="Civic AI agent for Romanian primărie procedures",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allow_origins.split(",")] or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(citizens_router)
app.include_router(procedures_router)
app.include_router(scenarios_router)
app.include_router(documents_router)
app.include_router(agent_router)
app.include_router(agent_voice_router)
app.include_router(reminders_router)
app.include_router(twilio_router)
app.include_router(demo_router)
app.include_router(health_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "civicai-backend"}
