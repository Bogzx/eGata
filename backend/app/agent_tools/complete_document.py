"""complete_document — render PDF, deliver, transition to DELIVERED.

This collapses the old generate_pdf + deliver into a single agent-facing
operation. The agent never juggles "did I generate the PDF yet?" — it's
one call that does both atomically (from the user's perspective).

Server-side flow:
  1. Idempotency: if document already finalized, return cached delivery.
  2. Verify all required fields satisfied (with applies_if).
  3. Render LaTeX → PDF via app.pdf.render_and_compile.
  4. Upload to storage.
  5. Finalize the document row (status=finalized, ref_number).
  6. Append ledger PDF_GENERATED + DELIVERED events.
  7. If delivery == "send", send the SMS to the citizen's phone.
  8. Transition session: REVIEWING → DELIVERED.

All blocking I/O (pdflatex subprocess, Supabase upload, Twilio HTTP, DB
writes) is offloaded via asyncio.to_thread so the WebSocket audio pumps
in agent_voice.py keep flowing while a PDF compiles (~5-15s normally).

Valid states: REVIEWING (the typical path; all fields filled).
"""
from __future__ import annotations

import asyncio
import logging
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
from app.sessions import Session, SessionState, is_review_confirmed
from app.storage import (
    create_signed_pdf_url,
    pdf_object_path,
    upload_pdf_to_storage,
)

log = logging.getLogger("complete_document")

_VALID_DELIVERY = {"save", "send", "print", "download"}


def _db_delivery(delivery: str) -> str:
    # "download" is a frontend-only signal (auto-trigger browser download).
    # Persist as "save" so we don't have to alter the DB CHECK constraint.
    return "save" if delivery == "download" else delivery


