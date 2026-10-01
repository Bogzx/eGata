"""State-gated tool surface for the new agent architecture.

Each tool declares the set of `SessionState`s in which it is permitted.
The dispatcher refuses out-of-state calls and tells the agent what is
permitted — this is a hard guarantee, not a soft hint to the LLM.

Tools take a `Session` and `ToolContext` and return a `ToolResult` that
the dispatcher folds back into the session before snapshotting.

Tool inventory: seven tools, permitted per state
(tests/test_agent_guardrails.py pins this matrix):

  tool                exploring  confirming_match  filling  reviewing  delivered  redirected
  ──────────────────────────────────────────────────────────────────────────────────────────
  lookup_procedure        ✓             ✓                                  ✓          ✓
  list_procedures         ✓             ✓                                  ✓          ✓
  find_redirect           ✓             ✓                                  ✓          ✓
  start_procedure                       ✓                                  ✓
  propose_widget                        ✓             ✓         ✓
  set_field                                           ✓         ✓
  complete_document                                             ✓

`find_redirect` is intentionally OFF during FILLING/REVIEWING: a mid-fill
mention ("vreau și impozit cândva") must not flip the session to
REDIRECTED and abandon the draft. The agent can still reply with text
about the right institution; it just can't fire the tool that mutates
state. Same logic for `lookup_procedure` — no procedure switch mid-fill;
the user has to explicitly abandon first.

The dispatcher is `dispatch(session, name, args, ctx)`. It validates
state, validates args (via Pydantic), executes, and returns the result
+ mutated session.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.sessions import Session, SessionState

log = logging.getLogger("agent_tools")


def _summarize(value: Any, max_len: int = 120) -> str:
    """Compact preview of an arg/output dict for log lines.

    Full repr blows up the log when fields contain RAG payloads. Truncate.
    """
    s = repr(value)
    return s if len(s) <= max_len else s[:max_len] + f"...<{len(s) - max_len}b>"


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
    parameters: dict[str, Any]  # JSON-schema; normalized by azure_clients before being sent to the model
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
    log.info(
        "dispatch: in conv=%s tool=%s state=%s args=%s",
        session.id,
        name,
        session.state.value,
        _summarize(args),
    )
    started = time.perf_counter()
    tool = REGISTRY.get(name)
    if tool is None:
        # A model can name a tool that does not exist. Refuse it like an
        # out-of-state call, so the turn goes on and the model hears what it
        # may call, instead of the exception ending the turn (text) or the
        # call (voice).
        log.warning("dispatch: unknown tool conv=%s tool=%s", session.id, name)
        return ToolResult(
            error=(
                f"Tool {name!r} does not exist; "
                f"permitted now: {permitted_tools(session.state)}"
            )
        )
    if session.state not in tool.valid_states:
        msg = (
            f"Tool {name!r} not permitted in state {session.state.value!r}; "
            f"permitted: {[s.value for s in tool.valid_states]}"
        )
        log.warning(
            "dispatch: state-gated conv=%s tool=%s state=%s permitted=%s",
            session.id,
            name,
            session.state.value,
            [s.value for s in tool.valid_states],
        )
        return ToolResult(error=msg)

    try:
        result = await tool.execute(session, ctx, **args)
    except Exception as e:  # noqa: BLE001
        log.exception(
            "dispatch: tool raised conv=%s tool=%s args=%s",
            session.id,
            name,
            _summarize(args),
        )
        return ToolResult(error=str(e))

    if result.transition_to is not None:
        from app.sessions import transition  # local import to avoid cycle
        try:
            prev_state = session.state.value
            transition(session, result.transition_to)
            log.info(
                "dispatch: transition conv=%s tool=%s %s -> %s",
                session.id,
                name,
                prev_state,
                session.state.value,
            )
        except Exception as e:  # noqa: BLE001
            log.warning(
                "dispatch: illegal transition conv=%s tool=%s %s -> %s err=%s",
                session.id,
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

    log.info(
        "dispatch: out conv=%s tool=%s duration_ms=%.0f error=%s output=%s fe_event=%s",
        session.id,
        name,
        (time.perf_counter() - started) * 1000,
        result.error,
        _summarize(result.output),
        (result.frontend_event or {}).get("type"),
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
