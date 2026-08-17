"""Supabase + Postgres client wrappers."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import psycopg
from psycopg.rows import dict_row
from supabase import Client, create_client

from app.config import get_settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "Supabase client requested but SUPABASE_URL / "
            "SUPABASE_SERVICE_ROLE_KEY are not set. Either configure a "
            "Supabase project or set STORAGE_BACKEND=local (the default when "
            "no project is configured) to keep PDFs on a local volume."
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_pg_connection() -> psycopg.Connection[dict[str, Any]]:
    settings = get_settings()
    return psycopg.connect(settings.supabase_db_url, row_factory=dict_row)
