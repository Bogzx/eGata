"""What the model cannot do, whatever it says.

These tests replace Azure OpenAI with a scripted model that makes the calls
a confused or manipulated LLM would make, and run them through the real
`session_engine.step`, the real dispatcher and the real tools. Every function
that would write something (documents, ledger, PDF, storage, SMS) is patched
to fail the test if it is reached, so "refused" means refused before any side
effect, not cleaned up afterwards.

The guarantees, and where each one lives:

  1. The model is only offered the tools its state permits
     (`session_engine._tools_for_state`).
  2. A call outside them is refused anyway (`agent_tools.dispatch`), so a
     model that names a tool it was not offered gets nowhere.
  3. A tool that does not exist is refused the same way, and the turn goes on.
  4. The delivery picker cannot be shown before the citizen confirmed the
     filled form (`propose_widget`, review gate on the session row).
  5. `complete_document` cannot run in the turn that asks the citizen how to
     deliver, on a delivery the model chose (`complete_document`).
  6. The phone bridge only ever dispatches read-only tools
     (`twilio_bridge.PHONE_TOOL_ALLOWLIST`).

Ownership (a conversation or document of another citizen) is enforced at the
transport, before the model runs: see test_conversation_ownership.py.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from app import session_engine
from app.agent_tools import permitted_tools
from app.config import get_settings
from app.sessions import PendingWidget, Session, SessionState

DOC_ID = "11111111-2222-3333-4444-555555555555"

# Every state, and exactly what it permits. A change here is a change to what
# the model can do, so it should be a deliberate one.
EXPECTED_TOOLS: dict[SessionState, set[str]] = {
    SessionState.EXPLORING: {"lookup_procedure", "list_procedures", "find_redirect"},
    SessionState.CONFIRMING_MATCH: {
        "lookup_procedure", "list_procedures", "find_redirect",
        "start_procedure", "propose_widget",
    },
    SessionState.FILLING: {"propose_widget", "set_field"},
    SessionState.REVIEWING: {"propose_widget", "set_field", "complete_document"},
    SessionState.DELIVERED: {
        "lookup_procedure", "list_procedures", "find_redirect", "start_procedure",
    },
    SessionState.REDIRECTED: {"lookup_procedure", "list_procedures", "find_redirect"},
}

_SIDE_EFFECTS = [
    "app.agent_tools.start_procedure.insert_document",
    "app.agent_tools.start_procedure.update_document_fields",
    "app.agent_tools.start_procedure.append_ledger",
    "app.agent_tools.set_field.fetch_document",
    "app.agent_tools.set_field.update_document_fields",
    "app.agent_tools.set_field.append_ledger",
    "app.agent_tools.complete_document.fetch_document",
    "app.agent_tools.complete_document.render_and_compile",
    "app.agent_tools.complete_document.upload_pdf_to_storage",
    "app.agent_tools.complete_document.set_document_pdf_url",
    "app.agent_tools.complete_document.finalize_document",
    "app.agent_tools.complete_document.append_ledger",
    "app.agent_tools.complete_document.send_delivery_sms",
]


class ScriptedModel:
    """Stands in for AsyncAzureOpenAI. Each completion call returns the next
    scripted reply (a tool call or text) and records the tools it was offered.
    Once the script runs out it answers with text, which ends the turn."""

    def __init__(self, *replies: dict[str, Any]) -> None:
        self.replies = list(replies)
        self.offered: list[set[str]] = []
        self.tool_messages: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any) -> AsyncIterator[Any]:
        self.offered.append({t["function"]["name"] for t in kwargs.get("tools") or []})
        self.tool_messages = [m for m in kwargs["messages"] if m.get("role") == "tool"]
        reply = self.replies.pop(0) if self.replies else {"text": "Bine."}
        return _stream(reply)


async def _stream(reply: dict[str, Any]) -> AsyncIterator[Any]:
    if "tool" in reply:
        name, args = reply["tool"]
        fn = SimpleNamespace(name=name, arguments=json.dumps(args))
        tc = SimpleNamespace(index=0, id="call_1", function=fn)
        delta = SimpleNamespace(content=None, tool_calls=[tc])
        finish = "tool_calls"
    else:
        delta = SimpleNamespace(content=reply["text"], tool_calls=None)
        finish = "stop"
    yield SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish)])


@pytest.fixture(autouse=True)
def _llm_backend(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AGENT_BACKEND", "azure")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-never-used")
    get_settings.cache_clear()
    # The per-turn preamble reads the active document; give it a draft.
    monkeypatch.setattr(
        session_engine,
        "fetch_document",
        lambda _id: {"procedure_id": "schimbare-domiciliu", "status": "draft", "fields": {}},
    )
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def side_effects(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    reached: list[str] = []

    def sink(target: str) -> Any:
        def _fail(*_a: Any, **_k: Any) -> Any:
            reached.append(target)
            raise AssertionError(f"side effect reached: {target}")

        return _fail

    for target in _SIDE_EFFECTS:
        monkeypatch.setattr(target, sink(target))
    return reached


def _session(state: SessionState, **kw: Any) -> Session:
    doc = None if state in {SessionState.EXPLORING, SessionState.REDIRECTED} else DOC_ID
    return Session(id="sess_guard", citizen_id="c-1", state=state, active_document_id=doc, **kw)


def _turn(session: Session, model: ScriptedModel) -> list[Any]:
    async def run() -> list[Any]:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(session_engine, "get_openai_client", lambda: model)
            return [
                ev
                async for ev in session_engine.step(
                    session, "…", citizen_attrs={"nume_complet": "Maria Ionescu"}
                )
            ]

    return asyncio.run(run())


def _results(events: list[Any]) -> list[dict[str, Any]]:
    return [ev.data for ev in events if ev.kind == "tool_result"]


# ---- 1. what the model is offered ----


def test_registry_matches_the_reviewed_matrix() -> None:
    for state, tools in EXPECTED_TOOLS.items():
        assert set(permitted_tools(state)) == tools, state


@pytest.mark.parametrize("state", list(SessionState))
def test_model_is_offered_only_what_its_state_permits(state: SessionState) -> None:
    model = ScriptedModel({"text": "Bună ziua."})
    _turn(_session(state), model)
    assert model.offered == [EXPECTED_TOOLS[state]]


# ---- 2. and refused anything else ----

OUT_OF_STATE = [
    # Deliver without ever filling anything.
    (SessionState.EXPLORING, "complete_document", {"delivery": "save"}),
    # Write a field with no document opened through the confirm step.
    (SessionState.EXPLORING, "set_field", {"name": "cnp", "value": "1900512123456"}),
    # Open a document without the citizen confirming the match.
    (SessionState.EXPLORING, "start_procedure", {"procedure_id": "schimbare-domiciliu"}),
    # Skip the review and deliver mid-fill.
    (SessionState.FILLING, "complete_document", {"delivery": "send"}),
    # Abandon the draft for another procedure, or another institution, mid-fill.
    (SessionState.FILLING, "lookup_procedure", {"query": "impozit"}),
    (SessionState.REVIEWING, "find_redirect", {"query": "ANAF"}),
    # Edit a document after it was delivered (it is frozen).
    (SessionState.DELIVERED, "set_field", {"name": "adresa_noua", "value": "Str. Alta 1"}),
    (SessionState.DELIVERED, "complete_document", {"delivery": "save"}),
]


@pytest.mark.parametrize(("state", "tool", "args"), OUT_OF_STATE)
def test_call_outside_the_state_is_refused_before_any_side_effect(
    state: SessionState, tool: str, args: dict[str, Any], side_effects: list[str]
) -> None:
    session = _session(state)
    model = ScriptedModel({"tool": (tool, args)}, {"text": "Am înțeles."})
    events = _turn(session, model)

    [result] = _results(events)
    assert result["name"] == tool
    assert "not permitted" in result["error"]
    assert session.state is state
    assert session.active_document_id == _session(state).active_document_id
    assert side_effects == []
    # The refusal reaches the model, which then answers in text.
    assert "not permitted" in model.tool_messages[0]["content"]
    assert any(ev.kind == "delta" and "Am înțeles." in ev.data["text"] for ev in events)


def test_a_tool_that_does_not_exist_is_refused_and_the_turn_goes_on(
    side_effects: list[str],
) -> None:
    session = _session(SessionState.REVIEWING)
    model = ScriptedModel(
        {"tool": ("submit_to_primarie", {"document_id": DOC_ID})}, {"text": "Nu pot face asta."}
    )
    events = _turn(session, model)

    [result] = _results(events)
    assert "does not exist" in result["error"]
    assert session.state is SessionState.REVIEWING
    assert not any(ev.kind == "error" for ev in events)
    assert side_effects == []


# ---- 3. gates inside permitted tools ----


def test_delivery_picker_needs_the_citizen_to_confirm_the_form_first() -> None:
    session = _session(SessionState.REVIEWING, review_confirmed=False)
    model = ScriptedModel(
        {
            "tool": (
                "propose_widget",
                {
                    "type": "choice",
                    "question": "Cum vrei să primești cererea completată?",
                    "options": ["Salvare PDF", "Tipărire"],
                },
            )
        }
    )
    events = _turn(session, model)

    [result] = _results(events)
    assert result["output"].get("refused") is True
    assert session.pending_widgets == []
    assert session.state is SessionState.REVIEWING


def test_document_is_not_completed_in_the_turn_that_asks_how_to_deliver(
    side_effects: list[str],
) -> None:
    """The model shows the delivery choice and, without waiting for the
    citizen, completes the document with a delivery it picked itself."""
    session = _session(SessionState.REVIEWING, review_confirmed=True)
    model = ScriptedModel(
        {
            "tool": (
                "propose_widget",
                {
                    "type": "choice",
                    "question": "Cum vrei să primești cererea completată?",
                    "options": ["Salvare PDF", "Tipărire"],
                },
            )
        },
        {"tool": ("complete_document", {"delivery": "save"})},
    )
    events = _turn(session, model)

    proposed, completed = _results(events)
    assert proposed["error"] is None and not proposed["output"].get("refused")
    assert completed["output"].get("refused") is True
    assert session.state is SessionState.REVIEWING
    assert [w.question for w in session.pending_widgets] == [
        "Cum vrei să primești cererea completată?"
    ]
    assert side_effects == []


def test_a_new_chat_turn_forgets_widgets_the_browser_hid() -> None:
    """Typing hides every open widget in the browser; the server must not
    keep waiting on them (or refuse to ask the same question again)."""
    session = _session(
        SessionState.FILLING,
        pending_widgets=[
            PendingWidget(
                widget_id="w1",
                type="choice",
                question="Tip proprietate",
                options=["proprietar", "chiriaș"],
                target_field="tip_proprietate",
            )
        ],
    )
    model = ScriptedModel(
        {
            "tool": (
                "propose_widget",
                {
                    "type": "choice",
                    "question": "Tip proprietate",
                    "options": ["proprietar", "chiriaș"],
                    "target_field": "tip_proprietate",
                },
            )
        }
    )
    events = _turn(session, model)

    [result] = _results(events)
    assert result["error"] is None and not result["output"].get("refused")
    assert [w.widget_id for w in session.pending_widgets] != ["w1"]
    assert len(session.pending_widgets) == 1


# ---- 4. the phone bridge ----


def test_phone_sessions_can_only_read() -> None:
    from app.twilio_bridge import PHONE_TOOL_ALLOWLIST

    writes = {"start_procedure", "set_field", "complete_document", "propose_widget"}
    assert {"lookup_procedure", "find_redirect"} == PHONE_TOOL_ALLOWLIST
    assert not PHONE_TOOL_ALLOWLIST & writes
