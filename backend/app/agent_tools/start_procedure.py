"""start_procedure — create a Document and move the session into FILLING.

Valid states: CONFIRMING_MATCH (normal path, after lookup_procedure),
EXPLORING (skip-confirmation path when the agent is confident enough),
DELIVERED (start the next procedure of a scenario chain).

This tool replaces the frontend's "Începe" button click. In voice_only
mode this is the ONLY path to open a document.
"""
from __future__ import annotations

from uuid import UUID

from app.agent_tools import Tool, ToolContext, ToolResult, register
from app.documents import insert_document, update_document_fields
from app.ledger import LedgerEventType, append_ledger
from app.procedure_state import compute_profile_prefill
from app.procedures import get_registry
from app.sessions import Session, SessionState


async def execute(
    session: Session, ctx: ToolContext, procedure_id: str
) -> ToolResult:
    procedure_id = (procedure_id or "").strip()
    if not procedure_id:
        return ToolResult(error="procedure_id obligatoriu.")

    reg = get_registry()
    if procedure_id not in reg:
        return ToolResult(error=f"Procedura {procedure_id!r} nu există.")

    proc = reg[procedure_id]
    doc = insert_document(UUID(session.citizen_id), procedure_id)
    doc_id = str(doc["id"])

    # Auto-fill profile-sourced fields (cnp, nume_complet, email, etc.) from
    # citizen attributes so the agent doesn't ask the user for values it
    # already has in the profile. Without this the schema's `source: "profile"`
    # is aspirational — doc.fields stays empty and the agent has to chase
    # every field.
    prefill = compute_profile_prefill(proc, ctx.citizen_attributes)
    fields_snapshot: dict = dict(doc.get("fields") or {})
    if prefill:
        updated = update_document_fields(UUID(doc_id), prefill)
        fields_snapshot = dict(updated.get("fields") or {})

    append_ledger(
        citizen_id=UUID(session.citizen_id),
        event_type=LedgerEventType.DOC_CREATED,
        payload={"document_id": doc_id, "procedure_id": procedure_id},
        document_id=UUID(doc_id),
    )

    session.active_document_id = doc_id
    return ToolResult(
        output={
            "document_id": doc_id,
            "procedure_id": procedure_id,
            "title": proc.title,
            "fields": fields_snapshot,
        },
        transition_to=SessionState.FILLING,
        frontend_event={
            "type": "document_opened",
            "document_id": doc_id,
            "procedure_id": procedure_id,
        },
    )


register(
    Tool(
        name="start_procedure",
        description=(
            "Deschide o procedură: creează documentul în lucru și trece "
            "sesiunea în starea de completare. Confirmă întâi cu cetățeanul."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {"procedure_id": {"type": "STRING"}},
            "required": ["procedure_id"],
        },
        valid_states={
            SessionState.CONFIRMING_MATCH,
            SessionState.EXPLORING,
            SessionState.DELIVERED,
        },
        execute=execute,
    )
)
