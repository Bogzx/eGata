"""The reference text for delivery "send" reports what happened.

"sent" only when Twilio accepted it; "not_configured" when this server has
no SMS (MOCK_OTP, or no Twilio account); "failed" when Twilio, or the phone
lookup, raised. The citizen is told which (offline agent, DonePane), so a
rejected SMS must not read as "not configured".
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.config import get_settings
from app.documents import text_reference_to_citizen


@pytest.fixture
def twilio(monkeypatch: pytest.MonkeyPatch) -> Any:
    """A configured Twilio account whose client the test controls."""
    monkeypatch.setenv("MOCK_OTP", "0")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+40700000000")
    get_settings.cache_clear()
    monkeypatch.setattr("app.documents.fetch_phone_for_citizen", lambda _cid: "+40712345678")
    sent: list[dict[str, Any]] = []

    class Messages:
        error: Exception | None = None

        def create(self, **kw: Any) -> None:
            if Messages.error is not None:
                raise Messages.error
            sent.append(kw)

    class Client:
        def __init__(self, *_a: Any) -> None:
            self.messages = Messages()

    monkeypatch.setattr("app.documents.TwilioClient", Client)
    yield Messages, sent
    get_settings.cache_clear()


def test_sent_when_twilio_accepts(twilio: Any) -> None:
    _messages, sent = twilio
    assert text_reference_to_citizen(uuid4(), "CV-1111-2222") == "sent"
    assert len(sent) == 1 and "CV-1111-2222" in sent[0]["body"]
    assert "trimis" not in sent[0]["body"]  # never claims it was filed


def test_failed_when_twilio_rejects(twilio: Any) -> None:
    messages, sent = twilio
    messages.error = RuntimeError("21211 invalid 'To' phone number")
    assert text_reference_to_citizen(uuid4(), "CV-1111-2222") == "failed"
    assert sent == []


def test_failed_when_the_phone_lookup_raises(twilio: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_row(_cid: Any) -> str:
        raise LookupError("citizen not found")

    monkeypatch.setattr("app.documents.fetch_phone_for_citizen", no_row)
    assert text_reference_to_citizen(uuid4(), "CV-1111-2222") == "failed"


def test_not_configured_under_mock_otp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_OTP", "1")
    get_settings.cache_clear()
    monkeypatch.setattr("app.documents.fetch_phone_for_citizen", lambda _cid: "+40712345678")
    try:
        assert text_reference_to_citizen(uuid4(), "CV-1111-2222") == "not_configured"
    finally:
        get_settings.cache_clear()


def test_not_configured_without_a_twilio_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_OTP", "0")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "")
    get_settings.cache_clear()
    monkeypatch.setattr("app.documents.fetch_phone_for_citizen", lambda _cid: "+40712345678")
    try:
        assert text_reference_to_citizen(uuid4(), "CV-1111-2222") == "not_configured"
    finally:
        get_settings.cache_clear()
