"""Integration tests for session_engine.step() across multiple turns.

The pure state-machine tests live in test_sessions_state_machine.py; the
dispatcher tests in test_agent_tools_dispatch.py. What was missing — and
why "after the 2nd message" regressions slipped through — was a test that
runs step() back-to-back on the SAME Session with the real
history-rehydration path and verifies that:

  - the user/model turns persist into session.history each turn
  - serialized history round-trips through Pydantic without dropping
    function_call / function_response parts
  - state transitions requested by tools are applied
  - a second turn rehydrates the first turn's contents AND adds its own
  - the cumulative `transcript_so_far` correctly preserves preamble text
    across a tool-loop iteration

Gemini's `client.aio.models.generate_content_stream` is mocked: we hand
the engine canned chunks per turn so the tests don't burn quota and are
deterministic.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai import types as gt

from app.session_engine import Event, _content_to_dict, _history_to_contents, step
from app.sessions import Session, SessionState


# ---------- helpers ----------


def _chunk(parts: list[gt.Part], finish: str = "STOP") -> gt.GenerateContentResponse:
    return gt.GenerateContentResponse(
        candidates=[
            gt.Candidate(
                content=gt.Content(role="model", parts=parts),
                finish_reason=finish,
            )
        ]
    )


def _text_chunk(text: str) -> gt.GenerateContentResponse:
    return _chunk([gt.Part.from_text(text=text)])


def _fc_chunk(name: str, args: dict[str, Any]) -> gt.GenerateContentResponse:
    return _chunk([gt.Part.from_function_call(name=name, args=args)])


async def _make_stream(chunks: list[gt.GenerateContentResponse]) -> AsyncIterator:
    for c in chunks:
        yield c


class _FakeGenAI:
    """Drop-in for client.aio.models. `stream_plan` is a list-of-lists:
    one inner list per generate_content_stream call (one per tool-loop
    iteration). Each inner list is the chunks for that call.

    The engine passes `contents` by reference and then mutates the list
    in place across the tool loop. We snapshot a copy at call time so
    assertions can inspect the state-at-call rather than the post-mutation
    state.
    """

    def __init__(self, stream_plan: list[list[gt.GenerateContentResponse]]):
        self._plan = list(stream_plan)
        self.calls: list[dict[str, Any]] = []

    async def generate_content_stream(self, **kwargs):
        snap = dict(kwargs)
        if "contents" in snap:
            snap["contents"] = list(snap["contents"])
        self.calls.append(snap)
        if not self._plan:
            raise AssertionError("FakeGenAI exhausted but engine asked for more")
        chunks = self._plan.pop(0)
        return _make_stream(chunks)


async def _drain(it) -> list[Event]:
    out: list[Event] = []
    async for ev in it:
        out.append(ev)
    return out


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


# ---------- tests ----------


def test_single_text_only_turn_persists_user_and_model():
    """Baseline: empty history → user msg → text-only model reply →
    session.history has the right shape."""
    sess = Session(id="s1", citizen_id="cit")
    fake = _FakeGenAI([[_text_chunk("Salut! Cu ce te ajut?")]])
    mock_client = MagicMock()
    mock_client.aio.models = fake

    with patch("app.session_engine._client", return_value=mock_client):
        events = _run(_drain(step(sess, "salut", citizen_attrs={})))

    kinds = [e.kind for e in events]
    assert kinds[0] == "session_snapshot"
    assert "delta" in kinds
    assert kinds[-1] == "done"
    done = events[-1]
    assert done.data["message"] == "Salut! Cu ce te ajut?"
    assert sess.history[0] == {"parts": [{"text": "salut"}], "role": "user"}
    assert sess.history[1] == {
        "parts": [{"text": "Salut! Cu ce te ajut?"}],
        "role": "model",
    }


def test_history_round_trip_preserves_function_call_parts():
    """The serialization that goes into session.history MUST round-trip
    a function_call Part. If this breaks, the next turn rehydrates a
    None function_call and the agent loses its tool history."""
    content = gt.Content(
        role="model",
        parts=[
            gt.Part.from_text(text="Caut..."),
            gt.Part.from_function_call(
                name="lookup_procedure", args={"query": "schimbare"}
            ),
        ],
    )
    serialized = _content_to_dict(content)
    [restored] = _history_to_contents([serialized])
    assert restored.role == "model"
    assert restored.parts[0].text == "Caut..."
    assert restored.parts[1].function_call is not None
    assert restored.parts[1].function_call.name == "lookup_procedure"
    assert restored.parts[1].function_call.args == {"query": "schimbare"}


def test_history_round_trip_preserves_function_response_parts():
    """Same for function_response — the tool-result turn the engine
    appends to contents after each dispatch."""
    content = gt.Content(
        role="user",
        parts=[
            gt.Part.from_function_response(
                name="lookup_procedure",
                response={"output": {"matches": []}, "error": None},
            )
        ],
    )
    [restored] = _history_to_contents([_content_to_dict(content)])
    assert restored.role == "user"
    fr = restored.parts[0].function_response
    assert fr is not None
    assert fr.name == "lookup_procedure"
    assert fr.response == {"output": {"matches": []}, "error": None}


def test_two_turns_rehydrate_first_turn_history():
    """Run step() twice on the same Session. Turn 2 must see Turn 1 in
    contents (this is what was untested before; if rehydration silently
    drops a Part, the model gets a stub history)."""
    sess = Session(id="s2", citizen_id="cit")
    fake = _FakeGenAI(
        [
            [_text_chunk("Salut!")],  # turn 1 reply
            [_text_chunk("Da, te ascult.")],  # turn 2 reply
        ]
    )
    mock_client = MagicMock()
    mock_client.aio.models = fake

    with patch("app.session_engine._client", return_value=mock_client):
        _run(_drain(step(sess, "salut", citizen_attrs={})))
        # By this point sess.history = [user1, model1].
        _run(_drain(step(sess, "vreau ajutor", citizen_attrs={})))

    # Second call's `contents` kwarg should have rehydrated turn 1 + new user.
    assert len(fake.calls) == 2
    second_contents = fake.calls[1]["contents"]
    assert len(second_contents) == 3, (
        "expected [user1, model1, user2] in turn 2's contents; "
        f"got {[c.role for c in second_contents]}"
    )
    assert second_contents[0].parts[0].text == "salut"
    assert second_contents[1].parts[0].text == "Salut!"
    assert second_contents[2].parts[0].text == "vreau ajutor"

    # And session.history grew correctly.
    assert len(sess.history) == 4
    assert sess.history[0]["parts"][0]["text"] == "salut"
    assert sess.history[3]["parts"][0]["text"] == "Da, te ascult."


def _patch_tool_execute(tool_name: str, fn):
    """The Tool instance in REGISTRY captured a reference to the original
    `execute` at import time, so patching the module attribute doesn't
    reach it. Swap the Tool's execute attribute directly."""
    from app.agent_tools import REGISTRY

    original = REGISTRY[tool_name].execute
    REGISTRY[tool_name].execute = fn
    return lambda: setattr(REGISTRY[tool_name], "execute", original)


