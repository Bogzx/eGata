"""Document CRUD + ledger milestone writes + PDF + deliver."""
from __future__ import annotations

import json as _json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from twilio.rest import Client as TwilioClient

from app.config import get_settings
from app.db import get_pg_connection
from app.ledger import (
    LedgerEventType,
    append_ledger,
    fetch_ledger_for_document,
    verify_chain,
)
from app.models import (
    CreateDocumentRequest,
    DeliverRequest,
    DocumentResponse,
    GeneratePDFResponse,
    LedgerEntry,
    LedgerResponse,
    PatchFieldsRequest,
    SubmitDocumentRequest,
    SubmitDocumentResponse,
)
from app.pdf import render_and_compile
from app.procedures import get_registry
from app.security import current_citizen_id
from app.storage import (
    create_signed_pdf_url,
    create_signed_pdf_urls,
    pdf_object_path,
    upload_pdf_to_storage,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def _jsonb(value: Any) -> str:
    return _json.dumps(value, ensure_ascii=False)



def _document_response(row: dict[str, Any]) -> DocumentResponse:
    """Serialize a document row, exchanging the stored object path for a
    freshly signed, short-lived download URL.

    `documents.pdf_url` holds the storage object path, not a URL: the bucket
    is private (storage.py), so a link is minted per response and expires.
    Rows written before that change hold a permanent public URL — those are
    exactly the leak, so they are re-derived and re-signed rather than
    handed back.
    """
    data = dict(row)
    stored = data.get("pdf_url")
    if stored:
        path = str(stored)
        if path.startswith("http"):
            path = pdf_object_path(data["citizen_id"], data["id"])
        data["pdf_url"] = create_signed_pdf_url(path)
    return DocumentResponse(**data)


def _document_responses(rows: list[dict[str, Any]]) -> list[DocumentResponse]:
    """List form — one signing round trip for the whole page."""
    paths: dict[int, str] = {}
    for i, row in enumerate(rows):
        stored = row.get("pdf_url")
        if not stored:
            continue
        path = str(stored)
        if path.startswith("http"):
            path = pdf_object_path(row["citizen_id"], row["id"])
        paths[i] = path

    signed = create_signed_pdf_urls(sorted(set(paths.values())))
    out: list[DocumentResponse] = []
    for i, row in enumerate(rows):
        data = dict(row)
        data["pdf_url"] = signed.get(paths[i]) if i in paths else None
        out.append(DocumentResponse(**data))
    return out


def insert_document(citizen_id: UUID, procedure_id: str) -> dict[str, Any]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into documents (citizen_id, procedure_id) values (%s, %s) "
            "returning id, citizen_id, procedure_id, status, fields, pdf_url, delivery, "
            "ref_number, created_at, delivered_at;",
            (str(citizen_id), procedure_id),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=500, detail="insert failed")
        conn.commit()
    return dict(row)


def fetch_document(document_id: UUID) -> dict[str, Any]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, citizen_id, procedure_id, status, fields, pdf_url, delivery, "
            "ref_number, created_at, delivered_at from documents where id = %s;",
            (str(document_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return dict(row)


def list_documents_for_citizen(citizen_id: UUID) -> list[dict[str, Any]]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, citizen_id, procedure_id, status, fields, pdf_url, delivery, "
            "ref_number, created_at, delivered_at "
            "from documents where citizen_id = %s order by created_at desc;",
            (str(citizen_id),),
        )
        return [dict(r) for r in cur.fetchall()]


def update_document_fields(document_id: UUID, fields: dict[str, Any]) -> dict[str, Any]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "update documents set fields = fields || %s::jsonb where id = %s "
            "returning id, citizen_id, procedure_id, status, fields, pdf_url, delivery, "
            "ref_number, created_at, delivered_at;",
            (_jsonb(fields), str(document_id)),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found")
        conn.commit()
    return dict(row)


def set_document_pdf_url(document_id: UUID, pdf_url: str) -> None:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "update documents set pdf_url = %s where id = %s;",
            (pdf_url, str(document_id)),
        )
        conn.commit()


def generate_ref_number(document_id: UUID) -> str:
    raw = str(document_id).replace("-", "").upper()
    return f"CV-{raw[:4]}"


