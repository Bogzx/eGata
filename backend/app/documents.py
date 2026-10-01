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
    GENESIS_HASH,
    LedgerEventType,
    append_ledger,
    canonical_json,
    fetch_ledger_for_document,
    sha256_hex,
    verify_chain,
    verify_signatures,
)
from app.ledger_signing import published_keys
from app.models import (
    CreateDocumentRequest,
    DeliverRequest,
    DocumentResponse,
    GeneratePDFResponse,
    LedgerEntry,
    LedgerResponse,
    LedgerSigningKey,
    PatchFieldsRequest,
)
from app.pdf import render_and_compile
from app.procedure_state import (
    FieldValidationError,
    all_required_satisfied,
    coerce_field_value,
    validate_field_value,
)
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
    """`CV-XXXX-XXXX` from the document UUID — not a real registration number.

    Eight hex digits (4.3e9 values). The old four (65,536) made two citizens
    sharing a number likely after a few hundred documents (birthday bound).
    """
    raw = str(document_id).replace("-", "").upper()
    return f"CV-{raw[:4]}-{raw[4:8]}"


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


def send_delivery_sms(phone: str, ref_number: str) -> bool:
    """Text the citizen their reference. True only if Twilio accepted it.

    The text says what happened and nothing more: eGata fills and stores
    the form, it does not file it with the primărie.
    """
    settings = get_settings()
    if settings.mock_otp:
        # Reuse the mock-mode flag for SMS in dev to avoid Twilio costs.
        return False
    if not settings.twilio_account_sid or not settings.twilio_phone_number:
        return False
    body = (
        f"eGata: cererea ta e completată, referința {ref_number}. "
        "PDF-ul e în Documentele mele; semnează-l și depune-l la ghișeul primăriei."
    )
    client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
    client.messages.create(from_=settings.twilio_phone_number, to=phone, body=body)
    return True


def fetch_phone_for_citizen(citizen_id: UUID) -> str:
    with get_pg_connection() as conn, conn.cursor() as cur:
        cur.execute("select phone from citizens where id = %s;", (str(citizen_id),))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Citizen not found")
    return str(row["phone"])


def pdf_generated_payload(
    document_id: UUID | str, object_path: str, pdf_bytes: bytes, fields: dict[str, Any]
) -> dict[str, Any]:
    """Ledger payload for a rendered PDF.

    Binds the ledger to the document's *content*, not just to the fact that a
    file was written: `pdf_sha256` is the hash of the exact bytes stored, and
    `fields_sha256` the hash of the field values they were rendered from. A
    PDF swapped in storage afterwards no longer matches its ledger row
    (`scripts/verify_ledger.py --pdf` checks this). The ledger records the
    location, never a signed link: rows are permanent and a credential-bearing
    URL in one would outlive its own expiry.
    """
    return {
        "document_id": str(document_id),
        "object_path": object_path,
        "pdf_sha256": sha256_hex(pdf_bytes),
        "fields_sha256": sha256_hex(canonical_json(fields).encode("utf-8")),
    }


def _require_owner(doc: dict[str, Any], citizen_id: UUID) -> None:
    if str(doc["citizen_id"]) != str(citizen_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your document")


def _citizen_attributes(citizen_id: UUID) -> dict[str, Any]:
    # Local import: app.citizens is a router module; keep documents importable
    # on its own.
    from app.citizens import fetch_citizen_by_id

    return fetch_citizen_by_id(citizen_id).get("attributes") or {}


def _all_required_present(
    procedure_id: str, fields: dict[str, Any], citizen_attrs: dict[str, Any]
) -> bool:
    """Required-field check with applies_if, same rule the agent uses.

    The old check ignored applies_if, so a required-but-inapplicable field
    (e.g. a co-owner's name when there is no co-owner) kept a finished draft
    from ever counting as complete.
    """
    proc = get_registry().get(procedure_id)
    if proc is None:
        return False
    return all_required_satisfied(proc, fields, citizen_attrs)


def _require_draft(doc: dict[str, Any]) -> None:
    """Finalized documents are frozen.

    Their ledger already records the PDF (by hash) that was delivered;
    editing fields, re-rendering or re-delivering afterwards would make the
    stored form disagree with what the citizen submitted — and a second
    `delivered` row would make the reminders worker fire twice.
    """
    if doc.get("status") == "finalized":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "document_finalized",
                "message": "Documentul a fost deja finalizat.",
                "ref_number": doc.get("ref_number"),
            },
        )


