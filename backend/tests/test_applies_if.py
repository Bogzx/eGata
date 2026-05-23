"""Pure-logic tests for the applies_if expression evaluator (Plan 4)."""
import pytest

from app.applies_if import evaluate, ParseError


def test_literal_true():
    assert evaluate("owns_vehicle == true", {"owns_vehicle": True}) is True


def test_literal_false():
    assert evaluate("owns_vehicle == true", {"owns_vehicle": False}) is False


def test_missing_attribute_is_false():
    assert evaluate("owns_vehicle == true", {}) is False


def test_string_literal_match():
    assert evaluate(
        'marital_status == "căsătorit"',
        {"marital_status": "căsătorit"},
    ) is True


def test_string_literal_mismatch():
    assert evaluate(
        'marital_status == "căsătorit"',
        {"marital_status": "necăsătorit"},
    ) is False


def test_and_both_true():
    attrs = {"owns_vehicle": True, "has_children": True}
    assert evaluate("owns_vehicle == true and has_children == true", attrs) is True


def test_and_one_false():
    attrs = {"owns_vehicle": True, "has_children": False}
    assert evaluate("owns_vehicle == true and has_children == true", attrs) is False


def test_or_one_true():
    attrs = {"marital_status": "văduv"}
    expr = 'marital_status == "căsătorit" or marital_status == "văduv"'
    assert evaluate(expr, attrs) is True


def test_or_both_false():
    attrs = {"marital_status": "necăsătorit"}
    expr = 'marital_status == "căsătorit" or marital_status == "văduv"'
    assert evaluate(expr, attrs) is False


def test_not():
    assert evaluate("not (has_children == true)", {"has_children": False}) is True


def test_parentheses_precedence():
    attrs = {"a": True, "b": False, "c": True}
    assert evaluate("a == true and (b == true or c == true)", attrs) is True
    assert evaluate("(a == true and b == true) or c == true", attrs) is True


def test_inequality():
    assert evaluate("owns_vehicle != true", {"owns_vehicle": False}) is True


def test_empty_expression_returns_true():
    assert evaluate("", {}) is True
    assert evaluate(None, {}) is True


def test_parse_error_unknown_operator():
    with pytest.raises(ParseError):
        evaluate("owns_vehicle ~~ true", {})


def test_parse_error_unbalanced_parens():
    with pytest.raises(ParseError):
        evaluate("(owns_vehicle == true", {})
