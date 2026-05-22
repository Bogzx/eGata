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
)
from app.pdf import render_and_compile
from app.procedures import get_registry
from app.security import current_citizen_id
from app.storage import upload_pdf_to_storage

router = APIRouter(prefix="/documents", tags=["documents"])


def _jsonb(value: Any) -> str:
    return _json.dumps(value, ensure_ascii=False)


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
        f"CivicAI: cererea a fost trimisă la primărie. "
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
    return DocumentResponse(**doc)


@router.get("", response_model=list[DocumentResponse])
def list_my_documents(
    citizen_id: UUID = Depends(current_citizen_id),
) -> list[DocumentResponse]:
    rows = list_documents_for_citizen(citizen_id)
    return [DocumentResponse(**r) for r in rows]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    citizen_id: UUID = Depends(current_citizen_id),
) -> DocumentResponse:
    doc = fetch_document(document_id)
    _require_owner(doc, citizen_id)
    return DocumentResponse(**doc)


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
    return DocumentResponse(**updated)


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
    object_path = f"{citizen_id}/{document_id}.pdf"
    pdf_url = upload_pdf_to_storage(object_path, pdf_bytes)
    set_document_pdf_url(document_id, pdf_url)

    append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.PDF_GENERATED,
        payload={"document_id": str(document_id), "pdf_url": pdf_url},
        document_id=document_id,
    )

    return GeneratePDFResponse(pdf_url=pdf_url)


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

    return DocumentResponse(**finalized)


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
