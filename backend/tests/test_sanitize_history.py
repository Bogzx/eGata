"""Unit tests for _sanitize_history_for_gemini.

Regression coverage for the "chat works once, then fails from turn 2"
bug: a previously-failed step persists a trailing user turn into
session.history; the next turn would send Gemini consecutive user→user
content, which Gemini rejects, freezing the chat. The sanitizer strips
trailing orphan turns before the contents go to Gemini and preserves
real user text by returning it for merge into the next user message.
"""
from __future__ import annotations

from app.session_engine import _sanitize_history_for_gemini


def _user(text: str) -> dict:
    return {"role": "user", "parts": [{"text": text}]}


def _model(text: str) -> dict:
    return {"role": "model", "parts": [{"text": text}]}


def _model_fc(name: str, args: dict) -> dict:
    return {
        "role": "model",
        "parts": [{"function_call": {"name": name, "args": args}}],
    }


def _function_response(name: str, response: dict) -> dict:
    return {
        "role": "user",
        "parts": [{"function_response": {"name": name, "response": response}}],
    }


def test_empty_history_passes_through():
    sanitized, leftover = _sanitize_history_for_gemini([])
    assert sanitized == []
    assert leftover is None


def test_clean_history_unchanged():
    history = [_user("salut"), _model("bună!"), _user("vreau X"), _model("ok!")]
    sanitized, leftover = _sanitize_history_for_gemini(history)
    assert sanitized == history
    assert leftover is None


def test_trailing_user_text_returned_as_leftover():
    """The persist-early at step()'s top means a failed turn leaves a
    naked user turn. We must NOT send it to Gemini, but we also must NOT
    lose the user's typed message — return it for merge into the new
    user prompt."""
    history = [_user("salut"), _model("bună!"), _user("vreau ceva")]
    sanitized, leftover = _sanitize_history_for_gemini(history)
    assert sanitized == [_user("salut"), _model("bună!")]
    assert leftover == "vreau ceva"


def test_trailing_function_response_dropped_silently():
    """A function_response sitting at the end means dispatch ran but the
    next-iteration Gemini call never happened. That payload is agent
    internals, not user data — drop without preserving."""
    history = [
        _user("caută schimbare domiciliu"),
        _model_fc("lookup_procedure", {"query": "schimbare"}),
        _function_response("lookup_procedure", {"matches": []}),
    ]
    sanitized, leftover = _sanitize_history_for_gemini(history)
    # All three trailing turns peel off (function_response → drop;
    # then model_fc orphan → drop; then user → leftover).
    assert sanitized == []
    assert leftover == "caută schimbare domiciliu"


def test_trailing_model_function_call_dropped():
    """Model emitted a function_call but dispatch crashed before
    function_response was appended. Send the prior history without the
    orphan; the new user message just continues the conversation."""
    history = [
        _user("salut"),
        _model("bună!"),
        _user("vreau X"),
        _model_fc("lookup_procedure", {"query": "X"}),
    ]
    sanitized, leftover = _sanitize_history_for_gemini(history)
    assert sanitized == [_user("salut"), _model("bună!")]
    assert leftover == "vreau X"


def test_multiple_orphan_user_turns_merged_in_order():
    """Two failures in a row pile two orphan user turns. They should be
    merged in chronological order so the model sees them as written."""
    history = [
        _model("bună!"),
        _user("primul mesaj"),
        _user("al doilea mesaj"),
    ]
    sanitized, leftover = _sanitize_history_for_gemini(history)
    assert sanitized == [_model("bună!")]
    assert leftover == "primul mesaj\nal doilea mesaj"


def test_empty_text_user_turn_dropped_without_leftover():
    """A user turn with only whitespace shouldn't pollute the leftover."""
    history = [_user("salut"), _model("bună!"), _user("   ")]
    sanitized, leftover = _sanitize_history_for_gemini(history)
    assert sanitized == [_user("salut"), _model("bună!")]
    assert leftover is None


def test_clean_text_only_model_at_end_is_kept():
    """The most common case: history ends with a successful model reply.
    Don't touch it."""
    history = [_user("salut"), _model("Cum te ajut?")]
    sanitized, leftover = _sanitize_history_for_gemini(history)
    assert sanitized == history
    assert leftover is None


def test_unknown_role_short_circuits():
    """If we hit something we don't understand, bail conservatively
    rather than chewing through the rest of the history."""
    history = [
        _user("salut"),
        _model("bună!"),
        {"role": "system", "parts": [{"text": "weird"}]},
    ]
    sanitized, leftover = _sanitize_history_for_gemini(history)
    assert sanitized == history
    assert leftover is None


def test_function_call_orphan_does_not_consume_clean_history():
    """Stop trimming once we hit a clean text-only model turn."""
    history = [
        _user("u1"),
        _model("m1"),
        _user("u2"),
        _model_fc("foo", {}),
    ]
    sanitized, leftover = _sanitize_history_for_gemini(history)
    # The model_fc is an orphan; u2 is a leftover user; the prior
    # u1/m1 pair is a clean history that must remain.
    assert sanitized == [_user("u1"), _model("m1")]
    assert leftover == "u2"
