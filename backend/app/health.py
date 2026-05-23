"""/healthz endpoint (Plan 4) — reports Supabase, Gemini, Twilio status.

Always returns 200 so Railway healthchecks succeed; the body's `ok` flag is
True only when every dependency is reachable / configured.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter

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
    checks = {
        "supabase": _check_supabase(),
        "gemini_key": bool(os.environ.get("GEMINI_API_KEY")),
        "twilio_token": bool(os.environ.get("TWILIO_AUTH_TOKEN")),
    }
    return {"ok": all(checks.values()), "checks": checks}