def generate_submit_ref_number(document_id: UUID) -> str:
    """Kiosk-submit ref format: REG-{yyyy}-{8 hex chars from doc uuid}.

    Deterministic (same doc → same ref) so a 409 path can return the
    original ref. Collision risk is negligible: 16^8 ≈ 4.3B values per
    year. Not using a postgres sequence to avoid the migration in a
    hackathon timeline.
    """
    year = datetime.now(timezone.utc).year
    suffix = str(document_id).replace("-", "")[:8].upper()
    return f"REG-{year}-{suffix}"


def finalize_document(
    document_id: UUID, delivery: str, ref_number: str
) -> dict[str, Any]:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "update documents set status = 'finalized', delivery = %s, "
            "ref_number = %s, delivered_at = %s "
            "where id = %s "
            "returning id, citizen_id, procedure_id, status, fields, pdf_url, delivery, "
            "ref_number, created_at, delivered_at;",
            (delivery, ref_number, datetime.now(timezone.utc), str(document_id)),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found")
        conn.commit()
    return dict(row)


def send_delivery_sms(phone: str, ref_number: str) -> None:
    settings = get_settings()
    if settings.mock_otp:
        # Reuse the mock-mode flag for SMS in dev to avoid Twilio costs.
        return
    if not settings.twilio_account_sid or not settings.twilio_phone_number:
        return
    body = (
        f"eGata: cererea a fost trimisă la primărie. "
        f"Număr de înregistrare: {ref_number}."
    )
    client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
    client.messages.create(from_=settings.twilio_phone_number, to=phone, body=body)


def fetch_phone_for_citizen(citizen_id: UUID) -> str:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute("select phone from citizens where id = %s;", (str(citizen_id),))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Citizen not found")
    return str(row["phone"])


def _require_owner(doc: dict[str, Any], citizen_id: UUID) -> None:
    if str(doc["citizen_id"]) != str(citizen_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your document")


def _all_required_present(procedure_id: str, fields: dict[str, Any]) -> bool:
    reg = get_registry()
    proc = reg.get(procedure_id)
    if proc is None:
        return False
    return all(not (f.required and not fields.get(f.name)) for f in proc.fields)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    req: CreateDocumentRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> DocumentResponse:
    reg = get_registry()
    if req.procedure_id not in reg:
        raise HTTPException(status_code=404, detail=f"Unknown procedure {req.procedure_id}")
    doc = insert_document(citizen_id, req.procedure_id)
    append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.DOC_CREATED,
        payload={"document_id": str(doc["id"]), "procedure_id": req.procedure_id},
        document_id=doc["id"],
    )
    return _document_response(doc)


@router.get("", response_model=list[DocumentResponse])
def list_my_documents(
    citizen_id: UUID = Depends(current_citizen_id),
) -> list[DocumentResponse]:
    rows = list_documents_for_citizen(citizen_id)
    return _document_responses(rows)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    citizen_id: UUID = Depends(current_citizen_id),
) -> DocumentResponse:
    doc = fetch_document(document_id)
    _require_owner(doc, citizen_id)
    return _document_response(doc)


@router.patch("/{document_id}/fields", response_model=DocumentResponse)
def patch_fields(
    document_id: UUID,
    req: PatchFieldsRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> DocumentResponse:
    doc = fetch_document(document_id)
    _require_owner(doc, citizen_id)
    was_complete = _all_required_present(doc["procedure_id"], doc["fields"])
    updated = update_document_fields(document_id, req.fields)
    now_complete = _all_required_present(updated["procedure_id"], updated["fields"])
    if not was_complete and now_complete:
        append_ledger(
            citizen_id=citizen_id,
            event_type=LedgerEventType.COMPLETED_DRAFT,
            payload={"document_id": str(document_id)},
            document_id=document_id,
        )
    return _document_response(updated)


@router.post("/{document_id}/generate-pdf", response_model=GeneratePDFResponse)
def generate_pdf(
    document_id: UUID,
    citizen_id: UUID = Depends(current_citizen_id),
) -> GeneratePDFResponse:
    doc = fetch_document(document_id)
    _require_owner(doc, citizen_id)

    reg = get_registry()
    proc = reg.get(doc["procedure_id"])
    if proc is None:
        raise HTTPException(status_code=400, detail=f"Procedure {doc['procedure_id']} not found")

    pdf_bytes = render_and_compile(proc.template, doc["fields"])
    object_path = pdf_object_path(citizen_id, document_id)
    upload_pdf_to_storage(object_path, pdf_bytes)
    set_document_pdf_url(document_id, object_path)

    # The ledger records *that* a PDF exists and where, never a signed link:
    # ledger rows are permanent and a credential-bearing URL in one would
    # outlive its own expiry as a written-down secret.
    append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.PDF_GENERATED,
        payload={"document_id": str(document_id), "object_path": object_path},
        document_id=document_id,
    )

    signed = create_signed_pdf_url(object_path)
    if signed is None:
        raise HTTPException(status_code=502, detail="Could not sign the PDF download URL")
    return GeneratePDFResponse(pdf_url=signed)


