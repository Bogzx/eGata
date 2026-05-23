"""propose_widget — a UI directive tool.

The agent calls this to ask a structured question that the browser renders as
an inline chat widget (choice buttons, yes/no, date picker). Server-side this
is a near-no-op: validate the args and return an ack with a widget_id.

NOT included in PHONE_TOOL_ALLOWLIST — phone has no UI to render widgets.
"""
from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel

from app.tools import ToolContext, register


_ALLOWED_TYPES = {"choice", "confirm", "date"}


class WidgetResult(BaseModel):
    acknowledged: bool = True
    widget_id: str
    type: str
    question: str
    options: list[str] = []
    target_field: str | None = None


@register("propose_widget")
async def propose_widget(
    ctx: ToolContext,  # noqa: ARG001 — required by registry convention
    type: str,
    question: str,
    options: list[str] | None = None,
    target_field: str | None = None,
) -> WidgetResult:
    """Validate widget args and return an ack the frontend renders.

    Raises ValueError on invalid args so the dispatcher returns HTTP 400.
    """
    if type not in _ALLOWED_TYPES:
        raise ValueError(f"unknown widget type {type!r}; expected one of {sorted(_ALLOWED_TYPES)}")
    opts = options or []
    if type == "choice":
        if len(opts) < 2:
            raise ValueError("choice widget needs >= 2 options")
        if not target_field:
            raise ValueError("choice widget needs a target_field")
    if type == "date" and not target_field:
        raise ValueError("date widget needs a target_field")
    return WidgetResult(
        widget_id=str(uuid4()),
        type=type,
        question=question,
        options=opts,
        target_field=target_field,
    )
