"""Serves PDFs for the local storage backend.

Only mounted meaningfully when STORAGE_BACKEND resolves to `local` — the
Supabase backend signs its own URLs and this route is never linked to.

Authorization is the signature in the query string, not the session: the
frontend renders these as plain `<a href>` download links and a browser
navigation carries no Authorization header. That is the same trade Supabase's
`create_signed_url` makes. The signature covers the object path and an expiry,
so a forwarded link stops working, and it is checked in constant time.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.storage import active_backend, read_local_pdf, verify_local_signature

router = APIRouter(prefix="/files", tags=["files"])
log = logging.getLogger("files")


@router.get("/pdf/{citizen_id}/{filename}")
def get_pdf(
    citizen_id: str,
    filename: str,
    exp: int = Query(..., description="Unix timestamp the link expires at"),
    sig: str = Query(..., description="HMAC of the object path and expiry"),
) -> Response:
    if active_backend() != "local":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    object_path = f"{citizen_id}/{filename}"

    # Deliberately one message for bad-signature, expired and missing-file:
    # a distinguishable "signature ok but no such file" would confirm which
    # document IDs exist to someone holding a stale link.
    if not verify_local_signature(object_path, exp, sig):
        log.warning("files: rejected link for %s (bad signature or expired)", object_path)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Link invalid or expired"
        )

    try:
        data = read_local_pdf(object_path)
    except ValueError:
        log.warning("files: rejected traversal attempt %r", object_path)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Link invalid or expired"
        ) from None

    if data is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Link invalid or expired"
        )

    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            # Signed links are per-citizen; never let a shared cache keep one.
            "Cache-Control": "private, no-store",
        },
    )
