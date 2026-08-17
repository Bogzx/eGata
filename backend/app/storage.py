"""Supabase Storage helpers.

The bucket holds completed primărie forms: full name, CNP, home address,
sometimes disability status. It used to be created with `public: True` and
served via `get_public_url`, so anyone who guessed or was forwarded a URL
could read someone's identity document, forever and unauthenticated. The
object path is `<citizen_id>/<document_id>.pdf` — both UUIDs, so it was not
trivially enumerable, but "hard to guess" is not access control and the URLs
were handed out in chat frontend_events and stored in the ledger payload.

The bucket is private now and every link is a short-lived signed URL.
"""
from __future__ import annotations

import contextlib
import logging
from typing import Any, cast
from uuid import UUID

from app.db import get_supabase

log = logging.getLogger("storage")

BUCKET_NAME = "pdfs"

# Long enough to finish a download or a print dialog, short enough that a
# forwarded link (chat log, screenshot, browser history) stops working.
SIGNED_URL_TTL_SECONDS = 900


def pdf_object_path(citizen_id: UUID | str, document_id: UUID | str) -> str:
    """The single source of truth for where a document's PDF lives.

    Fully derivable from the row, so nothing needs to persist it and a link
    can always be re-signed.
    """
    return f"{citizen_id}/{document_id}.pdf"


def _ensure_bucket() -> None:
    client = get_supabase()
    # Bucket may already exist; suppress the create error and proceed.
    with contextlib.suppress(Exception):
        client.storage.create_bucket(BUCKET_NAME, options={"public": False})


def upload_pdf_to_storage(object_path: str, data: bytes) -> str:
    """Upload and return the object path (NOT a URL).

    Callers that need a link must ask for one via `create_signed_pdf_url`, so
    that the link's lifetime is decided at hand-out time rather than baked
    into a database row that outlives it.
    """
    _ensure_bucket()
    client = get_supabase()
    client.storage.from_(BUCKET_NAME).upload(
        path=object_path,
        file=data,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    return object_path


def _extract_signed_url(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    # storage3 returns both spellings; older versions returned only one.
    return payload.get("signedURL") or payload.get("signedUrl")


def create_signed_pdf_url(
    object_path: str, expires_in: int = SIGNED_URL_TTL_SECONDS
) -> str | None:
    """A time-limited download link, or None if signing fails.

    Returning None rather than raising: a document whose link cannot be signed
    is still a valid document, and the citizen should see the rest of it
    instead of a 500.
    """
    try:
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