def _validated_patch(procedure_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Coerce + validate a field patch against the procedure schema (422 on error)."""
    proc = get_registry().get(procedure_id)
    if proc is None:
        raise HTTPException(status_code=400, detail=f"Procedure {procedure_id} not found")
    out: dict[str, Any] = {}
    errors: list[str] = []
    for name, raw in patch.items():
        value = coerce_field_value(proc, name, raw)
        try:
            validate_field_value(proc, name, value)
        except FieldValidationError as exc:
            errors.append(str(exc))
            continue
        out[name] = value
    if errors:
        raise HTTPException(status_code=422, detail={"code": "invalid_fields", "errors": errors})
    return out


def _latest_pdf_matches_fields(document_id: UUID, fields: dict[str, Any]) -> bool:
    """True if the newest rendered PDF was rendered from exactly these fields."""
    rows = fetch_ledger_for_document(document_id)
    for row in reversed(rows):
        if row["event_type"] != LedgerEventType.PDF_GENERATED.value:
            continue
        payload = row["payload"]
        if isinstance(payload, str):
            payload = _json.loads(payload)
        expected = sha256_hex(canonical_json(fields).encode("utf-8"))
        return bool(payload.get("fields_sha256") == expected)
    return False


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
    _require_draft(doc)
    patch = _validated_patch(doc["procedure_id"], req.fields)
    attrs = _citizen_attributes(citizen_id)
    was_complete = _all_required_present(doc["procedure_id"], doc["fields"], attrs)
    updated = update_document_fields(document_id, patch)
    now_complete = _all_required_present(updated["procedure_id"], updated["fields"], attrs)
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
    _require_draft(doc)

    reg = get_registry()
    proc = reg.get(doc["procedure_id"])
    if proc is None:
        raise HTTPException(status_code=400, detail=f"Procedure {doc['procedure_id']} not found")

    pdf_bytes = render_and_compile(proc.template, doc["fields"])
    object_path = pdf_object_path(citizen_id, document_id)
    upload_pdf_to_storage(object_path, pdf_bytes)
    set_document_pdf_url(document_id, object_path)

    append_ledger(
        citizen_id=citizen_id,
        event_type=LedgerEventType.PDF_GENERATED,
        payload=pdf_generated_payload(document_id, object_path, pdf_bytes, doc["fields"]),
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
    _require_draft(doc)
    if not _all_required_present(
        doc["procedure_id"], doc["fields"], _citizen_attributes(citizen_id)
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "incomplete",
                "message": "Mai sunt câmpuri obligatorii necompletate.",
            },
        )
    # What gets delivered must be the PDF the ledger hashed, rendered from the
    # fields as they are now — not nothing, and not a render from before the
    # last edit.
    if not doc.get("pdf_url") or not _latest_pdf_matches_fields(document_id, doc["fields"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "pdf_missing_or_stale",
                "message": "Generează PDF-ul (POST /documents/{id}/generate-pdf) înainte de livrare.",
            },
        )

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
            created_at=r["created_at"],
            payload=_json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
            hashed_at=r.get("ts_iso"),
            key_id=r.get("key_id"),
            signature=r.get("signature"),
        )
        for r in rows
    ]
    verified = verify_chain(rows, genesis_hash=GENESIS_HASH) and verify_signatures(
        rows, citizen_id=str(doc["citizen_id"]), document_id=str(document_id)
    )
    return LedgerResponse(
        entries=entries,
        verified=verified,
        genesis_hash=GENESIS_HASH,
        citizen_id=str(doc["citizen_id"]),
        document_id=str(document_id),
        signing_keys=[LedgerSigningKey(**k) for k in published_keys()],
    )
