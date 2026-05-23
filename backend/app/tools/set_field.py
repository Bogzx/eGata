"""set_field — patch a single form field on the active document."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.documents import fetch_document, update_document_fields
from app.procedures import get_registry
from app.tools import ToolContext, register


@register("set_field")
async def set_field(ctx: ToolContext, name: str, value: Any) -> dict[str, Any]:
    """Set one form field on the active document and return the updated doc."""
    if not ctx.document_id:
        raise ValueError("document_id required for set_field")

    doc = fetch_document(UUID(ctx.document_id))
    if str(doc["citizen_id"]) != ctx.citizen_id:
        raise ValueError("not your document")

    reg = get_registry()
    proc = reg.get(doc["procedure_id"])
    if proc is None:
        raise ValueError(f"Unknown procedure {doc['procedure_id']}")

    field_spec = next((f for f in proc.fields if f.name == name), None)
    if field_spec is None:
        raise ValueError(f"Unknown field '{name}' for procedure {doc['procedure_id']}")
    if field_spec.options and value not in field_spec.options:
        raise ValueError(
            f"Value {value!r} not in options for '{name}': {field_spec.options}"
        )

    updated = update_document_fields(UUID(ctx.document_id), {name: value})
    # Normalize uuid/datetime for JSON
    return {
        "id": str(updated["id"]),
        "citizen_id": str(updated["citizen_id"]),
        "procedure_id": updated["procedure_id"],
        "status": updated["status"],
        "fields": updated["fields"],
    }
