"""Supabase Storage helpers."""
from __future__ import annotations

import contextlib
from typing import cast

from app.db import get_supabase

BUCKET_NAME = "pdfs"


def upload_pdf_to_storage(object_path: str, data: bytes) -> str:
    client = get_supabase()
    # Bucket may already exist; suppress the create error and proceed.
    with contextlib.suppress(Exception):
        client.storage.create_bucket(BUCKET_NAME, options={"public": True})
    client.storage.from_(BUCKET_NAME).upload(
        path=object_path,
        file=data,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    return cast(str, client.storage.from_(BUCKET_NAME).get_public_url(object_path))
