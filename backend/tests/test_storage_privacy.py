"""Identity PDFs must not be reachable without a time-limited credential.

The bucket held completed primărie forms — full name, CNP, home address —
created with `public: True` and handed out as `get_public_url` links that
never expired. These tests pin the three properties that fixed it, against a
fake Supabase client so no network is involved.
"""
from __future__ import annotations

from typing import Any

import pytest

from app import storage


class FakeBucketAPI:
    def __init__(self, parent: FakeSupabaseStorage) -> None:
        self.parent = parent

    def upload(self, path: str, file: bytes, file_options: dict[str, str]) -> dict:
        self.parent.uploaded[path] = file
        return {"path": path}

    def get_public_url(self, path: str) -> str:  # pragma: no cover - must not be called
        raise AssertionError(
            "get_public_url was called: identity PDFs would be world-readable"
        )

    def create_signed_url(self, path: str, expires_in: int) -> dict[str, Any]:
        self.parent.signed.append((path, expires_in))
        return {"signedURL": f"https://sb/storage/{path}?token=sig&exp={expires_in}"}

    def create_signed_urls(
        self, paths: list[str], expires_in: int
    ) -> list[dict[str, Any]]:
        self.parent.batch_calls += 1
        for p in paths:
            self.parent.signed.append((p, expires_in))
        return [
            {
                "path": p,
                "signedURL": f"https://sb/storage/{p}?token=sig&exp={expires_in}",
                "error": None,
            }
            for p in paths
        ]


class FakeSupabaseStorage:
    def __init__(self) -> None:
        self.created_buckets: list[tuple[str, dict[str, Any]]] = []
        self.uploaded: dict[str, bytes] = {}
        self.signed: list[tuple[str, int]] = []
        self.batch_calls = 0

    def create_bucket(self, name: str, options: dict[str, Any]) -> None:
        self.created_buckets.append((name, options))

    def from_(self, name: str) -> FakeBucketAPI:
        assert name == storage.BUCKET_NAME
        return FakeBucketAPI(self)


class FakeSupabase:
    def __init__(self) -> None:
        self.storage = FakeSupabaseStorage()


@pytest.fixture
def fake_supabase(monkeypatch: pytest.MonkeyPatch) -> FakeSupabaseStorage:
    client = FakeSupabase()
    monkeypatch.setattr(storage, "get_supabase", lambda: client)
    return client.storage


def test_bucket_is_created_private(fake_supabase: FakeSupabaseStorage) -> None:
    storage.upload_pdf_to_storage("cit/doc.pdf", b"%PDF-1.4")
    assert fake_supabase.created_buckets, "bucket creation was never attempted"
    for _name, options in fake_supabase.created_buckets:
        assert options.get("public") is False, (
            "the PDF bucket must be private — it holds names, CNPs and addresses"
        )


def test_upload_returns_the_object_path_not_a_url(
    fake_supabase: FakeSupabaseStorage,
) -> None:
    """If upload handed back a URL, callers would persist it and the link's
    lifetime would be decided at write time instead of hand-out time."""
    result = storage.upload_pdf_to_storage("cit/doc.pdf", b"%PDF-1.4")
    assert result == "cit/doc.pdf"
    assert not result.startswith("http")


def test_signed_url_carries_a_bounded_ttl(fake_supabase: FakeSupabaseStorage) -> None:
    url = storage.create_signed_pdf_url("cit/doc.pdf")
    assert url is not None
    assert "token=" in url
    (path, ttl), = fake_supabase.signed
    assert path == "cit/doc.pdf"
    assert 0 < ttl <= 3600, f"TTL of {ttl}s is not a short-lived link"
    assert ttl == storage.SIGNED_URL_TTL_SECONDS


def test_signing_failure_degrades_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom:
        storage = None

        def __getattr__(self, name: str) -> Any:
            raise RuntimeError("supabase down")

    monkeypatch.setattr(storage, "get_supabase", Boom)
    assert storage.create_signed_pdf_url("cit/doc.pdf") is None
    assert storage.create_signed_pdf_urls(["cit/doc.pdf"]) == {}


def test_batch_signing_uses_one_round_trip(fake_supabase: FakeSupabaseStorage) -> None:
    paths = [f"cit/doc{i}.pdf" for i in range(5)]
    out = storage.create_signed_pdf_urls(paths)
    assert set(out) == set(paths)
    assert fake_supabase.batch_calls == 1


def test_batch_signing_of_nothing_makes_no_call(
    fake_supabase: FakeSupabaseStorage,
) -> None:
    assert storage.create_signed_pdf_urls([]) == {}
    assert fake_supabase.batch_calls == 0


def test_object_path_is_derivable_from_the_row() -> None:
    """Nothing needs to persist the path, so a link can always be re-signed."""
    assert storage.pdf_object_path("cit-1", "doc-1") == "cit-1/doc-1.pdf"