def test_tool_call_transitions_state_and_continues():
    """A turn where the model calls a real tool (lookup_procedure) →
    iter 2 generates the post-tool text → session transitions to
    CONFIRMING_MATCH."""
    sess = Session(id="s3", citizen_id="11111111-1111-1111-1111-111111111111")

    async def fake_lookup(session, ctx, query):  # noqa: ARG001
        from app.agent_tools import ToolResult

        return ToolResult(
            output={
                "matches": [
                    {
                        "procedure_id": "schimbare-domiciliu",
                        "title": "Schimbare domiciliu",
                        "score": 0.9,
                        "description": "x",
                        "acte_necesare": [],
                    }
                ],
                "scenario_plan": None,
            },
            transition_to=SessionState.CONFIRMING_MATCH,
            frontend_event={"type": "lookup_returned"},
        )

    fake = _FakeGenAI(
        [
            [
                _text_chunk("Caut procedura..."),
                _fc_chunk("lookup_procedure", {"query": "schimbare"}),
            ],
            [_text_chunk("Schimbare domiciliu, confirmi?")],
        ]
    )
    mock_client = MagicMock()
    mock_client.aio.models = fake

    restore = _patch_tool_execute("lookup_procedure", fake_lookup)
    try:
        with patch("app.session_engine._client", return_value=mock_client):
            events = _run(
                _drain(step(sess, "vreau schimbare domiciliu", citizen_attrs={}))
            )
    finally:
        restore()

    kinds = [e.kind for e in events]
    assert "tool_call" in kinds
    assert "tool_result" in kinds
    assert "frontend_event" in kinds
    assert kinds[-1] == "done"
    assert sess.state == SessionState.CONFIRMING_MATCH
    # The cumulative transcript across both iterations should land in done.
    assert "Schimbare domiciliu" in events[-1].data["message"]


def test_transcript_so_far_preserves_preamble_across_tool_iteration():
    """B-3 (P0) from AUDIT_CHAT.md: a model preamble in iter 1 must NOT
    be replaced by iter 2's text. The final done message must contain
    both — concatenated, not just iter N."""
    sess = Session(id="s4", citizen_id="11111111-1111-1111-1111-111111111111")

    async def fake_lookup(session, ctx, query):  # noqa: ARG001
        from app.agent_tools import ToolResult

        return ToolResult(
            output={"matches": [], "scenario_plan": None},
            transition_to=SessionState.CONFIRMING_MATCH,
        )

    fake = _FakeGenAI(
        [
            [
                _text_chunk("Hai să mă uit."),
                _fc_chunk("lookup_procedure", {"query": "x"}),
            ],
            [_text_chunk(" Gata, am găsit ceva.")],
        ]
    )
    mock_client = MagicMock()
    mock_client.aio.models = fake

    restore = _patch_tool_execute("lookup_procedure", fake_lookup)
    try:
        with patch("app.session_engine._client", return_value=mock_client):
            events = _run(_drain(step(sess, "salut", citizen_attrs={})))
    finally:
        restore()

    final = events[-1].data["message"]
    assert "Hai să mă uit." in final, "iter 1 preamble dropped from done message"
    assert "Gata, am găsit ceva." in final, "iter 2 text missing from done"


def test_history_persists_user_turn_before_model_responds():
    """If the Gemini stream blows up mid-turn the engine emits an `error`
    event and returns — the transport's finally-block update_session()
    needs to persist the user's message so the next turn sees it.
    Pre-rewrite this was B-NEW-A in AUDIT_CHAT.md."""
    sess = Session(id="s5", citizen_id="cit")

    class _Boom:
        async def generate_content_stream(self, **kwargs):
            raise RuntimeError("gemini hiccup")

    mock_client = MagicMock()
    mock_client.aio.models = _Boom()

    with patch("app.session_engine._client", return_value=mock_client):
        events = _run(_drain(step(sess, "vreau ceva", citizen_attrs={})))

    assert events[-1].kind == "error"
    # CRITICAL: the user turn must have survived in session.history so the
    # transport can persist it. Otherwise the next /agent/chat/stream call
    # has no record of what the user just said.
    assert any(
        h.get("role") == "user"
        and h.get("parts", [{}])[0].get("text") == "vreau ceva"
        for h in sess.history
    )
