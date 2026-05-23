"""deliver — finalize document, choose delivery channel, write ledger event."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.documents import (
    fetch_document,
    fetch_phone_for_citizen,
    finalize_document,
    generate_ref_number,
    send_delivery_sms,
)
from app.ledger import LedgerEventType, append_ledger
from app.tools import ToolContext, register

_VALID = {"save", "send", "print"}


@register("deliver")
async def deliver(ctx: ToolContext, delivery: str) -> dict[str, Any]:
    """Finalize document. ``delivery`` must be one of save/send/print."""
    if not ctx.document_id:
        raise ValueError("document_id required for deliver")
    if delivery not in _VALID:
        raise ValueError(f"delivery must be one of {_VALID}, got {delivery!r}")

    doc_uuid = UUID(ctx.document_id)
    citizen_uuid = UUID(ctx.citizen_id)
    doc = fetch_document(doc_uuid)
    if str(doc["citizen_id"]) != ctx.citizen_id:
        raise ValueError("not your document")

    ref_number = generate_ref_number(doc_uuid)
    finalized = finalize_document(doc_uuid, delivery, ref_number)

    append_ledger(
        citizen_id=citizen_uuid,
        event_type=LedgerEventType.DELIVERED,
        payload={
            "document_id": ctx.document_id,
            "delivery": delivery,
            "ref_number": ref_number,
        },
        document_id=doc_uuid,
    )

    if delivery == "send":
        phone = fetch_phone_for_citizen(citizen_uuid)
        send_delivery_sms(phone, ref_number)

    return {
        "id": str(finalized["id"]),
        "status": finalized["status"],
        "delivery": finalized["delivery"],
        "ref_number": finalized["ref_number"],
    }
