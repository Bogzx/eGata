"""FastAPI app entrypoint."""
from __future__ import annotations

import logging
import logging.config
import os
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response


def _configure_logging() -> None:
    """Wire app loggers to stderr so Docker captures every line.

    Why this is its own block: uvicorn sets up its own root logger when it
    boots, which by default leaves our `logging.getLogger("agent")` etc.
    handler-less. Without an explicit dictConfig, every log.info on the AI
    path is silently dropped and you can't diagnose anything from
    `docker logs`. Set LOG_LEVEL=DEBUG to see per-audio-chunk traces.
    """
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    redact = os.environ.get("LOG_REDACT_PII", "1") != "0"
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"pii": {"()": "app.log_redaction.PiiRedactingFilter"}},
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
                    # CNP / e-mail / phone never reach the log sink.
                    "filters": ["pii"] if redact else [],
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
from app.config import get_settings, insecure_settings_warnings
from app.demo import router as demo_router
from app.documents import router as documents_router
from app.files import router as files_router
from app.health import router as health_router
from app.pdf import PdfRenderError, PdfRendererUnavailable
from app.procedures import router as procedures_router
from app.reminders import router as reminders_router
from app.scenarios import router as scenarios_router
from app.twilio_bridge import router as twilio_router
from app.worker import init_worker, shutdown_worker

log = logging.getLogger(__name__)
log.info("logging configured level=%s", os.environ.get("LOG_LEVEL", "INFO").upper())
settings = get_settings()
for _warning in insecure_settings_warnings(settings):
    log.warning("INSECURE CONFIG: %s", _warning)


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


def _check_ledger_setup() -> None:
    """Load (or, in dev, generate) the signing key, sign any history written
    before migrations/014, and say so if the backend connects with rights
    that could bypass the ledger's protections."""
    from app.db import get_pg_connection
    from app.ledger import sign_unsigned_rows
    from app.ledger_signing import signing_key

    key = signing_key()
    log.info("ledger signing key %s (source: %s)", key.key_id, key.source)
    try:
        signed = sign_unsigned_rows()
        if signed:
            log.warning("ledger: signed %d rows written before signing existed", signed)
        with get_pg_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "select current_user as me, "
                "(select rolsuper from pg_roles where rolname = current_user) as su, "
                "(select tableowner from pg_tables where tablename = 'ledger') as owner;"
            )
            row = cur.fetchone()
        if row and (row["su"] or row["me"] == row["owner"]):
            log.warning(
                "INSECURE CONFIG: the backend connects to Postgres as %s (%s). That role "
                "can drop the ledger's append-only triggers. Connect as egata_app "
                "(README: 'Upgrading an existing database').",
                row["me"], "superuser" if row["su"] else "owner of ledger",
            )
    except Exception:
        log.exception("ledger startup checks failed (database unreachable?)")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    _check_ledger_setup()
    init_worker()
    try:
        yield
    finally:
        shutdown_worker()


app = FastAPI(
    title="eGata",
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
async def _log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
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

@app.exception_handler(PdfRenderError)
async def _pdf_render_error(_: Request, exc: PdfRenderError) -> JSONResponse:
    """A failed render is the server's problem, and its detail is PII-free by
    construction (see app.pdf.PdfRenderError) — say so instead of a bare 500."""
    status = 503 if isinstance(exc, PdfRendererUnavailable) else 500
    return JSONResponse(status_code=status, content={"detail": str(exc)})


app.include_router(auth_router)
app.include_router(citizens_router)
app.include_router(procedures_router)
app.include_router(scenarios_router)
app.include_router(documents_router)
app.include_router(files_router)
app.include_router(agent_router)
app.include_router(agent_voice_router)
app.include_router(reminders_router)
app.include_router(twilio_router)
app.include_router(demo_router)
app.include_router(health_router)


@app.get("/.well-known/egata-ledger-keys.json")
def ledger_keys() -> dict[str, object]:
    """Public keys that sign the audit ledger (no auth: they are public).

    Compare the key_id with a copy obtained elsewhere (a README, a printed
    notice at the counter) — a key fetched from the same server that signs is
    only trust-on-first-use.
    """
    from app.ledger_signing import STATEMENT_TYPE, STATEMENT_VERSION, published_keys

    return {
        "algorithm": "Ed25519",
        "statement": {
            "v": STATEMENT_VERSION,
            "type": STATEMENT_TYPE,
            "fields": ["v", "type", "key_id", "citizen_id", "document_id", "row_id", "row_hash"],
            "encoding": "canonical JSON (sorted keys, no whitespace, UTF-8)",
        },
        "keys": published_keys(),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "egata-backend"}
