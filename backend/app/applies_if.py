"""Tiny boolean-expression evaluator for procedure next_steps.applies_if.

Grammar (recursive descent):
    expr     := or_expr
    or_expr  := and_expr ("or" and_expr)*
    and_expr := not_expr ("and" not_expr)*
    not_expr := "not" not_expr | atom
    atom     := "(" expr ")" | comparison
    comparison := IDENT op value
    op       := "==" | "!="
    value    := "true" | "false" | STRING | NUMBER

Missing attributes resolve to None and compare unequal to any literal.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class ParseError(ValueError):
    """Raised when the applies_if expression cannot be parsed."""


_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<LPAREN>\()
      | (?P<RPAREN>\))
      | (?P<EQ>==)
      | (?P<NEQ>!=)
      | (?P<STRING>"(?:[^"\\]|\\.)*")
      | (?P<NUMBER>-?\d+(?:\.\d+)?)
      | (?P<IDENT>[A-Za-z_À-ſ][A-Za-z0-9_À-ſ]*)
    )
    """,
    re.VERBOSE,
)


@dataclass
class _Token:
    kind: str
    value: str


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if m is None or m.end() == m.start():
            if text[pos:].strip() == "":
                break
            raise ParseError(f"Unexpected character at pos {pos}: {text[pos:pos+10]!r}")
        for name, val in m.groupdict().items():
            if val is not None:
                tokens.append(_Token(name, val))
                break
        pos = m.end()
    return tokens


_KEYWORDS = {"and", "or", "not", "true", "false"}

# Parse tree: ("or" | "and", left, right), ("not", node) or
# ("cmp", name, "==" | "!=", literal).
_Node = tuple[Any, ...]


class _Parser:
    def __init__(self, tokens: list[_Token]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> _Token | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _consume(self) -> _Token:
        if self.pos >= len(self.tokens):
            raise ParseError("Unexpected end of expression")
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _is_keyword(self, kw: str) -> bool:
        tok = self._peek()
        return tok is not None and tok.kind == "IDENT" and tok.value == kw

    def parse(self) -> _Node:
        node = self._or_expr()
        if self.pos != len(self.tokens):
            tok = self.tokens[self.pos]
            raise ParseError(f"Unexpected token {tok.value!r} at pos {self.pos}")
        return node

    def _or_expr(self) -> _Node:
        left = self._and_expr()
        while self._is_keyword("or"):
            self._consume()
            right = self._and_expr()
            left = ("or", left, right)
        return left

    def _and_expr(self) -> _Node:
        left = self._not_expr()
        while self._is_keyword("and"):
            self._consume()
            right = self._not_expr()
            left = ("and", left, right)
        return left

    def _not_expr(self) -> _Node:
        if self._is_keyword("not"):
            self._consume()
            return ("not", self._not_expr())
        return self._atom()

    def _atom(self) -> _Node:
        tok = self._peek()
        if tok is None:
            raise ParseError("Expected expression, got end of input")
        if tok.kind == "LPAREN":
            self._consume()
            node = self._or_expr()
            close = self._peek()
            if close is None or close.kind != "RPAREN":
                raise ParseError("Unbalanced parentheses")
            self._consume()
            return node
        return self._comparison()

    def _comparison(self) -> _Node:
        ident = self._consume()
        if ident.kind != "IDENT" or ident.value in _KEYWORDS:
            raise ParseError(f"Expected attribute name, got {ident.value!r}")
        op_tok = self._consume()
        if op_tok.kind not in ("EQ", "NEQ"):
            raise ParseError(f"Expected '==' or '!=', got {op_tok.value!r}")
        op = "==" if op_tok.kind == "EQ" else "!="
        val_tok = self._consume()
        value = self._literal(val_tok)
        return ("cmp", ident.value, op, value)

    @staticmethod
    def _literal(tok: _Token) -> Any:
        if tok.kind == "IDENT":
            if tok.value == "true":
                return True
            if tok.value == "false":
                return False
            raise ParseError(f"Expected literal, got identifier {tok.value!r}")
        if tok.kind == "STRING":
            raw = tok.value[1:-1]
            return _unescape_string(raw)
        if tok.kind == "NUMBER":
            return float(tok.value) if "." in tok.value else int(tok.value)
        raise ParseError(f"Expected literal, got {tok.value!r}")


def _unescape_string(raw: str) -> str:
    """Resolve only \\" and \\\\ inside a string literal; leave Unicode intact."""
    out: list[str] = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt == '"':
                out.append('"')
            elif nxt == "\\":
                out.append("\\")
            elif nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            else:
                out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _eval(node: _Node, attrs: Mapping[str, Any]) -> bool:
    op = node[0]
    if op == "and":
        return _eval(node[1], attrs) and _eval(node[2], attrs)
    if op == "or":
        return _eval(node[1], attrs) or _eval(node[2], attrs)
    if op == "not":
        return not _eval(node[1], attrs)
    if op == "cmp":
        _, name, comparator, value = node
        actual = attrs.get(name)
        if comparator == "==":
            return bool(actual == value)
        return bool(actual != value)
    raise ParseError(f"Unknown node {op!r}")


def evaluate(expression: str | None, attributes: Mapping[str, Any]) -> bool:
    """Evaluate an applies_if expression against citizen attributes.

    Empty / None expression returns True (matches by default).
    Missing attributes resolve to None.
    """
    if expression is None or expression.strip() == "":
        return True
    tokens = _tokenize(expression)
    if not tokens:
        return True
    parser = _Parser(tokens)
    tree = parser.parse()
    return _eval(tree, attributes)
