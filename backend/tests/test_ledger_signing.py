"""Key handling for the ledger signatures (app/ledger_signing.py)."""
from __future__ import annotations

import base64
import logging
import stat
from pathlib import Path

import pytest

from app import ledger_signing
from app.config import get_settings


@pytest.fixture
def fresh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LEDGER_SIGNING_KEY", raising=False)
    monkeypatch.setenv("LEDGER_SIGNING_KEY_FILE", str(tmp_path / "keys" / "ledger.pem"))
    get_settings.cache_clear()
    ledger_signing.signing_key.cache_clear()
    yield tmp_path / "keys" / "ledger.pem"
    get_settings.cache_clear()
    ledger_signing.signing_key.cache_clear()


def test_first_run_generates_a_private_key_file_and_warns(
    fresh: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # app.* loggers do not propagate once app.main configured logging, so
    # listen on the module's logger itself.
    logger = logging.getLogger(ledger_signing.__name__)
    logger.addHandler(caplog.handler)
    try:
        key = ledger_signing.signing_key()
    finally:
        logger.removeHandler(caplog.handler)
    assert key.source == "generated"
    assert fresh.is_file()
    assert stat.S_IMODE(fresh.stat().st_mode) == 0o600
    assert "LEDGER SIGNING KEY GENERATED" in caplog.text

    ledger_signing.signing_key.cache_clear()
    again = ledger_signing.signing_key()
    assert again.source == "file" and again.key_id == key.key_id


def test_env_key_wins_and_accepts_pem(fresh: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger_signing.signing_key()  # writes a file key
    pem = fresh.read_text()
    ledger_signing.signing_key.cache_clear()
    monkeypatch.setenv("LEDGER_SIGNING_KEY", pem)
    get_settings.cache_clear()
    assert ledger_signing.signing_key().source == "env"


def test_bad_env_key_fails_loudly(fresh: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGER_SIGNING_KEY", base64.b64encode(b"short").decode())
    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        ledger_signing.signing_key()


def test_retired_keys_are_published(fresh: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = base64.b64encode(bytes(range(32))).decode()
    monkeypatch.setenv("LEDGER_RETIRED_PUBLIC_KEYS", f"{old}, not-a-key==")
    get_settings.cache_clear()
    keys = ledger_signing.published_keys()
    assert [k["status"] for k in keys] == ["current", "retired"]
    assert keys[1]["key_id"] == ledger_signing.key_id_for(bytes(range(32)))
