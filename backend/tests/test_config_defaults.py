"""Settings must fail closed and must not carry anyone's personal resources.

conftest.py sets MOCK_OTP=1 for the suite, so these instantiate Settings with
the relevant variables removed rather than reading the ambient config.
"""
from __future__ import annotations

import pytest

from app.config import Settings

REQUIRED = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_ANON_KEY": "x",
    "SUPABASE_SERVICE_ROLE_KEY": "x",
    "SUPABASE_DB_URL": "postgresql://localhost/x",
    "JWT_SIGNING_SECRET": "x",
}


def _settings_without(monkeypatch: pytest.MonkeyPatch, *unset: str) -> Settings:
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key, value)
    for key in unset:
        monkeypatch.delenv(key, raising=False)
    # Ignore any .env sitting in the working tree.
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_mock_otp_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """With MOCK_OTP on, /auth/login-roeid issues a challenge to anyone naming
    a persona and /auth/otp accepts the literal code 123456 — anyone can log
    in as anyone. A deploy that forgets the variable must not be open."""
    settings = _settings_without(monkeypatch, "MOCK_OTP")
    assert settings.mock_otp is False


def test_mock_otp_can_be_turned_on_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("MOCK_OTP", "1")
    assert Settings(_env_file=None).mock_otp is True  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "field",
    ["azure_openai_endpoint", "azure_voicelive_endpoint"],
)
def test_azure_endpoints_have_no_baked_in_resource(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    """A personal resource name as the default leaks a tenant and silently
    routes a stranger's traffic at someone else's endpoint instead of
    failing loudly."""
    settings = _settings_without(
        monkeypatch, "AZURE_OPENAI_ENDPOINT", "AZURE_VOICELIVE_ENDPOINT"
    )
    assert getattr(settings, field) == ""


def test_demo_grade_settings_are_flagged() -> None:
    from app.config import Settings, insecure_settings_warnings

    demo = Settings(
        supabase_db_url="postgresql://x",
        jwt_signing_secret="dev-only-not-a-secret",
        mock_otp=True,
        allow_origins="*",
    )
    assert len(insecure_settings_warnings(demo)) == 3

    real = Settings(
        supabase_db_url="postgresql://x",
        jwt_signing_secret="a" * 64,
        mock_otp=False,
        allow_origins="https://cluj-hackathon.vercel.app",
    )
    assert insecure_settings_warnings(real) == []


def test_auto_agent_with_endpoint_but_no_key_is_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import backend_choice_warnings, resolved_agent_backend

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    s = _settings_without(monkeypatch, "AZURE_OPENAI_API_KEY", "AGENT_BACKEND")
    assert resolved_agent_backend(s) == "offline"
    assert any("OFFLINE" in w for w in backend_choice_warnings(s))

    monkeypatch.setenv("AGENT_BACKEND", "offline")  # deliberate: no warning
    assert backend_choice_warnings(_settings_without(monkeypatch, "AZURE_OPENAI_API_KEY")) == []

    monkeypatch.delenv("AGENT_BACKEND")
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT")  # keyless demo stack: no warning
    assert backend_choice_warnings(_settings_without(monkeypatch, "AZURE_OPENAI_API_KEY")) == []
