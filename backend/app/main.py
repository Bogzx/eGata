"""FastAPI app entrypoint."""
from __future__ import annotations

import logging
import logging.config
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware


def _configure_logging() -> None:
    """Wire app loggers to stderr so Docker captures every line.

    Why this is its own block: uvicorn sets up its own root logger when it
    boots, which by default leaves our `logging.getLogger("agent")` etc.
    handler-less. Without an explicit dictConfig, every log.info on the AI
    path is silently dropped and you can't diagnose anything from
    `docker logs`. Set LOG_LEVEL=DEBUG to see per-audio-chunk traces.
    """
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
                    "datefmt": "%H:%M:%S",
                },
            },
            "handlers": {
                "stderr": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                    "formatter": "default",
                },
            },
            "loggers": {
                # All `app.*` loggers (anything using __name__) inherit here.
                "app": {"level": level, "handlers": ["stderr"], "propagate": False},
                # Loggers that use explicit names instead of __name__:
                "agent": {"level": level, "handlers": ["stderr"], "propagate": False},
                "agent_voice": {"level": level, "handlers": ["stderr"], "propagate": False},
                "agent_tools": {"level": level, "handlers": ["stderr"], "propagate": False},
                "session_engine": {"level": level, "handlers": ["stderr"], "propagate": False},
                "twilio_bridge": {"level": level, "handlers": ["stderr"], "propagate": False},
                "complete_document": {"level": level, "handlers": ["stderr"], "propagate": False},
                "auth": {"level": level, "handlers": ["stderr"], "propagate": False},
                # Quiet noisy third-party loggers (they propagate to root → stderr otherwise).
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
                "h2": {"level": "WARNING"},
                "hpack": {"level": "WARNING"},
                "websockets": {"level": "INFO"},
            },
        }
    )


_configure_logging()

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
log.info("logging configured level=%s", os.environ.get("LOG_LEVEL", "INFO").upper())
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


@app.middleware("http")
async def _log_requests(request: Request, call_next):
    """Log every HTTP request with method, path, status, duration, and a
    short request-id so chat turns can be correlated across log lines.

    Skips /healthz to avoid spamming the logs with Railway's healthcheck
    poll (~every 30s). Everything else is fair game.
    """
    if request.url.path == "/healthz":
        return await call_next(request)
    req_id = uuid.uuid4().hex[:6]
    start = time.perf_counter()
    client_host = request.client.host if request.client else "-"
    log.info(
        "http: req=%s %s %s from=%s",
        req_id,
        request.method,
        request.url.path,
        client_host,
    )
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log.exception(
            "http: req=%s %s %s CRASHED after %.0fms",
            req_id,
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000
    log.info(
        "http: req=%s %s %s -> %s in %.0fms",
        req_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    # Surface the request id back to the client so they can quote it in
    # bug reports / docker logs greps.
    response.headers["x-request-id"] = req_id
    return response

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
