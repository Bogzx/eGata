"""Agent tool registry.

Each tool is a callable with a typed signature. The same Python function is
invoked from two contexts:
- The conversational agent loop (server-side, /agent/chat).
- HTTP endpoint dispatched by browser when Gemini Live emits a function-call.

Both paths go through the same function so behavior cannot drift.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeAlias

ToolFunc: TypeAlias = Callable[..., Awaitable[Any]]


@dataclass
class ToolContext:
    """Per-invocation context.

    Built from JWT for browser path, or from the agent's session state for
    server path. Phone callers get a synthetic ctx with ``citizen_id="phone-anonymous"``.
    """

    citizen_id: str
    document_id: str | None


REGISTRY: dict[str, ToolFunc] = {}


def register(name: str) -> Callable[[ToolFunc], ToolFunc]:
    def deco(func: ToolFunc) -> ToolFunc:
        REGISTRY[name] = func
        return func

    return deco


# Importing the modules below registers each tool via @register.
from app.tools import (  # noqa: E402, F401
    deliver as _deliver_mod,
    find_redirect as _find_redirect_mod,
    generate_pdf as _generate_pdf_mod,
    lookup_procedure as _lookup_procedure_mod,
    set_field as _set_field_mod,
    set_reminder as _set_reminder_mod,
)
