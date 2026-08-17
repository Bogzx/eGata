"""PDF storage: Supabase Storage, or a local volume when there is no project.

The bucket holds completed primărie forms: full name, CNP, home address,
sometimes disability status. It used to be created with `public: True` and
served via `get_public_url`, so anyone who guessed or was forwarded a URL
could read someone's identity document, forever and unauthenticated. The
object path is `<citizen_id>/<document_id>.pdf` — both UUIDs, so it was not
trivially enumerable, but "hard to guess" is not access control and the URLs
were handed out in chat frontend_events and stored in the ledger payload.

Both backends now expose the same shape: an upload that returns an object
path, and a separate call that mints a short-lived signed link. Nothing
persists a URL, so a link's lifetime is decided when it is handed out rather
than baked into a database row that outlives it.

The local backend exists so `docker compose up` gives a stranger a working
stack with no Supabase project. It signs with the same JWT secret the API
uses and is served by app/files.py.
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import logging
import time
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlencode
from uuid import UUID

from app.config import get_settings

log = logging.getLogger("storage")

BUCKET_NAME = "pdfs"

# Long enough to finish a download or a print dialog, short enough that a
# forwarded link (chat log, screenshot, browser history) stops working.
SIGNED_URL_TTL_SECONDS = 900

LOCAL_URL_PREFIX = "/files/pdf"


def pdf_object_path(citizen_id: UUID | str, document_id: UUID | str) -> str:
    """The single source of truth for where a document's PDF lives.

    Fully derivable from the row, so nothing needs to persist it and a link
    can always be re-signed.
    """
    return f"{citizen_id}/{document_id}.pdf"


def active_backend() -> str:
    """'supabase' or 'local'."""
    settings = get_settings()
    configured = (settings.storage_backend or "auto").strip().lower()
    if configured in {"supabase", "local"}:
        return configured
    if configured != "auto":
        raise RuntimeError(
            f"STORAGE_BACKEND={configured!r} is not one of auto|supabase|local"
        )
    if settings.supabase_url and settings.supabase_service_role_key:
        return "supabase"
    return "local"


# ---------------------------------------------------------------------------
# Local backend
# ---------------------------------------------------------------------------


def local_storage_root() -> Path:
    root = Path(get_settings().pdf_storage_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_local_path(object_path: str) -> Path:
    """Resolve an object path under the storage root, or refuse.

    Object paths come from `pdf_object_path` today, but this is the boundary
    where a traversal would land if one ever came from a request instead.
    """
    root = local_storage_root()
    candidate = (root / object_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"object path escapes the storage root: {object_path!r}")
    return candidate


def _sign(object_path: str, expires_at: int) -> str:
    secret = get_settings().jwt_signing_secret.encode("utf-8")
    message = f"{object_path}:{expires_at}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_local_signature(object_path: str, expires_at: int, signature: str) -> bool:
    """Constant-time check of a local signed-URL signature and its expiry."""
    if expires_at < int(time.time()):
        return False
    return hmac.compare_digest(_sign(object_path, expires_at), signature)


def _local_signed_url(object_path: str, expires_in: int) -> str:
    expires_at = int(time.time()) + expires_in
    query = urlencode({"exp": expires_at, "sig": _sign(object_path, expires_at)})
    base = get_settings().public_base_url.rstrip("/")
    return f"{base}{LOCAL_URL_PREFIX}/{quote(object_path)}?{query}"


def read_local_pdf(object_path: str) -> bytes | None:
    path = _safe_local_path(object_path)
    if not path.is_file():
        return None
    return path.read_bytes()


def _local_upload(object_path: str, data: bytes) -> None:
    path = _safe_local_path(object_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


# ---------------------------------------------------------------------------
# Supabase backend
# ---------------------------------------------------------------------------


def _ensure_bucket() -> None:
    from app.db import get_supabase

    client = get_supabase()
    # Bucket may already exist; suppress the create error and proceed.
    with contextlib.suppress(Exception):
        client.storage.create_bucket(BUCKET_NAME, options={"public": False})


def _extract_signed_url(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    # storage3 returns both spellings; older versions returned only one.
    return payload.get("signedURL") or payload.get("signedUrl")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def upload_pdf_to_storage(object_path: str, data: bytes) -> str:
    """Upload and return the object path (NOT a URL).

    Callers that need a link must ask for one via `create_signed_pdf_url`, so
    that the link's lifetime is decided at hand-out time rather than baked
    into a database row that outlives it.
    """
    if active_backend() == "local":
        _local_upload(object_path, data)
        return object_path

    from app.db import get_supabase

    _ensure_bucket()
    client = get_supabase()
    client.storage.from_(BUCKET_NAME).upload(
        path=object_path,
        file=data,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    return object_path


def create_signed_pdf_url(
    object_path: str, expires_in: int = SIGNED_URL_TTL_SECONDS
) -> str | None:
    """A time-limited download link, or None if signing fails.

    Returning None rather than raising: a document whose link cannot be signed
    is still a valid document, and the citizen should see the rest of it
    instead of a 500.
    """
    try:
        if active_backend() == "local":
            return _local_signed_url(object_path, expires_in)

        from app.db import get_supabase

        client = get_supabase()
        result = client.storage.from_(BUCKET_NAME).create_signed_url(
            object_path, expires_in
        )
        return _extract_signed_url(result)
    except Exception:
        log.exception("create_signed_pdf_url failed for %s", object_path)
        return None


def create_signed_pdf_urls(
    object_paths: list[str], expires_in: int = SIGNED_URL_TTL_SECONDS
) -> dict[str, str]:
    """Batch form of `create_signed_pdf_url` — one round trip for a list view.

    Returns a {object_path: signed_url} map, omitting anything that failed.
    """
    if not object_paths:
        return {}
    try:
        if active_backend() == "local":
            return {p: _local_signed_url(p, expires_in) for p in object_paths}

        from app.db import get_supabase

        client = get_supabase()
        results = cast(
            list[dict[str, Any]],
            client.storage.from_(BUCKET_NAME).create_signed_urls(
                object_paths, expires_in
            ),
        )
    except Exception:
        log.exception("create_signed_pdf_urls failed for %d paths", len(object_paths))
        return {}

    out: dict[str, str] = {}
    for item in results:
        path = item.get("path")
        url = _extract_signed_url(item)
        if path and url:
            # The API echoes paths without the leading slash it sometimes adds.
            out[str(path).lstrip("/")] = url
    return out