@router.post("/{document_id}/deliver", response_model=DocumentResponse)
def deliver(
    document_id: UUID,
    req: DeliverRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> DocumentResponse:
    doc = fetch_document(document_id)
    _require_owner(doc, citizen_id)

    ref_number = generate_ref_number(document_id)
    finalized = finalize_document(document_id, req.delivery, ref_number)

    append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.DELIVERED,
        payload={
            "document_id": str(document_id),
            "delivery": req.delivery,
            "ref_number": ref_number,
        },
        document_id=document_id,
    )

    if req.delivery == "send":
        phone = fetch_phone_for_citizen(citizen_id)
        send_delivery_sms(phone, ref_number)

    return _document_response(finalized)


@router.post(
    "/{document_id}/submit",
    response_model=SubmitDocumentResponse,
)
def submit(
    document_id: UUID,
    req: SubmitDocumentRequest,
    citizen_id: UUID = Depends(current_citizen_id),
) -> SubmitDocumentResponse:
    """Kiosk-flow submit. Replaces /deliver for the /ghiseu surface.

    `method=city` → marks delivered, routes to destination department
    (notification queueing deferred to Phase 2.4 polish).
    `method=email` → marks delivered, attempts email delivery to the
    citizen (or to `email_address` override). Email infrastructure is
    not wired in v1 — the intent is recorded in the ledger; production
    deploy adds SendGrid/SMTP later.

    Idempotent on already-delivered documents: returns 409 with the
    existing ref_number, NOT a fresh one.
    """
    doc = fetch_document(document_id)
    _require_owner(doc, citizen_id)

    # Idempotency: a doc that's already delivered returns its existing ref
    # under a 409 status. The frontend treats this as a "success" (the user
    # has already seen the done screen for this doc).
    if doc.get("delivered_at") is not None:
        existing_ref = doc.get("ref_number") or ""
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "already_delivered", "ref_number": existing_ref},
        )

    ref_number = generate_submit_ref_number(document_id)
    finalized = finalize_document(document_id, req.method, ref_number)

    append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.DELIVERED,
        payload={
            "document_id": str(document_id),
            "delivery": req.method,
            "ref_number": ref_number,
            **(
                {"to_email": req.email_address}
                if req.method == "email" and req.email_address
                else {}
            ),
        },
        document_id=document_id,
    )

    delivered_at = finalized.get("delivered_at")
    if delivered_at is None:
        # Defensive: finalize_document always sets it, but pin a default
        # so the response stays well-formed if a future refactor changes it.
        delivered_at = datetime.now(timezone.utc)

    return SubmitDocumentResponse(
        ref_number=ref_number,
        delivery=req.method,
        delivered_at=delivered_at,
    )


@router.get("/{document_id}/ledger", response_model=LedgerResponse)
def get_ledger(
    document_id: UUID,
    citizen_id: UUID = Depends(current_citizen_id),
) -> LedgerResponse:
    doc = fetch_document(document_id)
    _require_owner(doc, citizen_id)
    rows = fetch_ledger_for_document(document_id)
    entries = [
        LedgerEntry(
            id=r["id"],
            event_type=r["event_type"],
            payload_hash=r["payload_hash"],
            prev_hash=r["prev_hash"],
            row_hash=r["row_hash"],
            created_at=r["created_at"] if isinstance(r["created_at"], datetime) else r["created_at"],
        )
        for r in rows
    ]
    verified = verify_chain(rows, genesis_hash=get_settings().ledger_genesis_hash)
    return LedgerResponse(entries=entries, verified=verified)
