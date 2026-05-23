"""complete_document — render PDF, deliver, transition to DELIVERED.

This collapses the old generate_pdf + deliver into a single agent-facing
operation. The agent never juggles "did I generate the PDF yet?" — it's
one call that does both atomically (from the user's perspective).

Server-side flow:
  1. Verify all required fields satisfied (with applies_if).
  2. Render LaTeX → PDF via app.pdf.render_and_compile.
  3. Upload to storage.
  4. Finalize the document row (status=finalized, ref_number).
  5. Append ledger PDF_GENERATED + DELIVERED events.
  6. If delivery == "send", send the SMS to the citizen's phone.
  7. Transition session: REVIEWING → DELIVERED.

Valid states: REVIEWING (the typical path; all fields filled).
"""
from __future__ import annotations

from uuid import UUID

from app.agent_tools import Tool, ToolContext, ToolResult, register
from app.documents import (
    fetch_document,
    fetch_phone_for_citizen,
    finalize_document,
    generate_ref_number,
    send_delivery_sms,
    set_document_pdf_url,
)
from app.ledger import LedgerEventType, append_ledger
from app.pdf import render_and_compile
from app.procedures import get_registry
from app.procedure_state import all_required_satisfied
from app.sessions import Session, SessionState
from app.storage import upload_pdf_to_storage

_VALID_DELIVERY = {"save", "send", "print"}


async def execute(
    session: Session, ctx: ToolContext, delivery: str
) -> ToolResult:
    if delivery not in _VALID_DELIVERY:
        return ToolResult(
            error=f"delivery trebuie să fie unul din {sorted(_VALID_DELIVERY)}, a primit {delivery!r}."
        )
    if not session.active_document_id:
        return ToolResult(error="Niciun document activ.")

    doc_id = session.active_document_id
    doc_uuid = UUID(doc_id)
    citizen_uuid = UUID(session.citizen_id)
    doc = fetch_document(doc_uuid)
    if str(doc["citizen_id"]) != session.citizen_id:
        return ToolResult(error="Acest document nu îți aparține.")

    reg = get_registry()
    proc = reg.get(doc["procedure_id"])
    if proc is None:
        return ToolResult(error=f"Procedura {doc['procedure_id']!r} nu există.")

    fields = doc.get("fields") or {}
    if not all_required_satisfied(proc, fields, ctx.citizen_attributes):
        return ToolResult(
            error="Mai sunt câmpuri obligatorii necompletate. Completează-le mai întâi."
        )

    # 1. PDF
    pdf_bytes = render_and_compile(proc.template, fields)
    object_path = f"{session.citizen_id}/{doc_id}.pdf"
    pdf_url = upload_pdf_to_storage(object_path, pdf_bytes)
    set_document_pdf_url(doc_uuid, pdf_url)
    append_ledger(
        citizen_id=citizen_uuid,
        event_type=LedgerEventType.PDF_GENERATED,
        payload={"document_id": doc_id, "pdf_url": pdf_url},
        document_id=doc_uuid,
    )

    # 2. Finalize + deliver
    ref_number = generate_ref_number(doc_uuid)
    finalized = finalize_document(doc_uuid, delivery, ref_number)
    append_ledger(
        citizen_id=citizen_uuid,
        event_type=LedgerEventType.DELIVERED,
        payload={
            "document_id": doc_id,
            "delivery": delivery,
            "ref_number": ref_number,
        },
        document_id=doc_uuid,
    )
    if delivery == "send":
        phone = fetch_phone_for_citizen(citizen_uuid)
        send_delivery_sms(phone, ref_number)

    return ToolResult(
        output={
            "document_id": doc_id,
            "pdf_url": pdf_url,
            "delivery": finalized["delivery"],
            "ref_number": finalized["ref_number"],
            "status": finalized["status"],
        },
        transition_to=SessionState.DELIVERED,
        frontend_event={
            "type": "document_delivered",
            "document_id": doc_id,
            "pdf_url": pdf_url,
            "delivery": delivery,
            "ref_number": ref_number,
        },
    )


register(
    Tool(
        name="complete_document",
        description=(
            "Finalizează documentul: generează PDF-ul și aplică livrarea "
            "(save/send/print). Toate câmpurile obligatorii trebuie să fie "
            "completate, ținând cont de applies_if."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "delivery": {
                    "type": "STRING",
                    "enum": ["save", "send", "print"],
                },
            },
            "required": ["delivery"],
        },
        valid_states={SessionState.REVIEWING},
        execute=execute,
    )
)
