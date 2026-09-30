"""set_field — write a single document field with full validation.

Validates the value against the procedure's Pydantic schema (incl.
options enum) before writing. After write, re-evaluates field states
with `applies_if` and transitions FILLING → REVIEWING when all required
fields are satisfied.

Valid states: FILLING, REVIEWING (manual edits in review still update
through the agent path).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.agent_tools import Tool, ToolContext, ToolResult, register
from app.documents import fetch_document, update_document_fields
from app.ledger import LedgerEventType, append_ledger
from app.procedure_state import (
    FieldValidationError,
    all_required_satisfied,
    coerce_field_value,
    validate_field_value,
)
from app.procedures import get_registry
from app.sessions import Session, SessionState


async def execute(
    session: Session, ctx: ToolContext, name: str, value: Any
) -> ToolResult:
    if not session.active_document_id:
        return ToolResult(error="Niciun document activ.")
    doc_id = session.active_document_id

    doc = fetch_document(UUID(doc_id))
    if str(doc["citizen_id"]) != session.citizen_id:
        return ToolResult(error="Acest document nu îți aparține.")
    if doc.get("status") == "finalized":
        # Delivered forms are frozen: the ledger has already recorded the PDF
        # rendered from these values.
        return ToolResult(error="Documentul a fost deja finalizat și nu mai poate fi modificat.")

    reg = get_registry()
    proc = reg.get(doc["procedure_id"])
    if proc is None:
        return ToolResult(error=f"Procedura {doc['procedure_id']!r} nu există.")

    # Soft-skip unknown fields: the LLM often tries to set profile attributes
    # like `localitate` / `judet` that aren't in the current procedure's
    # schema. Surfacing this as a user-facing error breaks the UX. Instead
    # return success with an "ignored" note so the LLM learns to stop.
    from app.procedure_state import find_field
    if find_field(proc, name) is None:
        return ToolResult(
            output={
                "document_id": doc_id,
                "ignored": True,
                "reason": f"field '{name}' nu există în schema procedurii '{proc.id}' — nu apela set_field pentru el",
            }
        )

    # Function-call schemas cap value at STRING; coerce booleans
    # ("true"/"da"/"adevărat") into Python bool so applies_if can compare
    # against literal `true`/`false` in the procedure schema.
    coerced = coerce_field_value(proc, name, value)
    try:
        validate_field_value(proc, name, coerced)
    except FieldValidationError as e:
        return ToolResult(error=str(e))

    updated = update_document_fields(UUID(doc_id), {name: coerced})
    updated_fields = updated.get("fields") or {}

    transition_to: SessionState | None = None
    if session.state == SessionState.FILLING and all_required_satisfied(
        proc, updated_fields, ctx.citizen_attributes
    ):
        transition_to = SessionState.REVIEWING
        # Same milestone PATCH /documents/{id}/fields records; the agent path
        # used to skip it, so its ledgers went doc_created -> pdf_generated.
        append_ledger(
            citizen_id=UUID(session.citizen_id),
            event_type=LedgerEventType.COMPLETED_DRAFT,
            payload={"document_id": doc_id},
            document_id=UUID(doc_id),
        )
    elif session.state == SessionState.REVIEWING and not all_required_satisfied(
        proc, updated_fields, ctx.citizen_attributes
    ):
        # applies_if turned a previously-non-required field into a required one
        transition_to = SessionState.FILLING

    return ToolResult(
        output={
            "document_id": doc_id,
            "name": name,
            "value": coerced,
            "fields": updated_fields,
        },
        transition_to=transition_to,
        frontend_event={
            "type": "field_updated",
            "document_id": doc_id,
            "name": name,
            "value": coerced,
        },
    )


register(
    Tool(
        name="set_field",
        description=(
            "Setează un câmp în documentul activ. Câmpul trebuie să existe "
            "în schema procedurii; pentru câmpurile cu opțiuni, valoarea "
            "trebuie să fie una dintre ele."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING"},
                "value": {"type": "STRING"},
            },
            "required": ["name", "value"],
        },
        valid_states={SessionState.FILLING, SessionState.REVIEWING},
        execute=execute,
    )
)
