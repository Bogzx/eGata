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
from app.documents import insert_document
from app.ledger import LedgerEventType, append_ledger
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

    doc = insert_document(UUID(session.citizen_id), procedure_id)
    doc_id = str(doc["id"])

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
            "title": reg[procedure_id].title,
            "fields": doc.get("fields") or {},
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
