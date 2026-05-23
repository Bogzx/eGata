"""Live smoke test against a deployed Railway URL.

Skipped unless SMOKE_BASE_URL is set. Run manually after deploy:
    SMOKE_BASE_URL=https://egata.up.railway.app pytest tests/test_smoke_deployed.py -v
"""
from __future__ import annotations

import os

import httpx
import pytest


@pytest.fixture(scope="module")
def base_url() -> str:
    url = os.environ.get("SMOKE_BASE_URL")
    if not url:
        pytest.skip("SMOKE_BASE_URL not set; skipping live smoke test")
    return url.rstrip("/")


def test_health(base_url: str) -> None:
    resp = httpx.get(f"{base_url}/health", timeout=10)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_openapi_schema_lists_required_endpoints(base_url: str) -> None:
    resp = httpx.get(f"{base_url}/openapi.json", timeout=10)
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    for expected in (
        "/auth/login-roeid", "/auth/login-mrz", "/auth/otp",
        "/citizens/me",
        "/procedures", "/procedures/lookup",
        "/documents",
        "/agent/chat",
    ):
        assert any(p.startswith(expected) for p in paths), f"missing path {expected}"


def test_login_default_persona_round_trip(base_url: str) -> None:
    r = httpx.post(f"{base_url}/auth/login-roeid", json={}, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "challenge_id" in body
    assert body["phone_hint"].startswith("***")
