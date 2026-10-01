"""Dispatcher state-gating tests (no DB, no external services).

Tools that hit external services (lookup_procedure → embeddings,
complete_document → PDF) are exercised by integration tests once a test
DB + storage harness exists. Here we cover:

  - state-gated dispatch refuses out-of-state calls
  - transition_to is applied via session.transition()
  - illegal transitions don't fail the call, they degrade gracefully
  - permitted_tools() agrees with the per-tool valid_states sets
"""
from __future__ import annotations

import asyncio

import pytest

from app.agent_tools import (
    REGISTRY,
    Tool,
    ToolContext,
    ToolResult,
    UnknownToolError,
    dispatch,
    get_tool,
    permitted_tools,
    register,
)
from app.sessions import Session, SessionState


def _ctx() -> ToolContext:
    return ToolContext(citizen_id="cit_test", citizen_attributes={})


@pytest.fixture(autouse=True)
def _isolate_registry(monkeypatch):
    """Don't pollute the real registry from per-test fake tools."""
    snapshot = dict(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.update(snapshot)


def _register_fake(
    name: str = "fake_tool",
    valid: set[SessionState] | None = None,
    result: ToolResult | None = None,
) -> Tool:
    valid = valid or {SessionState.FILLING}
    result = result if result is not None else ToolResult(output={"ok": True})

    async def execute(session, ctx, **kwargs):  # noqa: ARG001
        return result

    tool = Tool(
        name=name,
        description=f"fake {name}",
        parameters={"type": "OBJECT", "properties": {}},
        valid_states=valid,
        execute=execute,
    )
    register(tool)
    return tool


def test_dispatch_refuses_out_of_state() -> None:
    _register_fake("only_filling", valid={SessionState.FILLING})
    sess = Session(id="s", citizen_id="c", state=SessionState.EXPLORING)
    result = asyncio.run(dispatch(sess, "only_filling", {}, _ctx()))
    assert result.error is not None
    assert "not permitted" in result.error.lower()
    assert sess.state is SessionState.EXPLORING  # unchanged


def test_dispatch_runs_when_in_state() -> None:
    _register_fake(
        "happy",
        valid={SessionState.FILLING},
        result=ToolResult(output={"done": True}),
    )
    sess = Session(id="s", citizen_id="c", state=SessionState.FILLING)
    result = asyncio.run(dispatch(sess, "happy", {}, _ctx()))
    assert result.error is None
    assert result.output == {"done": True}


def test_dispatch_applies_transition_to() -> None:
    _register_fake(
        "advances",
        valid={SessionState.FILLING},
        result=ToolResult(transition_to=SessionState.REVIEWING),
    )
    sess = Session(id="s", citizen_id="c", state=SessionState.FILLING)
    asyncio.run(dispatch(sess, "advances", {}, _ctx()))
    assert sess.state is SessionState.REVIEWING


def test_dispatch_swallows_illegal_transition_gracefully() -> None:
    _register_fake(
        "skips_ahead",
        valid={SessionState.FILLING},
        # filling → delivered is illegal in the state machine
        result=ToolResult(
            output={"computed": 42},
            transition_to=SessionState.DELIVERED,
        ),
    )
    sess = Session(id="s", citizen_id="c", state=SessionState.FILLING)
    result = asyncio.run(dispatch(sess, "skips_ahead", {}, _ctx()))
    assert result.error is None  # tool succeeded
    assert sess.state is SessionState.FILLING  # but transition didn't happen
    assert "illegal_transition:delivered" in result.output.get("warnings", [])


def test_get_tool_unknown_raises() -> None:
    with pytest.raises(UnknownToolError):
        get_tool("no_such_tool")


def test_dispatch_refuses_unknown_tool_without_raising() -> None:
    """A hallucinated tool name is a refusal the model can recover from, not
    an exception that ends the turn."""
    sess = Session(id="s", citizen_id="c", state=SessionState.EXPLORING)
    result = asyncio.run(dispatch(sess, "no_such_tool", {}, _ctx()))
    assert result.error is not None and "does not exist" in result.error
    assert sess.state is SessionState.EXPLORING


def test_dispatch_catches_tool_exception() -> None:
    async def boom(session, ctx, **kwargs):  # noqa: ARG001
        raise RuntimeError("kaboom")

    register(
        Tool(
            name="boom",
            description="explodes",
            parameters={"type": "OBJECT", "properties": {}},
            valid_states={SessionState.EXPLORING},
            execute=boom,
        )
    )
    sess = Session(id="s", citizen_id="c", state=SessionState.EXPLORING)
    result = asyncio.run(dispatch(sess, "boom", {}, _ctx()))
    assert result.error == "kaboom"


def test_permitted_tools_per_state_matches_registry() -> None:
    # the real tools registered at import time
    permitted_filling = set(permitted_tools(SessionState.FILLING))
    permitted_reviewing = set(permitted_tools(SessionState.REVIEWING))

    assert "set_field" in permitted_filling
    assert "set_field" in permitted_reviewing
    assert "complete_document" in permitted_reviewing
    assert "complete_document" not in permitted_filling
    assert "start_procedure" not in permitted_filling
    assert "lookup_procedure" not in permitted_filling


def test_real_tool_registry_complete() -> None:
    expected = {
        "lookup_procedure",
        "start_procedure",
        "set_field",
        "propose_widget",
        "complete_document",
        "find_redirect",
    }
    assert expected.issubset(set(REGISTRY.keys()))
