"""Shared pytest fixtures."""
from __future__ import annotations

import os

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault("OPENAI_API_KEY", "test-openai")
os.environ.setdefault("JWT_SIGNING_SECRET", "test-secret")
os.environ.setdefault("MOCK_OTP", "1")
os.environ.setdefault("LEDGER_GENESIS_HASH", "0x" + "0" * 64)