async def execute(
    session: Session, ctx: ToolContext, delivery: str
) -> ToolResult:
    if delivery not in _VALID_DELIVERY:
        return ToolResult(
            error=f"delivery trebuie să fie unul din {sorted(_VALID_DELIVERY)}, a primit {delivery!r}."
        )
    if not session.active_document_id:
        return ToolResult(error="Niciun document activ.")
    # Same gate as propose_widget(type='choice'): require an explicit Da on
    # a confirm widget in REVIEWING before delivering. Catches the case
    # where the LLM tries to skip the choice widget entirely.
    # `output` (not `error`) so the frontend doesn't bubble this as a
    # user-visible system message — guidance is for the LLM only.
    if (
        session.state == SessionState.REVIEWING
        and not is_review_confirmed(session.id)
    ):
        return ToolResult(
            output={
                "refused": True,
                "reason": (
                    "Nu poți apela complete_document înainte ca cetățeanul "
                    "să confirme datele. Apelează propose_widget(type='confirm', "
                    "question='Verifică datele din dreapta. Sunt complete și corecte?'), "
                    "apoi widget-ul de livrare, abia apoi complete_document."
                ),
            }
        )
    # Race guard: when the LLM emits propose_widget(choice) AND
    # complete_document in the same turn, the dispatcher runs them
    # sequentially and complete_document beats the user's click on the
    # delivery picker — locking the document to a guessed delivery.
    # If there's still a pending widget on the session, the user hasn't
    # answered yet; refuse and tell the LLM to wait.
    pending_choice = next(
        (w for w in session.pending_widgets if w.type == "choice"),
        None,
    )
    if pending_choice is not None:
        return ToolResult(
            output={
                "refused": True,
                "reason": (
                    f"Nu apela complete_document în același tur cu propose_widget. "
                    f"Widget-ul {pending_choice.widget_id!r} ({pending_choice.question!r}) "
                    f"încă nu a primit răspuns. AȘTEAPTĂ alegerea cetățeanului, "
                    f"apoi apelează complete_document cu delivery-ul corespunzător "
                    f"răspunsului ('save' pentru Salvare PDF, 'send' pentru "
                    f"Trimitere la primărie, 'print' pentru Tipărire, "
                    f"'download' pentru Descarcă PDF)."
                ),
            }
        )

    doc_id = session.active_document_id
    doc_uuid = UUID(doc_id)
    citizen_uuid = UUID(session.citizen_id)
    doc = await asyncio.to_thread(fetch_document, doc_uuid)
    if str(doc["citizen_id"]) != session.citizen_id:
        return ToolResult(error="Acest document nu îți aparține.")

    # Idempotency: if the doc is already finalized, short-circuit. Re-emitting
    # the delivery frontend_event lets the UI re-render the success pane on
    # an LLM retry without burning a second PDF + SMS.
    if doc.get("status") == "finalized" and doc.get("ref_number"):
        log.info(
            "complete_document: doc %s already finalized, returning cached result",
            doc_id,
        )
        # `pdf_url` holds the storage object path, and the bucket is
        # private — mint a fresh signed link rather than replaying whatever
        # is in the row (which for pre-private rows is a permanent public
        # URL, and for post-private rows would be a path the browser cannot
        # fetch).
        cached_pdf_url = ""
        if doc.get("pdf_url"):
            cached_path = str(doc["pdf_url"])
            if cached_path.startswith("http"):
                cached_path = pdf_object_path(doc["citizen_id"], doc["id"])
            cached_pdf_url = await asyncio.to_thread(
                create_signed_pdf_url, cached_path
            ) or ""
        # On retry the caller may pass "download" even though the row is
        # persisted as "save" — preserve the caller's intent so the UI
        # re-triggers the browser download.
        cached_delivery = delivery if delivery == "download" else (
            doc.get("delivery") or delivery
        )
        cached_ref = doc["ref_number"]
        return ToolResult(
            output={
                "document_id": doc_id,
                "pdf_url": cached_pdf_url,
                "delivery": cached_delivery,
                "ref_number": cached_ref,
                "status": "finalized",
                "already_finalized": True,
            },
            transition_to=SessionState.DELIVERED,
            frontend_event={
                "type": "document_delivered",
                "document_id": doc_id,
                "pdf_url": cached_pdf_url,
                "delivery": cached_delivery,
                "ref_number": cached_ref,
            },
        )

    reg = get_registry()
    proc = reg.get(doc["procedure_id"])
    if proc is None:
        return ToolResult(error=f"Procedura {doc['procedure_id']!r} nu există.")

    fields = doc.get("fields") or {}
    if not all_required_satisfied(proc, fields, ctx.citizen_attributes):
        return ToolResult(
            error="Mai sunt câmpuri obligatorii necompletate. Completează-le mai întâi."
        )

    # 1. PDF — pdflatex blocks ~5-15s, runs in worker thread.
    pdf_bytes = await asyncio.to_thread(render_and_compile, proc.template, fields)
    object_path = pdf_object_path(session.citizen_id, doc_id)
    await asyncio.to_thread(upload_pdf_to_storage, object_path, pdf_bytes)
    await asyncio.to_thread(set_document_pdf_url, doc_uuid, object_path)
    # The ledger stores the location, never the signed link: ledger rows are
    # permanent and a credential-bearing URL in one outlives its own expiry.
    await asyncio.to_thread(
        append_ledger,
        citizen_id=citizen_uuid,
        event_type=LedgerEventType.PDF_GENERATED,
        payload={"document_id": doc_id, "object_path": object_path},
        document_id=doc_uuid,
    )
    pdf_url = await asyncio.to_thread(create_signed_pdf_url, object_path) or ""

    # 2. Finalize + deliver
    ref_number = generate_ref_number(doc_uuid)
    finalized = await asyncio.to_thread(
        finalize_document, doc_uuid, _db_delivery(delivery), ref_number
    )
    await asyncio.to_thread(
        append_ledger,
        citizen_id=citizen_uuid,
        event_type=LedgerEventType.DELIVERED,
        payload={
            "document_id": doc_id,
            "delivery": delivery,
            "ref_number": ref_number,
        },
        document_id=doc_uuid,
    )
    # SMS is best-effort: a Twilio blip MUST NOT cause the LLM to retry and
    # double-finalize. Log + carry on; the doc is already finalized and the
    # delivery frontend_event will still fire.
    if delivery == "send":
        try:
            phone = await asyncio.to_thread(fetch_phone_for_citizen, citizen_uuid)
            await asyncio.to_thread(send_delivery_sms, phone, ref_number)
        except Exception:  # noqa: BLE001
            log.exception(
                "send_delivery_sms failed for doc=%s ref=%s — doc remains "
                "finalized, will not retry",
                doc_id,
                ref_number,
            )

    return ToolResult(
        output={
            "document_id": doc_id,
            "pdf_url": pdf_url,
            # Echo the original delivery (incl. "download") back to the agent
            # so it can phrase the closing message correctly.
            "delivery": delivery,
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
                    "enum": ["save", "send", "print", "download"],
                },
            },
            "required": ["delivery"],
        },
        valid_states={SessionState.REVIEWING},
        execute=execute,
    )
)
