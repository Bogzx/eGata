"""propose_widget — emit a structured UI prompt the frontend renders.

Server-side this:
  1. validates args (type, options for choice, target_field for choice/date)
  2. creates a PendingWidget on the session keyed by widget_id
  3. returns the widget_id; the frontend renders it and the user's
     response comes back via a `widget_result` event (SP4) which is
     translated to a `set_field` call by the bridge — the LLM never has
     to guess which field the value belongs to.

Valid states: FILLING (most common — ask the user a structured question),
CONFIRMING_MATCH (the agent asks "Confirmi procedura X?" via a confirm
widget after a lookup_procedure match).
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.agent_tools import Tool, ToolContext, ToolResult, register
from app.sessions import PendingWidget, Session, SessionState

_ALLOWED_TYPES = {"choice", "confirm", "date"}


async def execute(
    session: Session,
    ctx: ToolContext,
    type: str,
    question: str,
    options: list[str] | None = None,
    target_field: str | None = None,
) -> ToolResult:
    # Soft-skip invalid widget configurations: the LLM occasionally proposes
    # a `date` widget for free-form scheduling (no doc field to bind to) or
    # a `choice` with <2 options. Surfacing the validation error as a chat
    # pop-up breaks UX. Return an "ignored" output instead so the LLM
    # falls back to a plain text question.
    opts = options or []
    invalid_reason: str | None = None
    if type not in _ALLOWED_TYPES:
        invalid_reason = f"tip widget necunoscut {type!r}"
    elif type == "choice" and len(opts) < 2:
        invalid_reason = "type='choice' are nevoie de minim 2 opțiuni"
    elif type == "date" and not target_field:
        invalid_reason = (
            "type='date' are nevoie de target_field — folosit doar pentru "
            "a completa un câmp de tip dată în documentul activ"
        )
    if invalid_reason is not None:
        return ToolResult(
            output={
                "ignored": True,
                "reason": (
                    f"propose_widget skipped: {invalid_reason}. "
                    "Pune întrebarea direct în chat (răspuns text liber)."
                ),
            }
        )

    # Refuse a duplicate of an already-pending widget (same question text).
    # LLMs sometimes re-propose the same delivery-choice question twice
    # back-to-back; the first one is still waiting for the user. Silently
    # skip the duplicate so the user sees only one widget.
    for pending in session.pending_widgets:
        if pending.question.strip() == question.strip():
            return ToolResult(
                output={
                    "ignored": True,
                    "reason": (
                        f"duplicate: a widget with the same question is already "
                        f"pending (widget_id={pending.widget_id}). Așteaptă "
                        f"răspunsul cetățeanului, nu re-propune."
                    ),
                }
            )

    # target_field binds the widget answer to a document field via set_field.
    # set_field is only valid in FILLING/REVIEWING — there's no document to
    # write into during CONFIRMING_MATCH, so the combination is fatal if the
    # user clicks. Refuse it loudly so the model either calls start_procedure
    # first or drops target_field (a plain confirm/choice question whose
    # answer the model interprets in chat). `choice` without target_field is
    # the right primitive for "which of these procedures do you want?" in
    # CONFIRMING_MATCH.
    if target_field and session.state not in {
        SessionState.FILLING,
        SessionState.REVIEWING,
    }:
        return ToolResult(
            error=(
                f"target_field este permis doar în starea FILLING (sau REVIEWING). "
                f"Stare curentă: {session.state.value}. Pentru a alege între "
                f"proceduri folosește 'choice' fără target_field — răspunsul "
                f"ajunge la tine ca text și decizi ce procedură pornești. "
                f"Pentru confirmare directă folosește 'confirm' fără target_field, "
                f"apoi cheamă start_procedure."
            )
        )

    widget_id = uuid4().hex[:12]
    widget = PendingWidget(
        widget_id=widget_id,
        type=type,
        question=question,
        target_field=target_field,
        options=list(opts),
    )
    session.add_pending_widget(widget)

    return ToolResult(
        output={
            "widget_id": widget_id,
            "type": type,
            "question": question,
            "options": list(opts),
            "target_field": target_field,
        },
        frontend_event={
            "type": "widget_proposed",
            "widget_id": widget_id,
            "widget_type": type,
            "question": question,
            "options": list(opts),
            "target_field": target_field,
        },
    )


register(
    Tool(
        name="propose_widget",
        description=(
            "Trimite o întrebare structurată cetățeanului ca widget vizual "
            "(buton 'choice', 'confirm' Da/Nu, sau 'date' picker). "
            "Răspunsul revine ca eveniment structurat, nu ca text liber."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "type": {"type": "STRING", "enum": ["choice", "confirm", "date"]},
                "question": {"type": "STRING"},
                "options": {"type": "ARRAY", "items": {"type": "STRING"}},
                "target_field": {"type": "STRING"},
            },
            "required": ["type", "question"],
        },
        valid_states={SessionState.FILLING, SessionState.CONFIRMING_MATCH, SessionState.REVIEWING},
        execute=execute,
    )
)
