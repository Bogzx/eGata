"""The local storage backend must give the same guarantees as the Supabase one.

It exists so `docker compose up` works with no Supabase project. That makes it
the backend a stranger actually runs, so its links have to expire, resist
tampering, and refuse to walk out of the storage root.
"""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.config import Settings, get_settings
from app.main import app

OBJECT = "11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.pdf"
PDF = b"%PDF-1.4 local"


@pytest.fixture
def local_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Point storage at a temp dir and force the local backend."""
    base = get_settings()
    settings = base.model_copy(
        update={
            "storage_backend": "local",
            "pdf_storage_dir": str(tmp_path / "pdfs"),
            "public_base_url": "http://localhost:8000",
            "jwt_signing_secret": "test-secret",
        }
    )
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
    import app.files as files_mod

    monkeypatch.setattr(files_mod, "active_backend", lambda: "local")
    return settings


def _params(url: str) -> dict[str, str]:
    q = parse_qs(urlparse(url).query)
    return {k: v[0] for k, v in q.items()}


def test_backend_auto_selects_local_without_a_supabase_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = get_settings()
    monkeypatch.setattr(
        storage,
        "get_settings",
        lambda: base.model_copy(
            update={"storage_backend": "auto", "supabase_url": "", "supabase_service_role_key": ""}
        ),
    )
    assert storage.active_backend() == "local"


def test_backend_auto_selects_supabase_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = get_settings()
    monkeypatch.setattr(
        storage,
        "get_settings",
        lambda: base.model_copy(
            update={
                "storage_backend": "auto",
                "supabase_url": "https://x.supabase.co",
                "supabase_service_role_key": "k",
            }
        ),
    )
    assert storage.active_backend() == "supabase"


def test_unknown_backend_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    base = get_settings()
    monkeypatch.setattr(
        storage, "get_settings", lambda: base.model_copy(update={"storage_backend": "s3"})
    )
    with pytest.raises(RuntimeError, match="not one of"):
        storage.active_backend()


def test_upload_then_read_round_trips(local_backend: Settings) -> None:
    assert storage.upload_pdf_to_storage(OBJECT, PDF) == OBJECT
    assert storage.read_local_pdf(OBJECT) == PDF


def test_signed_url_is_fetchable_and_returns_the_pdf(local_backend: Settings) -> None:
    storage.upload_pdf_to_storage(OBJECT, PDF)
    url = storage.create_signed_pdf_url(OBJECT)
    assert url is not None and url.startswith("http://localhost:8000/files/pdf/")

    client = TestClient(app)
    res = client.get(urlparse(url).path, params=_params(url))
    assert res.status_code == 200
    assert res.content == PDF
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["cache-control"] == "private, no-store"


def test_tampered_signature_is_refused(local_backend: Settings) -> None:
    storage.upload_pdf_to_storage(OBJECT, PDF)
    url = storage.create_signed_pdf_url(OBJECT)
    assert url is not None
    params = _params(url)
    params["sig"] = "0" * 64

    res = TestClient(app).get(urlparse(url).path, params=params)
    assert res.status_code == 403


def test_extended_expiry_is_refused(local_backend: Settings) -> None:
    """The expiry is inside the HMAC, so pushing it out invalidates the link."""
    storage.upload_pdf_to_storage(OBJECT, PDF)
    url = storage.create_signed_pdf_url(OBJECT)
    assert url is not None
    params = _params(url)
    params["exp"] = str(int(params["exp"]) + 86400)

    res = TestClient(app).get(urlparse(url).path, params=params)
    assert res.status_code == 403


def test_expired_link_is_refused(local_backend: Settings) -> None:
    storage.upload_pdf_to_storage(OBJECT, PDF)
    url = storage.create_signed_pdf_url(OBJECT, expires_in=-1)
    assert url is not None

    res = TestClient(app).get(urlparse(url).path, params=_params(url))
    assert res.status_code == 403


def test_signature_of_one_object_does_not_open_another(local_backend: Settings) -> None:
    """The object path is inside the HMAC, so a link to your own document
    cannot be edited into a link to someone else's."""
    other = "33333333-3333-3333-3333-333333333333/44444444-4444-4444-4444-444444444444.pdf"
    storage.upload_pdf_to_storage(OBJECT, PDF)
    storage.upload_pdf_to_storage(other, b"%PDF-1.4 someone else")

    url = storage.create_signed_pdf_url(OBJECT)
    assert url is not None
    victim_path = "/files/pdf/" + other

    res = TestClient(app).get(victim_path, params=_params(url))
    assert res.status_code == 403


def test_missing_file_is_indistinguishable_from_a_bad_link(
    local_backend: Settings,
) -> None:
    """A 404 here would confirm which document IDs exist to someone holding a
    stale link."""
    url = storage.create_signed_pdf_url(OBJECT)  # never uploaded
    assert url is not None

    res = TestClient(app).get(urlparse(url).path, params=_params(url))
    assert res.status_code == 403


def test_traversal_out_of_the_storage_root_is_refused(local_backend: Settings) -> None:
    with pytest.raises(ValueError, match="escapes the storage root"):
        storage.read_local_pdf("../../etc/passwd")


def test_batch_signing_works_locally(local_backend: Settings) -> None:
    paths = [f"cit/doc{i}.pdf" for i in range(3)]
    out = storage.create_signed_pdf_urls(paths)
    assert set(out) == set(paths)
    for url in out.values():
        assert "sig=" in url and "exp=" in url


def test_ttl_is_bounded(local_backend: Settings) -> None:
    url = storage.create_signed_pdf_url(OBJECT)
    assert url is not None
    exp = int(_params(url)["exp"])
    assert 0 < exp - int(time.time()) <= storage.SIGNED_URL_TTL_SECONDS + 2


def test_route_is_inert_under_the_supabase_backend(
    local_backend: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Supabase signs its own URLs; this route must not become a second,
    differently-authorized way in."""
    storage.upload_pdf_to_storage(OBJECT, PDF)
    url = storage.create_signed_pdf_url(OBJECT)
    assert url is not None

    import app.files as files_mod

    monkeypatch.setattr(files_mod, "active_backend", lambda: "supabase")
    res = TestClient(app).get(urlparse(url).path, params=_params(url))
    assert res.status_code == 404
