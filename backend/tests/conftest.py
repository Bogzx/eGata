"""Shared pytest fixtures."""
from __future__ import annotations

import os

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-azure-openai")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_VOICELIVE_API_KEY", "test-azure-voicelive")
os.environ.setdefault("AZURE_VOICELIVE_ENDPOINT", "https://test.services.ai.azure.com/")
os.environ.setdefault("JWT_SIGNING_SECRET", "test-secret")
os.environ.setdefault("MOCK_OTP", "1")
# Unit tests run without Postgres; the *_postgres suites turn this back on.
os.environ.setdefault("DISTRIBUTED_LOCKS", "0")
# Fixed Ed25519 seed so tests never write a generated key to ./.data.
os.environ.setdefault("LEDGER_SIGNING_KEY", "ZWdhdGEtdGVzdC1sZWRnZXItc2lnbmluZy1rZXktMzI=")
