"""State-machine unit tests for app.sessions.

DB-independent — covers the pure transition logic + dataclass behavior.
DB-backed CRUD is exercised by an integration test elsewhere once a test
Postgres is wired up.
"""
from __future__ import annotations

import pytest

from app.sessions import (
    IllegalTransitionError,
    PendingWidget,
    Session,
    SessionState,
    can_transition,
    transition,
)


def test_initial_state_is_exploring():
    s = Session(id="sess_x", citizen_id="abc")
    assert s.state is SessionState.EXPLORING


def test_happy_path_through_state_machine():
    s = Session(id="sess_x", citizen_id="abc")
    transition(s, SessionState.CONFIRMING_MATCH)
    transition(s, SessionState.FILLING)
    transition(s, SessionState.REVIEWING)
    transition(s, SessionState.DELIVERED)
    assert s.state is SessionState.DELIVERED


def test_scenario_continuation_from_delivered():
    s = Session(id="sess_x", citizen_id="abc", state=SessionState.DELIVERED)
    transition(s, SessionState.CONFIRMING_MATCH)
    assert s.state is SessionState.CONFIRMING_MATCH


def test_scenario_chain_skips_confirm_from_delivered():
    """start_procedure on a scenario step 2 jumps DELIVERED → FILLING."""
    s = Session(id="sess_x", citizen_id="abc", state=SessionState.DELIVERED)
    transition(s, SessionState.FILLING)
    assert s.state is SessionState.FILLING


def test_legacy_doc_injection_exploring_to_filling():
    """Frontend's startProcedure REST path jumps EXPLORING → FILLING directly."""
    s = Session(id="sess_x", citizen_id="abc")
    transition(s, SessionState.FILLING)
    assert s.state is SessionState.FILLING


def test_filling_to_delivered_is_illegal():
    s = Session(id="sess_x", citizen_id="abc", state=SessionState.FILLING)
    with pytest.raises(IllegalTransitionError):
        transition(s, SessionState.DELIVERED)


def test_exploring_to_delivered_is_illegal():
    s = Session(id="sess_x", citizen_id="abc")
    with pytest.raises(IllegalTransitionError):
        transition(s, SessionState.DELIVERED)


def test_reviewing_back_to_filling_for_applies_if_changes():
    """When applies_if turns a field required again, reviewing -> filling."""
    s = Session(id="sess_x", citizen_id="abc", state=SessionState.REVIEWING)
    transition(s, SessionState.FILLING)
    assert s.state is SessionState.FILLING


def test_redirected_is_terminal_except_re_exploring():
    assert can_transition(SessionState.REDIRECTED, SessionState.EXPLORING)
    assert not can_transition(SessionState.REDIRECTED, SessionState.FILLING)


def test_self_loops_are_explicit():
    """Every state must be able to "no-op" — useful for tool no-state-change cases."""
    for st in SessionState:
        assert can_transition(st, st), f"missing self-loop on {st}"


def test_snapshot_excludes_history_but_includes_widgets():
    s = Session(
        id="sess_x",
        citizen_id="abc",
        history=[{"role": "user", "parts": [{"text": "salut"}]}],
        pending_widgets=[
            PendingWidget(
                widget_id="w1",
                type="choice",
                question="Ce vrei?",
                target_field="tip",
                options=["a", "b"],
            )
        ],
    )
    snap = s.snapshot()
    assert "history" not in snap
    assert snap["pending_widgets"][0]["widget_id"] == "w1"
    assert snap["pending_widgets"][0]["target_field"] == "tip"
    assert snap["pending_widgets"][0]["options"] == ["a", "b"]


def test_resolve_pending_widget_pops():
    s = Session(id="sess_x", citizen_id="abc")
    s.add_pending_widget(
        PendingWidget(widget_id="w1", type="confirm", question="?")
    )
    s.add_pending_widget(
        PendingWidget(widget_id="w2", type="date", question="când?")
    )
    found = s.resolve_pending_widget("w1")
    assert found is not None
    assert found.widget_id == "w1"
    assert len(s.pending_widgets) == 1
    assert s.pending_widgets[0].widget_id == "w2"


def test_resolve_pending_widget_missing_returns_none():
    s = Session(id="sess_x", citizen_id="abc")
    assert s.resolve_pending_widget("nope") is None
