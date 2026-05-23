"""generate_pdf — compile active document to PDF, upload, return URL."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.documents import (
    fetch_document,
    set_document_pdf_url,
)
from app.ledger import LedgerEventType, append_ledger
from app.pdf import render_and_compile
from app.procedures import get_registry
from app.storage import upload_pdf_to_storage
from app.tools import ToolContext, register


class PdfResult(BaseModel):
    pdf_url: str


@register("generate_pdf")
async def generate_pdf(ctx: ToolContext) -> PdfResult:
    """Render the active document to PDF and upload it to Storage."""
    if not ctx.document_id:
        raise ValueError("document_id required for generate_pdf")

    doc_uuid = UUID(ctx.document_id)
    citizen_uuid = UUID(ctx.citizen_id)
    doc = fetch_document(doc_uuid)
    if str(doc["citizen_id"]) != ctx.citizen_id:
        raise ValueError("not your document")

    reg = get_registry()
    proc = reg.get(doc["procedure_id"])
    if proc is None:
        raise ValueError(f"Procedure {doc['procedure_id']} not found")

    missing = [f.name for f in proc.fields if f.required and not (doc["fields"] or {}).get(f.name)]
    if missing:
        raise ValueError(f"missing required fields: {missing}")

    pdf_bytes = render_and_compile(proc.template, doc["fields"])
    object_path = f"{ctx.citizen_id}/{ctx.document_id}.pdf"
    pdf_url = upload_pdf_to_storage(object_path, pdf_bytes)
    set_document_pdf_url(doc_uuid, pdf_url)

    append_ledger(
        citizen_id=citizen_uuid,
        event_type=LedgerEventType.PDF_GENERATED,
        payload={"document_id": ctx.document_id, "pdf_url": pdf_url},
        document_id=doc_uuid,
    )
    return PdfResult(pdf_url=pdf_url)
