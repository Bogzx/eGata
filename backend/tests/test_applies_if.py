"""Pure-logic tests for the applies_if expression evaluator (Plan 4)."""
import pytest

from app.applies_if import ParseError, evaluate


def test_literal_true() -> None:
    assert evaluate("owns_vehicle == true", {"owns_vehicle": True}) is True


def test_literal_false() -> None:
    assert evaluate("owns_vehicle == true", {"owns_vehicle": False}) is False


def test_missing_attribute_is_false() -> None:
    assert evaluate("owns_vehicle == true", {}) is False


def test_string_literal_match() -> None:
    assert evaluate(
        'marital_status == "căsătorit"',
        {"marital_status": "căsătorit"},
    ) is True


def test_string_literal_mismatch() -> None:
    assert evaluate(
        'marital_status == "căsătorit"',
        {"marital_status": "necăsătorit"},
    ) is False


def test_and_both_true() -> None:
    attrs = {"owns_vehicle": True, "has_children": True}
    assert evaluate("owns_vehicle == true and has_children == true", attrs) is True


def test_and_one_false() -> None:
    attrs = {"owns_vehicle": True, "has_children": False}
    assert evaluate("owns_vehicle == true and has_children == true", attrs) is False


def test_or_one_true() -> None:
    attrs = {"marital_status": "văduv"}
    expr = 'marital_status == "căsătorit" or marital_status == "văduv"'
    assert evaluate(expr, attrs) is True


def test_or_both_false() -> None:
    attrs = {"marital_status": "necăsătorit"}
    expr = 'marital_status == "căsătorit" or marital_status == "văduv"'
    assert evaluate(expr, attrs) is False


def test_not() -> None:
    assert evaluate("not (has_children == true)", {"has_children": False}) is True


def test_parentheses_precedence() -> None:
    attrs = {"a": True, "b": False, "c": True}
    assert evaluate("a == true and (b == true or c == true)", attrs) is True
    assert evaluate("(a == true and b == true) or c == true", attrs) is True


def test_inequality() -> None:
    assert evaluate("owns_vehicle != true", {"owns_vehicle": False}) is True


def test_empty_expression_returns_true() -> None:
    assert evaluate("", {}) is True
    assert evaluate(None, {}) is True


def test_parse_error_unknown_operator() -> None:
    with pytest.raises(ParseError):
        evaluate("owns_vehicle ~~ true", {})


def test_parse_error_unbalanced_parens() -> None:
    with pytest.raises(ParseError):
        evaluate("(owns_vehicle == true", {})
