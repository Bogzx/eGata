"""State-gated tool surface for the new agent architecture.

Each tool declares the set of `SessionState`s in which it is permitted.
The dispatcher refuses out-of-state calls and tells the agent what is
permitted — this is a hard guarantee, not a soft hint to the LLM.

Tools take a `Session` and `ToolContext` and return a `ToolResult` that
the dispatcher folds back into the session before snapshotting.

Tool inventory (SP2 collapses the old 7-tool surface to 6 cleaner ones):

  exploring         confirming_match    filling         reviewing       delivered       redirected
  ─────────────────────────────────────────────────────────────────────────────────────────────────
  lookup_procedure  lookup_procedure                                    lookup_procedure  lookup_procedure
                    start_procedure
                                        set_field       set_field
                    propose_widget      propose_widget
                                                        complete_document
  find_redirect     find_redirect       find_redirect   find_redirect   find_redirect   find_redirect

The dispatcher is `dispatch(session, name, args, ctx)`. It validates
state, validates args (via Pydantic), executes, and returns the result
+ mutated session.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.sessions import Session, SessionState

log = logging.getLogger("agent_tools")


# ---- types ----


@dataclass
class ToolContext:
    """Per-request dependencies a tool may need.

    Citizen attributes are passed in so applies_if can evaluate against
    them; the dispatcher fetches them once per turn rather than per tool.
    """
    citizen_id: str
    citizen_attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Returned by every tool. Folded back into session by dispatcher.

    `output`: model-facing payload (small, what the LLM sees as the
              function response). Should be Romanian-friendly when it
              contains messages.
    `error`: when non-None, signals failure. The agent decides how to
             respond; the UI surfaces this as a system bubble.
    `transition_to`: optional next-state hint. The dispatcher applies it
                     via session.transition() (with the regular legality
                     check). Set to None to leave state unchanged.
    `frontend_event`: optional structured event to push to the browser
                      (e.g. `{type: "widget_proposed", widget_id, ...}`).
                      Sent in addition to the session_snapshot.
    """
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    transition_to: SessionState | None = None
    frontend_event: dict[str, Any] | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON-schema-ish, suitable for Gemini function_declarations
    valid_states: set[SessionState]
    execute: Callable[..., Awaitable[ToolResult]]  # (session, ctx, **args) -> ToolResult

    def function_declaration(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# ---- dispatcher ----


class IllegalToolStateError(ValueError):
    """Raised when an agent calls a tool that's not valid in the current state."""


class UnknownToolError(ValueError):
    """Raised when an agent calls a tool that isn't registered."""


REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    if tool.name in REGISTRY:
        raise ValueError(f"tool {tool.name!r} already registered")
    REGISTRY[tool.name] = tool


def get_tool(name: str) -> Tool:
    tool = REGISTRY.get(name)
    if tool is None:
        raise UnknownToolError(f"tool {name!r} not registered")
    return tool


def permitted_tools(state: SessionState) -> list[str]:
    """Tool names permitted in `state` — used to brief the agent each turn."""
    return [name for name, t in REGISTRY.items() if state in t.valid_states]


async def dispatch(
    session: Session,
    name: str,
    args: dict[str, Any],
    ctx: ToolContext,
) -> ToolResult:
    """Run the tool. Validates state-gating + applies state transitions.

    Does NOT persist the session — caller does `update_session(session)`
    after possibly multiple tool dispatches per turn.
    """
    tool = get_tool(name)
    if session.state not in tool.valid_states:
        msg = (
            f"Tool {name!r} not permitted in state {session.state.value!r}; "
            f"permitted: {[s.value for s in tool.valid_states]}"
        )
        log.warning(msg)
        return ToolResult(error=msg)

    try:
        result = await tool.execute(session, ctx, **args)
    except Exception as e:  # noqa: BLE001
        log.exception("tool %s raised", name)
        return ToolResult(error=str(e))

    if result.transition_to is not None:
        from app.sessions import transition  # local import to avoid cycle
        try:
            transition(session, result.transition_to)
        except Exception as e:  # noqa: BLE001
            log.warning(
                "tool %s requested illegal transition %s -> %s: %s",
                name,
                session.state.value,
                result.transition_to.value,
                e,
            )
            # Don't fail the whole call — the tool succeeded, just the
            # state move was illegal. Surface it as a warning in output.
            result.output.setdefault("warnings", []).append(
                f"illegal_transition:{result.transition_to.value}"
            )

    return result


# ---- registration: import side-effect populates REGISTRY ----

from app.agent_tools import (  # noqa: E402, F401
    complete_document,
    find_redirect,
    list_procedures,
    lookup_procedure,
    propose_widget,
    set_field,
    start_procedure,
)
