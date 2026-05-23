"""/healthz endpoint (Plan 4) — reports Supabase, Gemini, Twilio status.

Always returns 200 so Railway healthchecks succeed; the body's `ok` flag is
True only when every dependency is reachable / configured.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from app.config import get_settings
from app.db import get_pg_connection

log = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


def _check_supabase() -> bool:
    try:
        with get_pg_connection() as conn, conn.cursor() as cur:
            cur.execute("select 1;")
            cur.fetchone()
        return True
    except Exception:
        log.exception("supabase healthcheck failed")
        return False


@router.get("/healthz")
def healthz() -> dict[str, object]:
    # Read from Settings (which honors .env via pydantic-settings) rather than
    # raw os.environ so the check doesn't lie when only .env is set.
    settings = get_settings()
    checks = {
        "supabase": _check_supabase(),
        "gemini_key": bool(settings.gemini_api_key),
        "twilio_token": bool(settings.twilio_auth_token),
    }
    return {"ok": all(checks.values()), "checks": checks}
