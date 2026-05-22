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
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_pg_connection() -> psycopg.Connection[dict[str, Any]]:
    settings = get_settings()
    return psycopg.connect(settings.supabase_db_url, row_factory=dict_row)
