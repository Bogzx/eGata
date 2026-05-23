# CivicAI — Plan 4: Proactive Layer + Polish + Accessibility

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the agent "think ahead" — every delivered document spawns proactive next-step reminders that surface on the citizen home with motion. Make accessibility real, not lip service: voice-only mode completes a flow without screen touch; simple-language toggle changes agent tone; large-text mode works. Polish the UX with framer-motion. Harden production deploy. Run demo dry-runs against the juror poke-list.

**Architecture:** APScheduler-driven background worker in FastAPI that reads new ledger entries (`delivered` event) and writes reminders. New API endpoints for reminders + demo reset. Frontend reminder cards with framer-motion; accessibility toggles wired to behaviors (voice-only consumes Plan 3's voice hook; simple-language passes preference flag); axe-core + Lighthouse in CI; Sentry + healthchecks.

**Tech Stack:** APScheduler, FastAPI BackgroundTasks, Sentry SDK (Python + Next.js), axe-core, Lighthouse CI, framer-motion (full polish), Playwright (dry-run smoke tests).

**Dependencies:** Wave 1 merged. Plan 4 starts before Plan 3 is complete; tasks that depend on Plan 3 (voice-only mode behavior) ship the wiring assuming Plan 3's hook will land. Where Plan 3's hook isn't yet real, voice-only mode is verified manually only at Checkpoint 2.

**Interfaces with other plans:**
- Plan 3 owns `useVoiceAgent` real implementation. Plan 4's voice-only mode consumes that hook. Plan 4 also sets `preferences.simple_language` and `preferences.voice_only` on the `/voice/session` request — Plan 3 honors these.
- Plan 4 introduces `set_reminder` via background worker that writes directly to the `reminders` table. (Plan 3 exposes `set_reminder` as an AGENT tool for direct LLM-triggered reminders; both write to the same table and ledger.)

---

## File Structure

**Backend (Plan 4 owns):**
- Create: `backend/app/applies_if.py` — expression parser/evaluator
- Create: `backend/app/reminders.py` — reminders writer + endpoints + worker
- Create: `backend/app/demo.py` — demo reset endpoint
- Create: `backend/app/health.py` — `/healthz` endpoint
- Create: `backend/app/worker.py` — APScheduler bootstrap
- Create: `backend/migrations/004_processed_events.sql` — watermark table
- Create: `backend/migrations/005_seed_reminders.sql` — pre-seeded demo reminders
- Modify: `backend/app/main.py` — register routers + Sentry + startup hook
- Modify: `backend/app/citizens.py` — add `PATCH /citizens/me/attributes`
- Modify: `backend/pyproject.toml` — add apscheduler, sentry-sdk[fastapi]
- Test: `backend/tests/test_applies_if.py`
- Test: `backend/tests/test_reminders.py`
- Test: `backend/tests/test_demo_reset.py`
- Test: `backend/tests/test_citizens_attributes.py`
- Test: `backend/tests/test_healthz.py`

**Frontend (Plan 4 owns/extends):**
- Modify: `frontend/components/ReminderCard.tsx` — kind-specific layouts + actions
- Create: `frontend/components/RemindersList.tsx` — sorted list, empty state, stagger animation
- Create: `frontend/components/DemoResetButton.tsx` — floating dev-panel button
- Modify: `frontend/components/AccessibilityToggles.tsx` — wire behaviors (voice_only, simple_language, large_text)
- Modify: `frontend/app/page.tsx` — render `RemindersList` and `DemoResetButton`
- Modify: `frontend/app/layout.tsx` — Sentry init, error boundary, `prefers-reduced-motion` provider
- Create: `frontend/app/error.tsx` — global error boundary (Romanian)
- Create: `frontend/lib/motion.ts` — shared framer-motion variants + reduced-motion guard
- Modify: `frontend/components/ChatPanel.tsx` — message fade-in
- Modify: `frontend/components/FormPreview.tsx` — autofill pulse animation
- Modify: `frontend/components/CompletionModeSelector.tsx` — mode-switch transition
- Modify: `frontend/lib/api.ts` — add reminders/demo/attributes client methods
- Modify: `frontend/lib/types.ts` — confirm Reminder type (already in roadmap)
- Modify: `frontend/lib/i18n.ts` — used by simple-language toggle, no schema changes
- Modify: `frontend/package.json` — add `@axe-core/playwright`, `@sentry/nextjs`, `framer-motion` already present
- Test: `frontend/tests/RemindersList.test.tsx`
- Test: `frontend/tests/AccessibilityToggles.test.tsx`
- E2E: `frontend/e2e/demo-flow.spec.ts`
- E2E: `frontend/e2e/a11y.spec.ts`

**CI / Infra:**
- Create: `.github/workflows/a11y.yml` — Lighthouse CI + axe-core E2E
- Create: `lighthouserc.json` — Lighthouse CI config
- Create: `docs/superpowers/demo-pokelist.md` — juror Q/A checklist

---

## Task 1: Set up Plan 4 branch and install dependencies

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `frontend/package.json`

- [ ] **Step 1: Create branch off main**

Run:
```bash
git checkout main
git pull
git checkout -b wave2/plan-4-proactive-polish
```

- [ ] **Step 2: Add backend dependencies**

Edit `backend/pyproject.toml`, add to `[project] dependencies`:

```toml
"apscheduler>=3.10.4",
"sentry-sdk[fastapi]>=2.18.0",
```

Run:
```bash
cd backend && pip install -e .
```
Expected: apscheduler and sentry-sdk install cleanly.

- [ ] **Step 3: Add frontend dependencies**

Run:
```bash
cd frontend
npm install @sentry/nextjs@^8 @axe-core/playwright@^4
```

Expected: packages added to `package.json`; `framer-motion` already present from Plan 1.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml frontend/package.json frontend/package-lock.json
git commit -m "chore(plan-4): add apscheduler, sentry, axe-core deps"
```

---

## Task 2: `applies_if` expression evaluator (TDD)

**Files:**
- Create: `backend/app/applies_if.py`
- Test: `backend/tests/test_applies_if.py`

The evaluator parses tiny boolean expressions against a `citizen.attributes` dict. Examples we MUST handle:
- `owns_vehicle == true`
- `has_children == false`
- `marital_status == "căsătorit"`
- `owns_vehicle == true and has_children == true`
- `marital_status == "căsătorit" or marital_status == "văduv"`
- `not (has_children == true)`
- Parentheses for grouping.

Missing attributes evaluate to `None` and are NOT equal to anything (so `owns_vehicle == true` is `False` if the attribute is absent).

- [ ] **Step 1: Write failing tests**

Write `backend/tests/test_applies_if.py`:

```python
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
    # Without parens: a and (b or c) → True. With parens: (a and b) or c → True.
    assert evaluate("a == true and (b == true or c == true)", attrs) is True
    assert evaluate("(a == true and b == true) or c == true", attrs) is True


def test_inequality():
    assert evaluate("owns_vehicle != true", {"owns_vehicle": False}) is True


def test_empty_expression_returns_true():
    # When a next_step has no applies_if, callers pass None; evaluate("") is True
    assert evaluate("", {}) is True
    assert evaluate(None, {}) is True


def test_parse_error_unknown_operator():
    with pytest.raises(ParseError):
        evaluate("owns_vehicle ~~ true", {})


def test_parse_error_unbalanced_parens():
    with pytest.raises(ParseError):
        evaluate("(owns_vehicle == true", {})
```

- [ ] **Step 2: Run tests; verify they all fail**

Run: `cd backend && pytest tests/test_applies_if.py -v`
Expected: All tests FAIL (module does not exist yet).

- [ ] **Step 3: Implement the evaluator**

Write `backend/app/applies_if.py`:

```python
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

We deliberately do NOT support arbitrary identifiers on the RHS — only literals.
Missing attributes resolve to None and compare unequal to any literal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


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
      | (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)
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
        if m is None:
            # check if remainder is just whitespace
            if text[pos:].strip() == "":
                break
            raise ParseError(f"Unexpected character at pos {pos}: {text[pos:pos+10]!r}")
        if m.end() == m.start():
            # only whitespace consumed; bail
            if text[pos:].strip() == "":
                break
            raise ParseError(f"Empty match at pos {pos}")
        for name, val in m.groupdict().items():
            if val is not None:
                tokens.append(_Token(name, val))
                break
        pos = m.end()
    return tokens


_KEYWORDS = {"and", "or", "not", "true", "false"}


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

    def parse(self):
        node = self._or_expr()
        if self.pos != len(self.tokens):
            tok = self.tokens[self.pos]
            raise ParseError(f"Unexpected token {tok.value!r} at pos {self.pos}")
        return node

    def _or_expr(self):
        left = self._and_expr()
        while self._is_keyword("or"):
            self._consume()
            right = self._and_expr()
            left = ("or", left, right)
        return left

    def _and_expr(self):
        left = self._not_expr()
        while self._is_keyword("and"):
            self._consume()
            right = self._not_expr()
            left = ("and", left, right)
        return left

    def _not_expr(self):
        if self._is_keyword("not"):
            self._consume()
            return ("not", self._not_expr())
        return self._atom()

    def _atom(self):
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

    def _comparison(self):
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
            # strip surrounding quotes and unescape \" and \\
            raw = tok.value[1:-1]
            return raw.encode("utf-8").decode("unicode_escape")
        if tok.kind == "NUMBER":
            return float(tok.value) if "." in tok.value else int(tok.value)
        raise ParseError(f"Expected literal, got {tok.value!r}")


def _eval(node, attrs: Mapping[str, Any]) -> bool:
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
            return actual == value
        return actual != value
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
```

- [ ] **Step 4: Run tests; verify all pass**

Run: `cd backend && pytest tests/test_applies_if.py -v`
Expected: 14/14 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/applies_if.py backend/tests/test_applies_if.py
git commit -m "feat(plan-4): add applies_if expression evaluator with TDD"
```

---

## Task 3: Watermark migration for processed ledger events

**Files:**
- Create: `backend/migrations/004_processed_events.sql`

- [ ] **Step 1: Write migration**

Create `backend/migrations/004_processed_events.sql`:

```sql
-- Watermark table so the background worker is idempotent.
-- Each row records that ledger entry N has been processed by the reminders evaluator.

CREATE TABLE IF NOT EXISTS processed_events (
    ledger_id   BIGINT PRIMARY KEY REFERENCES ledger(id) ON DELETE CASCADE,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processed_events_processed_at
    ON processed_events (processed_at DESC);

-- Helper view: ledger rows that are 'delivered' and not yet processed.
CREATE OR REPLACE VIEW pending_delivered_events AS
SELECT l.*
FROM ledger l
LEFT JOIN processed_events p ON p.ledger_id = l.id
WHERE l.event_type = 'delivered'
  AND p.ledger_id IS NULL
ORDER BY l.id ASC;
```

- [ ] **Step 2: Apply migration in Supabase**

Run from Supabase SQL editor (or `supabase db push` if local CLI configured):

```bash
psql "$SUPABASE_DB_URL" -f backend/migrations/004_processed_events.sql
```

Expected: `CREATE TABLE`, `CREATE INDEX`, `CREATE VIEW` succeed.

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/004_processed_events.sql
git commit -m "feat(plan-4): add processed_events watermark migration"
```

---

## Task 4: Reminders writer (TDD)

**Files:**
- Create: `backend/app/reminders.py` (writer + selection logic, endpoints come in Task 6)
- Test: `backend/tests/test_reminders.py`

This task only implements `evaluate_next_steps(citizen_id, procedure_id, trigger_doc_id, db) -> list[Reminder]`. Worker scheduling and endpoints come later.

- [ ] **Step 1: Write failing tests**

Write `backend/tests/test_reminders.py`:

```python
"""Tests for reminders selection + writer."""
import pytest
from uuid import uuid4
from datetime import date, timedelta

from app.reminders import evaluate_next_steps, _select_applicable_steps


# ---- pure selection-logic tests (no DB) ----

PROCEDURE = {
    "id": "schimbare-domiciliu",
    "title": "Schimbare domiciliu",
    "next_steps": [
        {
            "kind": "in_scope_procedure",
            "procedure_id": "preschimbare-ci",
            "deadline_days": 15,
            "title": "Preschimbare carte de identitate",
        },
        {
            "kind": "external_redirect",
            "redirect_target": "DRPCIV",
            "deadline_days": 30,
            "title": "Actualizare certificat înmatriculare auto",
            "applies_if": "owns_vehicle == true",
        },
        {
            "kind": "external_redirect",
            "redirect_target": "CNAS",
            "title": "Actualizare medic de familie",
        },
        {
            "kind": "external_redirect",
            "redirect_target": "ANAF",
            "title": "Notificare schimbare domiciliu fiscal",
        },
    ],
}


def test_no_applies_if_always_selected():
    steps = _select_applicable_steps(PROCEDURE, {})
    titles = [s["title"] for s in steps]
    assert "Preschimbare carte de identitate" in titles
    assert "Actualizare medic de familie" in titles
    assert "Notificare schimbare domiciliu fiscal" in titles


def test_applies_if_true_includes_step():
    steps = _select_applicable_steps(PROCEDURE, {"owns_vehicle": True})
    titles = [s["title"] for s in steps]
    assert "Actualizare certificat înmatriculare auto" in titles


def test_applies_if_false_excludes_step():
    steps = _select_applicable_steps(PROCEDURE, {"owns_vehicle": False})
    titles = [s["title"] for s in steps]
    assert "Actualizare certificat înmatriculare auto" not in titles


def test_missing_attribute_excludes_conditional_step():
    steps = _select_applicable_steps(PROCEDURE, {})
    titles = [s["title"] for s in steps]
    assert "Actualizare certificat înmatriculare auto" not in titles


def test_unconditional_steps_count():
    # 3 unconditional + 0 of the conditional one
    steps = _select_applicable_steps(PROCEDURE, {})
    assert len(steps) == 3


# ---- DB-integration tests (use the test db fixture from conftest) ----


def test_evaluate_writes_reminders_for_applicable_steps(db, seed_citizen):
    citizen = seed_citizen(attributes={"owns_vehicle": True})
    trigger_doc_id = uuid4()
    reminders = evaluate_next_steps(
        citizen_id=citizen.id,
        procedure_id="schimbare-domiciliu",
        trigger_doc_id=trigger_doc_id,
        db=db,
    )
    assert len(reminders) == 4  # all four next_steps apply
    titles = {r.title for r in reminders}
    assert "Actualizare certificat înmatriculare auto" in titles


def test_evaluate_skips_non_applicable_steps(db, seed_citizen):
    citizen = seed_citizen(attributes={"owns_vehicle": False})
    trigger_doc_id = uuid4()
    reminders = evaluate_next_steps(
        citizen_id=citizen.id,
        procedure_id="schimbare-domiciliu",
        trigger_doc_id=trigger_doc_id,
        db=db,
    )
    titles = {r.title for r in reminders}
    assert "Actualizare certificat înmatriculare auto" not in titles
    assert len(reminders) == 3


def test_evaluate_writes_ledger_entry_per_reminder(db, seed_citizen):
    citizen = seed_citizen(attributes={"owns_vehicle": True})
    before = db.count_ledger_rows(event_type="reminder_created")
    evaluate_next_steps(
        citizen_id=citizen.id,
        procedure_id="schimbare-domiciliu",
        trigger_doc_id=uuid4(),
        db=db,
    )
    after = db.count_ledger_rows(event_type="reminder_created")
    assert after - before == 4


def test_evaluate_sets_due_date_from_deadline_days(db, seed_citizen):
    citizen = seed_citizen(attributes={"owns_vehicle": True})
    reminders = evaluate_next_steps(
        citizen_id=citizen.id,
        procedure_id="schimbare-domiciliu",
        trigger_doc_id=uuid4(),
        db=db,
    )
    drpciv = next(r for r in reminders if r.redirect_target == "DRPCIV")
    expected = date.today() + timedelta(days=30)
    assert drpciv.due_date == expected


def test_evaluate_is_safe_to_call_twice_for_same_doc(db, seed_citizen):
    """If called twice with the same trigger_doc_id, no duplicate reminders."""
    citizen = seed_citizen(attributes={"owns_vehicle": True})
    trigger = uuid4()
    first = evaluate_next_steps(
        citizen_id=citizen.id,
        procedure_id="schimbare-domiciliu",
        trigger_doc_id=trigger,
        db=db,
    )
    second = evaluate_next_steps(
        citizen_id=citizen.id,
        procedure_id="schimbare-domiciliu",
        trigger_doc_id=trigger,
        db=db,
    )
    assert len(first) == 4
    assert len(second) == 0  # idempotent
```

- [ ] **Step 2: Run tests; verify all fail**

Run: `cd backend && pytest tests/test_reminders.py -v`
Expected: All FAIL (module/functions do not exist).

- [ ] **Step 3: Implement reminders writer**

Write `backend/app/reminders.py`:

```python
"""Reminders writer + selection logic.

The endpoints and worker are added in later tasks; this module exposes:
- evaluate_next_steps: read procedure registry, filter by applies_if, persist.
- _select_applicable_steps: pure selection used by tests.

Each persisted reminder also writes a ledger entry of type 'reminder_created'.
The writer is idempotent per (trigger_doc_id, procedure_id_or_redirect_target):
if the same combination already exists, it's skipped.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping
from uuid import UUID, uuid4

from app.applies_if import evaluate
from app.procedures import load_procedure
from app.ledger import append_ledger


log = logging.getLogger(__name__)


@dataclass
class Reminder:
    id: UUID
    citizen_id: UUID
    trigger_doc_id: UUID | None
    kind: str
    procedure_id: str | None
    redirect_target: str | None
    title: str
    due_date: date | None
    status: str
    created_at: Any


def _select_applicable_steps(
    procedure: Mapping[str, Any],
    attributes: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    """Return the subset of procedure.next_steps whose applies_if evaluates True."""
    out: list[Mapping[str, Any]] = []
    for step in procedure.get("next_steps", []):
        cond = step.get("applies_if")
        if evaluate(cond, attributes):
            out.append(step)
    return out


def _step_identity(step: Mapping[str, Any]) -> tuple[str, str | None]:
    """Stable identity for a next_step within a procedure (for idempotency)."""
    return (
        step["kind"],
        step.get("procedure_id") or step.get("redirect_target"),
    )


def evaluate_next_steps(
    *,
    citizen_id: UUID,
    procedure_id: str,
    trigger_doc_id: UUID | None,
    db,
) -> list[Reminder]:
    """Evaluate next_steps for a citizen + procedure; write matching reminders.

    Returns the list of newly created reminders (excludes ones that already
    exist for the same trigger_doc_id + step identity).
    """
    citizen = db.fetch_citizen(citizen_id)
    procedure = load_procedure(procedure_id)
    if procedure is None:
        log.warning("evaluate_next_steps: unknown procedure %s", procedure_id)
        return []

    attrs = (citizen.attributes or {}) if citizen else {}
    applicable = _select_applicable_steps(procedure, attrs)

    existing = db.fetch_reminders_for_trigger(trigger_doc_id) if trigger_doc_id else []
    existing_keys = {_step_identity(_step_from_reminder(r)) for r in existing}

    created: list[Reminder] = []
    for step in applicable:
        if _step_identity(step) in existing_keys:
            continue  # idempotent
        rem = _persist_reminder(
            citizen_id=citizen_id,
            trigger_doc_id=trigger_doc_id,
            step=step,
            db=db,
        )
        created.append(rem)
    return created


def _step_from_reminder(r: Reminder) -> dict[str, Any]:
    return {
        "kind": r.kind,
        "procedure_id": r.procedure_id,
        "redirect_target": r.redirect_target,
    }


def _persist_reminder(
    *,
    citizen_id: UUID,
    trigger_doc_id: UUID | None,
    step: Mapping[str, Any],
    db,
) -> Reminder:
    deadline_days = step.get("deadline_days")
    due = date.today() + timedelta(days=deadline_days) if deadline_days else None
    rem_id = uuid4()
    rem = db.insert_reminder(
        id=rem_id,
        citizen_id=citizen_id,
        trigger_doc_id=trigger_doc_id,
        kind=step["kind"],
        procedure_id=step.get("procedure_id"),
        redirect_target=step.get("redirect_target"),
        title=step["title"],
        due_date=due,
        status="pending",
    )
    # Ledger entry — uses the existing append_ledger helper from Plan 2.
    append_ledger(
        db=db,
        citizen_id=citizen_id,
        document_id=trigger_doc_id,
        event_type="reminder_created",
        payload={
            "reminder_id": str(rem_id),
            "kind": step["kind"],
            "title": step["title"],
            "procedure_id": step.get("procedure_id"),
            "redirect_target": step.get("redirect_target"),
        },
    )
    return rem
```

- [ ] **Step 4: Wire conftest fixtures**

Edit `backend/tests/conftest.py` to add `db` and `seed_citizen` fixtures (extend the existing conftest from Plan 2):

```python
# Append to backend/tests/conftest.py

import pytest
from uuid import uuid4
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeCitizen:
    id: Any
    attributes: dict[str, Any]


class FakeDb:
    """In-memory test double matching the methods used by reminders.py."""
    def __init__(self):
        self.citizens: dict[Any, FakeCitizen] = {}
        self.reminders: list = []
        self.ledger: list = []

    def fetch_citizen(self, cid):
        return self.citizens.get(cid)

    def fetch_reminders_for_trigger(self, trigger_doc_id):
        return [r for r in self.reminders if r.trigger_doc_id == trigger_doc_id]

    def insert_reminder(self, **kwargs):
        from app.reminders import Reminder
        rem = Reminder(
            **{k: v for k, v in kwargs.items() if k != "created_at"},
            created_at=None,
        )
        self.reminders.append(rem)
        return rem

    def append_ledger_row(self, row):
        self.ledger.append(row)

    def count_ledger_rows(self, event_type):
        return sum(1 for r in self.ledger if r["event_type"] == event_type)


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def seed_citizen(db):
    def _seed(attributes=None):
        c = FakeCitizen(id=uuid4(), attributes=attributes or {})
        db.citizens[c.id] = c
        return c
    return _seed
```

Also patch `app/ledger.py:append_ledger` for the test path: ensure it calls `db.append_ledger_row({...event_type, ...})`. (Adjust the existing Plan 2 implementation to accept a `db` parameter shim — see Plan 2's ledger module for the existing signature and adapt; the test only needs the row to land in `db.ledger`.)

- [ ] **Step 5: Run tests; verify all pass**

Run: `cd backend && pytest tests/test_reminders.py -v`
Expected: 9/9 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/reminders.py backend/tests/test_reminders.py backend/tests/conftest.py
git commit -m "feat(plan-4): reminders writer + applies_if selection with TDD"
```

---

## Task 5: Background worker (APScheduler)

**Files:**
- Create: `backend/app/worker.py`
- Modify: `backend/app/main.py` (register startup hook)

We use APScheduler in `BackgroundScheduler` mode running inside the FastAPI process. Decision rationale: APScheduler is the right choice because we want a recurring poll independent of incoming HTTP requests; FastAPI's `BackgroundTasks` is request-scoped and would miss `delivered` events created by the agent's tool calls running outside the request lifecycle. APScheduler's overhead is tiny and Railway is single-process, so no multi-worker contention.

- [ ] **Step 1: Write `worker.py`**

Create `backend/app/worker.py`:

```python
"""APScheduler-based background worker for proactive reminders.

Polls the `pending_delivered_events` view every 5 seconds, and for each new
`delivered` ledger entry, calls evaluate_next_steps to write reminders.

Idempotent: the processed_events watermark table records which ledger ids
have been handled.
"""

from __future__ import annotations

import logging
from uuid import UUID

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.db import get_db
from app.reminders import evaluate_next_steps


log = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 5


def _process_pending_events() -> None:
    db = get_db()
    rows = db.fetch_pending_delivered_events()  # implemented in app/db.py — see below
    for row in rows:
        try:
            doc = db.fetch_document(row["document_id"])
            if doc is None:
                log.warning("ledger row %s references missing document %s",
                            row["id"], row["document_id"])
                db.mark_event_processed(row["id"])
                continue
            evaluate_next_steps(
                citizen_id=UUID(str(row["citizen_id"])),
                procedure_id=doc.procedure_id,
                trigger_doc_id=UUID(str(row["document_id"])),
                db=db,
            )
            db.mark_event_processed(row["id"])
        except Exception:
            log.exception("worker failed to process ledger row %s", row["id"])
            # do NOT mark processed; will retry next tick


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        _process_pending_events,
        IntervalTrigger(seconds=POLL_INTERVAL_SECONDS),
        id="reminders_worker",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("reminders worker started; poll=%ss", POLL_INTERVAL_SECONDS)
    return scheduler


# Module-level singleton so main.py can manage lifecycle cleanly.
_SCHEDULER: BackgroundScheduler | None = None


def init_worker() -> None:
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = start_scheduler()


def shutdown_worker() -> None:
    global _SCHEDULER
    if _SCHEDULER is not None:
        _SCHEDULER.shutdown(wait=False)
        _SCHEDULER = None
```

- [ ] **Step 2: Add the DB helpers used by the worker**

Edit `backend/app/db.py` (extend Plan 2's module — find the appropriate place):

```python
# Add inside the SupabaseDb class (or whatever Plan 2 named it):

def fetch_pending_delivered_events(self) -> list[dict]:
    """Return ledger rows where event_type='delivered' and not yet processed."""
    res = self._client.from_("pending_delivered_events").select("*").execute()
    return res.data or []


def mark_event_processed(self, ledger_id: int) -> None:
    self._client.from_("processed_events").insert(
        {"ledger_id": ledger_id}
    ).execute()


def fetch_document(self, doc_id):
    res = (
        self._client.from_("documents")
        .select("*")
        .eq("id", str(doc_id))
        .single()
        .execute()
    )
    return res.data  # returned as dict; caller treats .procedure_id appropriately

def insert_reminder(self, **kwargs):
    payload = {k: v for k, v in kwargs.items() if v is not None}
    payload["due_date"] = (
        payload["due_date"].isoformat() if payload.get("due_date") else None
    )
    res = self._client.from_("reminders").insert(payload).execute()
    from app.reminders import Reminder
    row = res.data[0]
    return Reminder(
        id=row["id"],
        citizen_id=row["citizen_id"],
        trigger_doc_id=row.get("trigger_doc_id"),
        kind=row["kind"],
        procedure_id=row.get("procedure_id"),
        redirect_target=row.get("redirect_target"),
        title=row["title"],
        due_date=row.get("due_date"),
        status=row["status"],
        created_at=row.get("created_at"),
    )

def fetch_reminders_for_trigger(self, trigger_doc_id):
    if trigger_doc_id is None:
        return []
    res = (
        self._client.from_("reminders")
        .select("*")
        .eq("trigger_doc_id", str(trigger_doc_id))
        .execute()
    )
    from app.reminders import Reminder
    return [
        Reminder(
            id=row["id"], citizen_id=row["citizen_id"],
            trigger_doc_id=row.get("trigger_doc_id"),
            kind=row["kind"], procedure_id=row.get("procedure_id"),
            redirect_target=row.get("redirect_target"),
            title=row["title"], due_date=row.get("due_date"),
            status=row["status"], created_at=row.get("created_at"),
        )
        for row in (res.data or [])
    ]
```

Note: If Plan 2 named the doc shape with object-style access (`doc.procedure_id`), wrap the dict with a small `Document` dataclass in `app/db.py`. The worker calls `doc.procedure_id`, so the field MUST be accessible that way. If Plan 2 returns dicts, change `doc.procedure_id` to `doc["procedure_id"]` in worker.py.

- [ ] **Step 3: Wire the worker to FastAPI startup**

Edit `backend/app/main.py`:

```python
# Add near the top:
from contextlib import asynccontextmanager
from app.worker import init_worker, shutdown_worker

@asynccontextmanager
async def lifespan(app):
    init_worker()
    yield
    shutdown_worker()

# Modify the FastAPI() init to pass lifespan:
app = FastAPI(title="CivicAI", lifespan=lifespan)
```

If Plan 2 already configured a `lifespan` context manager (e.g., to init the Supabase client), add the worker init/shutdown calls into that existing function rather than duplicating it.

- [ ] **Step 4: Manual smoke test**

Run the backend locally (`cd backend && uvicorn app.main:app`) and:
1. Hit `POST /documents/{id}/deliver` for a draft doc (via Plan 2's endpoint).
2. Wait 6 seconds.
3. Query `GET /reminders` (added in Task 6) — should return new reminders.

For now (Task 5 only), confirm via SQL:
```sql
SELECT * FROM reminders WHERE trigger_doc_id = '<just-delivered-doc-id>';
SELECT * FROM processed_events ORDER BY processed_at DESC LIMIT 5;
```

Expected: reminder rows present; corresponding ledger ids in processed_events.

- [ ] **Step 5: Commit**

```bash
git add backend/app/worker.py backend/app/main.py backend/app/db.py
git commit -m "feat(plan-4): APScheduler worker writes reminders after delivery"
```

---

## Task 6: `/reminders/*` endpoints

**Files:**
- Modify: `backend/app/reminders.py` (add FastAPI router)
- Modify: `backend/app/main.py` (mount the router)
- Test: `backend/tests/test_reminders_endpoints.py`

Endpoints:
- `GET /reminders` — list active reminders for the authenticated citizen.
- `POST /reminders/{id}/start` — for `in_scope_procedure`, create a draft document for that procedure and mark reminder `status="started"`; return the new document.
- `POST /reminders/{id}/dismiss` — mark `status="dismissed"`.

- [ ] **Step 1: Write failing endpoint tests**

Write `backend/tests/test_reminders_endpoints.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_list_reminders_requires_auth(client):
    res = client.get("/reminders")
    assert res.status_code == 401


def test_list_reminders_returns_pending_for_citizen(client, auth_header, seeded_reminder):
    res = client.get("/reminders", headers=auth_header)
    assert res.status_code == 200
    data = res.json()
    assert any(r["id"] == str(seeded_reminder.id) for r in data)
    # only pending reminders are returned (dismissed/done filtered out)
    for r in data:
        assert r["status"] in ("pending", "started")


def test_start_in_scope_reminder_creates_draft_document(client, auth_header,
                                                       seeded_in_scope_reminder):
    res = client.post(
        f"/reminders/{seeded_in_scope_reminder.id}/start",
        headers=auth_header,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "started"
    assert body["document"]["procedure_id"] == seeded_in_scope_reminder.procedure_id
    assert body["document"]["status"] == "draft"


def test_start_external_redirect_returns_400(client, auth_header,
                                              seeded_external_reminder):
    res = client.post(
        f"/reminders/{seeded_external_reminder.id}/start",
        headers=auth_header,
    )
    assert res.status_code == 400
    assert "external" in res.json()["detail"].lower()


def test_dismiss_marks_reminder_dismissed(client, auth_header, seeded_reminder):
    res = client.post(
        f"/reminders/{seeded_reminder.id}/dismiss",
        headers=auth_header,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "dismissed"


def test_cannot_act_on_another_citizens_reminder(client, auth_header,
                                                  other_citizen_reminder):
    res = client.post(
        f"/reminders/{other_citizen_reminder.id}/dismiss",
        headers=auth_header,
    )
    assert res.status_code == 404
```

Add the fixtures (`auth_header`, `seeded_reminder`, `seeded_in_scope_reminder`, `seeded_external_reminder`, `other_citizen_reminder`) to `backend/tests/conftest.py`. These should hit a real test database (Plan 2's conftest already establishes one). Pattern:

```python
@pytest.fixture
def seeded_reminder(db_real, default_citizen):
    # insert a pending in_scope reminder into real DB
    from uuid import uuid4
    rid = uuid4()
    db_real.from_("reminders").insert({
        "id": str(rid),
        "citizen_id": str(default_citizen.id),
        "kind": "in_scope_procedure",
        "procedure_id": "preschimbare-ci",
        "title": "Preschimbare CI",
        "status": "pending",
    }).execute()
    yield SimpleNamespace(id=rid, procedure_id="preschimbare-ci")
    db_real.from_("reminders").delete().eq("id", str(rid)).execute()
```

(Use the existing `db_real` and `default_citizen` patterns from Plan 2's conftest. If they don't exist by those names, follow whatever Plan 2 named them and harmonize.)

- [ ] **Step 2: Run tests; verify all fail**

Run: `cd backend && pytest tests/test_reminders_endpoints.py -v`
Expected: All FAIL (endpoints not registered).

- [ ] **Step 3: Implement the endpoints**

Append to `backend/app/reminders.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from uuid import UUID

from app.auth import get_current_citizen
from app.db import get_db
from app.documents import create_draft_document  # exposed by Plan 2's documents.py


router = APIRouter(prefix="/reminders", tags=["reminders"])


class ReminderOut(BaseModel):
    id: UUID
    citizen_id: UUID
    trigger_doc_id: UUID | None
    kind: str
    procedure_id: str | None
    redirect_target: str | None
    title: str
    due_date: str | None
    status: str
    created_at: str | None


class StartReminderResponse(BaseModel):
    id: UUID
    status: str
    document: dict  # full Document model from Plan 2


@router.get("", response_model=list[ReminderOut])
def list_reminders(citizen=Depends(get_current_citizen), db=Depends(get_db)):
    rows = (
        db.client.from_("reminders")
        .select("*")
        .eq("citizen_id", str(citizen.id))
        .in_("status", ["pending", "started"])
        .order("due_date", desc=False)
        .order("created_at", desc=True)
        .execute()
    )
    return rows.data or []


@router.post("/{reminder_id}/start", response_model=StartReminderResponse)
def start_reminder(
    reminder_id: UUID,
    citizen=Depends(get_current_citizen),
    db=Depends(get_db),
):
    rem = _load_owned_reminder(db, reminder_id, citizen.id)
    if rem["kind"] != "in_scope_procedure":
        raise HTTPException(
            status_code=400,
            detail="Reminder is an external redirect; cannot start in-app.",
        )
    if not rem.get("procedure_id"):
        raise HTTPException(status_code=400, detail="Reminder has no procedure_id")

    new_doc = create_draft_document(
        citizen_id=citizen.id,
        procedure_id=rem["procedure_id"],
        db=db,
    )
    db.client.from_("reminders").update({"status": "started"}).eq(
        "id", str(reminder_id)
    ).execute()
    return StartReminderResponse(
        id=reminder_id,
        status="started",
        document=new_doc.dict() if hasattr(new_doc, "dict") else new_doc,
    )


@router.post("/{reminder_id}/dismiss", response_model=ReminderOut)
def dismiss_reminder(
    reminder_id: UUID,
    citizen=Depends(get_current_citizen),
    db=Depends(get_db),
):
    _load_owned_reminder(db, reminder_id, citizen.id)  # 404 if not owned
    res = (
        db.client.from_("reminders")
        .update({"status": "dismissed"})
        .eq("id", str(reminder_id))
        .execute()
    )
    return res.data[0]


def _load_owned_reminder(db, reminder_id, citizen_id):
    res = (
        db.client.from_("reminders")
        .select("*")
        .eq("id", str(reminder_id))
        .eq("citizen_id", str(citizen_id))
        .single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return res.data
```

- [ ] **Step 4: Mount the router**

In `backend/app/main.py`, after `app = FastAPI(...)`:

```python
from app.reminders import router as reminders_router
app.include_router(reminders_router)
```

- [ ] **Step 5: Run tests; verify all pass**

Run: `cd backend && pytest tests/test_reminders_endpoints.py -v`
Expected: 6/6 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/reminders.py backend/app/main.py backend/tests/test_reminders_endpoints.py backend/tests/conftest.py
git commit -m "feat(plan-4): reminders endpoints (list/start/dismiss)"
```

---

## Task 7: Seed demo reminders migration

**Files:**
- Create: `backend/migrations/005_seed_reminders.sql`

Goal: ensure each demo citizen has 1-2 active reminders on first login so the home screen is rich during the demo.

- [ ] **Step 1: Write migration**

Create `backend/migrations/005_seed_reminders.sql`:

```sql
-- Seed pending reminders so the demo home screen is rich on first login.
-- Idempotent: deletes any pre-existing seed reminders before inserting.

DELETE FROM reminders
WHERE citizen_id IN (SELECT id FROM citizens WHERE cnp LIKE '___demo%')
   OR id IN (
     '11111111-1111-1111-1111-111111111101'::uuid,
     '11111111-1111-1111-1111-111111111102'::uuid,
     '11111111-1111-1111-1111-111111111103'::uuid
   );

-- Maria Ionescu (CNP 2851014123456) — primary demo persona
INSERT INTO reminders (id, citizen_id, kind, procedure_id, title, due_date, status)
SELECT
    '11111111-1111-1111-1111-111111111101'::uuid,
    id,
    'in_scope_procedure',
    'preschimbare-ci',
    'Cartea de identitate expiră în 23 de zile',
    CURRENT_DATE + INTERVAL '23 days',
    'pending'
FROM citizens WHERE cnp = '2851014123456';

INSERT INTO reminders (id, citizen_id, kind, redirect_target, title, due_date, status)
SELECT
    '11111111-1111-1111-1111-111111111102'::uuid,
    id,
    'external_redirect',
    'CNAS',
    'Actualizare medic de familie după schimbare adresă',
    NULL,
    'pending'
FROM citizens WHERE cnp = '2851014123456';

-- Andrei Pop (second demo persona) — has a vehicle
INSERT INTO reminders (id, citizen_id, kind, redirect_target, title, due_date, status)
SELECT
    '11111111-1111-1111-1111-111111111103'::uuid,
    id,
    'external_redirect',
    'DRPCIV',
    'Actualizare certificat înmatriculare auto (termen 30 zile)',
    CURRENT_DATE + INTERVAL '30 days',
    'pending'
FROM citizens WHERE cnp = '1900215987654';
```

(CNPs and personas should match those seeded in Plan 2's `002_seed_data.sql`. If they don't match exactly, adjust the WHERE clauses to use whichever CNPs Plan 2 actually inserted.)

- [ ] **Step 2: Apply migration**

```bash
psql "$SUPABASE_DB_URL" -f backend/migrations/005_seed_reminders.sql
```

Expected: 3 INSERT rows.

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/005_seed_reminders.sql
git commit -m "feat(plan-4): seed demo reminders for rich home screen"
```

---

## Task 8: `POST /demo/reset` endpoint (TDD)

**Files:**
- Create: `backend/app/demo.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_demo_reset.py`

The endpoint wipes a citizen's documents, reminders, ledger entries, and processed_events watermarks, then re-applies the seed data so the demo starts from a known state. Authorized via a static dev token in `DEMO_RESET_TOKEN` env var.

- [ ] **Step 1: Write failing tests**

Write `backend/tests/test_demo_reset.py`:

```python
import os
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def demo_token(monkeypatch):
    token = "test-demo-token-abc"
    monkeypatch.setenv("DEMO_RESET_TOKEN", token)
    return token


def test_reset_requires_dev_token(client):
    res = client.post("/demo/reset", json={"citizen_id": None})
    assert res.status_code == 401


def test_reset_with_wrong_token_rejected(client, demo_token):
    res = client.post(
        "/demo/reset",
        headers={"X-Demo-Token": "wrong"},
        json={"citizen_id": None},
    )
    assert res.status_code == 401


def test_reset_wipes_and_reseeds_citizen(client, demo_token, default_citizen_id,
                                          db_real):
    # Arrange: create some "dirty" state
    db_real.from_("documents").insert({
        "citizen_id": str(default_citizen_id),
        "procedure_id": "schimbare-domiciliu",
        "status": "draft",
        "fields": {},
    }).execute()

    # Act
    res = client.post(
        "/demo/reset",
        headers={"X-Demo-Token": demo_token},
        json={"citizen_id": str(default_citizen_id)},
    )

    # Assert
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["citizen_id"] == str(default_citizen_id)
    assert body["counts"]["documents_deleted"] >= 1
    assert body["counts"]["reminders_seeded"] >= 1

    # Documents wiped
    docs = (
        db_real.from_("documents").select("id")
        .eq("citizen_id", str(default_citizen_id)).execute().data
    )
    assert docs == []

    # Reminders re-seeded
    rems = (
        db_real.from_("reminders").select("*")
        .eq("citizen_id", str(default_citizen_id))
        .eq("status", "pending").execute().data
    )
    assert len(rems) >= 1


def test_reset_default_citizen_when_none_provided(client, demo_token,
                                                    default_citizen_id):
    res = client.post(
        "/demo/reset",
        headers={"X-Demo-Token": demo_token},
        json={},
    )
    assert res.status_code == 200
    assert res.json()["citizen_id"] == str(default_citizen_id)


def test_reset_is_idempotent(client, demo_token, default_citizen_id, db_real):
    client.post(
        "/demo/reset",
        headers={"X-Demo-Token": demo_token},
        json={"citizen_id": str(default_citizen_id)},
    )
    snap1 = sorted([
        r["title"] for r in
        db_real.from_("reminders").select("title")
        .eq("citizen_id", str(default_citizen_id))
        .eq("status", "pending").execute().data
    ])
    client.post(
        "/demo/reset",
        headers={"X-Demo-Token": demo_token},
        json={"citizen_id": str(default_citizen_id)},
    )
    snap2 = sorted([
        r["title"] for r in
        db_real.from_("reminders").select("title")
        .eq("citizen_id", str(default_citizen_id))
        .eq("status", "pending").execute().data
    ])
    assert snap1 == snap2
```

- [ ] **Step 2: Run tests; verify all fail**

Run: `cd backend && pytest tests/test_demo_reset.py -v`
Expected: All FAIL.

- [ ] **Step 3: Implement demo.py**

Write `backend/app/demo.py`:

```python
"""Demo reset endpoint — wipes a citizen's state and re-applies seed data.

Authorized by static dev token in DEMO_RESET_TOKEN. Disabled in production
(if the env var is not set, the endpoint returns 401 for any request).
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.db import get_db


router = APIRouter(prefix="/demo", tags=["demo"])


DEFAULT_DEMO_CITIZEN_CNP = "2851014123456"  # Maria Ionescu


SEED_FILES = [
    "002_seed_data.sql",
    "005_seed_reminders.sql",
]


class ResetRequest(BaseModel):
    citizen_id: UUID | None = None


class ResetCounts(BaseModel):
    documents_deleted: int
    reminders_deleted: int
    ledger_deleted: int
    processed_events_deleted: int
    reminders_seeded: int


class ResetResponse(BaseModel):
    ok: bool
    citizen_id: UUID
    counts: ResetCounts


def _verify_token(x_demo_token: str | None = Header(default=None)):
    expected = os.environ.get("DEMO_RESET_TOKEN")
    if not expected or x_demo_token != expected:
        raise HTTPException(status_code=401, detail="Invalid demo token")
    return True


@router.post("/reset", response_model=ResetResponse, dependencies=[Depends(_verify_token)])
def reset_demo(body: ResetRequest, db=Depends(get_db)):
    citizen_id = body.citizen_id
    if citizen_id is None:
        row = (
            db.client.from_("citizens").select("id")
            .eq("cnp", DEFAULT_DEMO_CITIZEN_CNP)
            .single().execute()
        )
        if not row.data:
            raise HTTPException(status_code=500, detail="Default demo citizen not seeded")
        citizen_id = UUID(row.data["id"])

    cid = str(citizen_id)

    # 1) Delete processed_events first (FK to ledger)
    pe = db.client.from_("processed_events").delete().in_(
        "ledger_id",
        [
            r["id"] for r in (
                db.client.from_("ledger").select("id").eq("citizen_id", cid).execute().data
                or []
            )
        ],
    ).execute()
    pe_count = len(pe.data) if pe.data else 0

    # 2) Delete ledger rows for this citizen
    led = db.client.from_("ledger").delete().eq("citizen_id", cid).execute()
    led_count = len(led.data) if led.data else 0

    # 3) Delete reminders
    rem = db.client.from_("reminders").delete().eq("citizen_id", cid).execute()
    rem_count = len(rem.data) if rem.data else 0

    # 4) Delete documents (cascades none since we cleared ledger above)
    doc = db.client.from_("documents").delete().eq("citizen_id", cid).execute()
    doc_count = len(doc.data) if doc.data else 0

    # 5) Re-apply seed reminders SQL (subset: only the relevant rows for this citizen)
    seeded = _reapply_seed_reminders(db, citizen_id)

    return ResetResponse(
        ok=True,
        citizen_id=citizen_id,
        counts=ResetCounts(
            documents_deleted=doc_count,
            reminders_deleted=rem_count,
            ledger_deleted=led_count,
            processed_events_deleted=pe_count,
            reminders_seeded=seeded,
        ),
    )


def _reapply_seed_reminders(db, citizen_id: UUID) -> int:
    """Re-run the relevant rows from 005_seed_reminders.sql for one citizen."""
    sql_path = Path(__file__).parent.parent / "migrations" / "005_seed_reminders.sql"
    if not sql_path.exists():
        return 0
    text = sql_path.read_text(encoding="utf-8")
    # Strip the DELETE prelude (we already wiped) and execute INSERTs via raw SQL RPC.
    # Supabase Python client: db.client.rpc('exec_sql', {...}) requires a server-side
    # function; instead we hand-parse and call .insert() with the static rows.
    return _seed_for_citizen(db, citizen_id)


def _seed_for_citizen(db, citizen_id: UUID) -> int:
    """Hard-coded mirror of 005_seed_reminders.sql, keyed by citizen.cnp."""
    citizen = (
        db.client.from_("citizens").select("cnp").eq("id", str(citizen_id))
        .single().execute().data
    )
    if not citizen:
        return 0
    cnp = citizen["cnp"]
    seeds: list[dict] = []
    if cnp == "2851014123456":
        seeds = [
            {
                "citizen_id": str(citizen_id),
                "kind": "in_scope_procedure",
                "procedure_id": "preschimbare-ci",
                "title": "Cartea de identitate expiră în 23 de zile",
                "status": "pending",
            },
            {
                "citizen_id": str(citizen_id),
                "kind": "external_redirect",
                "redirect_target": "CNAS",
                "title": "Actualizare medic de familie după schimbare adresă",
                "status": "pending",
            },
        ]
    elif cnp == "1900215987654":
        seeds = [{
            "citizen_id": str(citizen_id),
            "kind": "external_redirect",
            "redirect_target": "DRPCIV",
            "title": "Actualizare certificat înmatriculare auto (termen 30 zile)",
            "status": "pending",
        }]

    if not seeds:
        return 0
    res = db.client.from_("reminders").insert(seeds).execute()
    return len(res.data or [])
```

- [ ] **Step 4: Mount the router**

Add to `backend/app/main.py`:

```python
from app.demo import router as demo_router
app.include_router(demo_router)
```

- [ ] **Step 5: Run tests; verify all pass**

Run: `cd backend && pytest tests/test_demo_reset.py -v`
Expected: 5/5 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/demo.py backend/app/main.py backend/tests/test_demo_reset.py
git commit -m "feat(plan-4): demo reset endpoint with TDD"
```

---

## Task 9: `PATCH /citizens/me/attributes` endpoint (TDD)

**Files:**
- Modify: `backend/app/citizens.py`
- Test: `backend/tests/test_citizens_attributes.py`

Shallow-merges request body into `citizens.attributes` JSONB. Used by accessibility toggles.

- [ ] **Step 1: Write failing tests**

Write `backend/tests/test_citizens_attributes.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_patch_requires_auth(client):
    res = client.patch("/citizens/me/attributes", json={"large_text": True})
    assert res.status_code == 401


def test_patch_shallow_merges_attribute(client, auth_header, default_citizen_id, db_real):
    res = client.patch(
        "/citizens/me/attributes",
        headers=auth_header,
        json={"accessibility": {"large_text": True}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["attributes"]["accessibility"]["large_text"] is True

    # Other attributes preserved
    row = (
        db_real.from_("citizens").select("attributes")
        .eq("id", str(default_citizen_id)).single().execute().data
    )
    # owns_vehicle was in the seed; should still be present after PATCH
    assert "owns_vehicle" in row["attributes"]


def test_patch_merges_nested_accessibility_keys(client, auth_header, db_real,
                                                  default_citizen_id):
    client.patch(
        "/citizens/me/attributes",
        headers=auth_header,
        json={"accessibility": {"voice_only": True}},
    )
    client.patch(
        "/citizens/me/attributes",
        headers=auth_header,
        json={"accessibility": {"simple_language": True}},
    )
    row = (
        db_real.from_("citizens").select("attributes")
        .eq("id", str(default_citizen_id)).single().execute().data
    )
    acc = row["attributes"]["accessibility"]
    assert acc["voice_only"] is True
    assert acc["simple_language"] is True


def test_patch_rejects_unknown_top_level_key(client, auth_header):
    # Allowlist enforced — only whitelisted top-level keys can be patched.
    res = client.patch(
        "/citizens/me/attributes",
        headers=auth_header,
        json={"hacked_field": "evil"},
    )
    assert res.status_code == 400
    assert "not permitted" in res.json()["detail"].lower()
```

- [ ] **Step 2: Run tests; verify they fail**

Run: `cd backend && pytest tests/test_citizens_attributes.py -v`
Expected: All FAIL (endpoint doesn't exist).

- [ ] **Step 3: Implement the endpoint**

Edit `backend/app/citizens.py`. Add:

```python
from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import Any


# Top-level attribute keys we permit citizens to set/merge.
ALLOWED_ATTRIBUTE_KEYS = {
    "owns_vehicle",
    "marital_status",
    "has_children",
    "preferred_language",
    "accessibility",
    "current_address",
}


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base or {})
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@router.patch("/me/attributes")
def patch_my_attributes(
    patch: dict[str, Any],
    citizen=Depends(get_current_citizen),
    db=Depends(get_db),
):
    unknown = set(patch.keys()) - ALLOWED_ATTRIBUTE_KEYS
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Top-level keys not permitted: {sorted(unknown)}",
        )

    current = (
        db.client.from_("citizens").select("attributes")
        .eq("id", str(citizen.id)).single().execute().data
    )
    merged = _deep_merge(current["attributes"] or {}, patch)

    db.client.from_("citizens").update({"attributes": merged}).eq(
        "id", str(citizen.id)
    ).execute()

    return {"id": str(citizen.id), "attributes": merged}
```

(Use the existing router and dependencies already defined in `citizens.py` by Plan 2. If the router prefix differs from `/citizens`, the route path becomes `/me/attributes` on that router.)

- [ ] **Step 4: Run tests; verify they pass**

Run: `cd backend && pytest tests/test_citizens_attributes.py -v`
Expected: 4/4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/citizens.py backend/tests/test_citizens_attributes.py
git commit -m "feat(plan-4): PATCH /citizens/me/attributes with TDD"
```

---

## Task 10: `/healthz` endpoint

**Files:**
- Create: `backend/app/health.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_healthz.py`

Checks: Supabase reachable, Gemini key set, Twilio token set. Returns 200 always (so Railway healthchecks succeed); returns details in body.

- [ ] **Step 1: Write tests**

Write `backend/tests/test_healthz.py`:

```python
import os
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_healthz_returns_200(client):
    res = client.get("/healthz")
    assert res.status_code == 200


def test_healthz_body_structure(client):
    res = client.get("/healthz")
    body = res.json()
    assert "ok" in body
    assert "checks" in body
    assert "supabase" in body["checks"]
    assert "gemini_key" in body["checks"]
    assert "twilio_token" in body["checks"]


def test_healthz_reports_missing_keys(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    res = client.get("/healthz")
    assert res.json()["checks"]["gemini_key"] is False
```

- [ ] **Step 2: Implement health.py**

Write `backend/app/health.py`:

```python
import os
import logging

from fastapi import APIRouter, Depends

from app.db import get_db


router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)


@router.get("/healthz")
def healthz(db=Depends(get_db)):
    checks = {
        "supabase": _check_supabase(db),
        "gemini_key": bool(os.environ.get("GEMINI_API_KEY")),
        "twilio_token": bool(os.environ.get("TWILIO_AUTH_TOKEN")),
    }
    return {"ok": all(checks.values()), "checks": checks}


def _check_supabase(db) -> bool:
    try:
        db.client.from_("citizens").select("id").limit(1).execute()
        return True
    except Exception:
        log.exception("supabase healthcheck failed")
        return False
```

Mount in `main.py`:

```python
from app.health import router as health_router
app.include_router(health_router)
```

- [ ] **Step 3: Run tests; verify pass**

Run: `cd backend && pytest tests/test_healthz.py -v`
Expected: 3/3 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/health.py backend/app/main.py backend/tests/test_healthz.py
git commit -m "feat(plan-4): /healthz endpoint reporting supabase/gemini/twilio status"
```

---

## Task 11: Sentry integration (backend + frontend)

**Files:**
- Modify: `backend/app/main.py`
- Create: `frontend/sentry.client.config.ts`
- Create: `frontend/sentry.server.config.ts`
- Create: `frontend/sentry.edge.config.ts`
- Modify: `frontend/next.config.ts`

- [ ] **Step 1: Backend Sentry init**

Edit `backend/app/main.py` near the top:

```python
import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

if os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        environment=os.environ.get("APP_ENV", "production"),
        traces_sample_rate=0.1,
        integrations=[FastApiIntegration()],
        send_default_pii=False,
    )
```

- [ ] **Step 2: Frontend Sentry init**

Run the Sentry wizard or write configs by hand. Create `frontend/sentry.client.config.ts`:

```typescript
import * as Sentry from "@sentry/nextjs";

if (process.env.NEXT_PUBLIC_SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    environment: process.env.NEXT_PUBLIC_APP_ENV ?? "production",
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 1.0,
    integrations: [Sentry.replayIntegration({ maskAllText: true, blockAllMedia: true })],
  });
}
```

Create `frontend/sentry.server.config.ts`:

```typescript
import * as Sentry from "@sentry/nextjs";

if (process.env.SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.SENTRY_DSN,
    environment: process.env.APP_ENV ?? "production",
    tracesSampleRate: 0.1,
  });
}
```

Create `frontend/sentry.edge.config.ts`:

```typescript
import * as Sentry from "@sentry/nextjs";

if (process.env.SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.SENTRY_DSN,
    environment: process.env.APP_ENV ?? "production",
    tracesSampleRate: 0.1,
  });
}
```

Update `frontend/next.config.ts`:

```typescript
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig = {
  // ... existing config from Plan 1 ...
};

export default withSentryConfig(nextConfig, {
  silent: true,
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  widenClientFileUpload: true,
  hideSourceMaps: true,
});
```

- [ ] **Step 3: Manual smoke test**

Set `SENTRY_DSN` and `NEXT_PUBLIC_SENTRY_DSN` env vars locally; throw a test error in dev, confirm it appears in Sentry. Then clear the test event.

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py frontend/sentry.client.config.ts \
        frontend/sentry.server.config.ts frontend/sentry.edge.config.ts \
        frontend/next.config.ts
git commit -m "feat(plan-4): wire Sentry on backend + frontend"
```

---

## Task 12: Global Romanian error boundary

**Files:**
- Create: `frontend/app/error.tsx`

- [ ] **Step 1: Write the error boundary**

Create `frontend/app/error.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import * as Sentry from "@sentry/nextjs";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="ro">
      <body className="min-h-screen flex items-center justify-center bg-gray-50">
        <main
          role="alert"
          className="max-w-md mx-auto p-8 bg-white rounded-2xl shadow-lg text-center"
        >
          <h1 className="text-2xl font-semibold mb-3">A apărut o eroare</h1>
          <p className="text-gray-600 mb-6">
            Ne pare rău — ceva nu a mers cum trebuia. Echipa CivicAI a fost
            notificată automat.
          </p>
          <button
            onClick={() => reset()}
            className="px-6 py-3 rounded-xl bg-blue-600 text-white font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Reîncearcă
          </button>
          {error.digest && (
            <p className="mt-6 text-xs text-gray-400">Cod: {error.digest}</p>
          )}
        </main>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Manual verification**

Add a temporary `throw new Error("test")` in a page, confirm the error boundary renders with Romanian text and the Reset button works, then remove the throw.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/error.tsx
git commit -m "feat(plan-4): Romanian global error boundary"
```

---

## Task 13: Shared framer-motion helpers + reduced-motion guard (TDD)

**Files:**
- Create: `frontend/lib/motion.ts`
- Test: `frontend/tests/motion.test.ts`

- [ ] **Step 1: Write failing tests**

Write `frontend/tests/motion.test.ts`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { variantsWithReducedMotion, reminderListContainer, reminderItem,
         fieldHighlightPulse } from "@/lib/motion";

describe("variantsWithReducedMotion", () => {
  it("returns original variants when prefers-reduced-motion is false", () => {
    const variants = { hidden: { opacity: 0 }, visible: { opacity: 1 } };
    const out = variantsWithReducedMotion(variants, false);
    expect(out).toEqual(variants);
  });

  it("flattens transitions to instant when prefers-reduced-motion is true", () => {
    const variants = {
      hidden: { opacity: 0, y: 20, transition: { duration: 0.5 } },
      visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
    };
    const out = variantsWithReducedMotion(variants, true);
    expect(out.hidden.transition).toEqual({ duration: 0 });
    expect(out.visible.transition).toEqual({ duration: 0 });
  });
});

describe("preset variants", () => {
  it("reminderListContainer stagger is positive", () => {
    expect(reminderListContainer.visible.transition.staggerChildren).toBeGreaterThan(0);
  });

  it("reminderItem has both hidden and visible", () => {
    expect(reminderItem.hidden).toBeDefined();
    expect(reminderItem.visible).toBeDefined();
  });

  it("fieldHighlightPulse animates a background ring", () => {
    expect(fieldHighlightPulse.pulse).toBeDefined();
  });
});
```

- [ ] **Step 2: Run tests; verify they fail**

Run: `cd frontend && npx vitest run tests/motion.test.ts`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement motion.ts**

Create `frontend/lib/motion.ts`:

```typescript
import { Variants } from "framer-motion";


export function variantsWithReducedMotion<T extends Variants>(
  variants: T,
  reducedMotion: boolean,
): T {
  if (!reducedMotion) return variants;
  const out: any = {};
  for (const [key, value] of Object.entries(variants)) {
    if (typeof value === "object" && value !== null) {
      out[key] = { ...value, transition: { duration: 0 } };
    } else {
      out[key] = value;
    }
  }
  return out as T;
}


export const reminderListContainer: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.05 },
  },
};


export const reminderItem: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: "easeOut" },
  },
};


export const pageTransition: Variants = {
  initial: { opacity: 0, y: 8 },
  enter: { opacity: 1, y: 0, transition: { duration: 0.25 } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.15 } },
};


export const fieldHighlightPulse: Variants = {
  pulse: {
    boxShadow: [
      "0 0 0 0 rgba(59, 130, 246, 0)",
      "0 0 0 6px rgba(59, 130, 246, 0.35)",
      "0 0 0 0 rgba(59, 130, 246, 0)",
    ],
    transition: { duration: 0.9, times: [0, 0.4, 1] },
  },
};


export const modeSwitch: Variants = {
  hidden: { opacity: 0, x: -8 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.2 } },
  exit: { opacity: 0, x: 8, transition: { duration: 0.15 } },
};


export const messageFadeIn: Variants = {
  hidden: { opacity: 0, y: 6 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.2 } },
};


/**
 * Tiny React hook reading the OS-level prefers-reduced-motion media query.
 * Used by every animated component in the app.
 */
import { useEffect, useState } from "react";

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}
```

- [ ] **Step 4: Run tests; verify pass**

Run: `cd frontend && npx vitest run tests/motion.test.ts`
Expected: 5/5 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/motion.ts frontend/tests/motion.test.ts
git commit -m "feat(plan-4): shared motion variants + reduced-motion guard with TDD"
```

---

## Task 14: ReminderCard polish (kind-specific layouts + actions)

**Files:**
- Modify: `frontend/components/ReminderCard.tsx`
- Modify: `frontend/lib/api.ts` (add reminder client methods)
- Test: `frontend/tests/ReminderCard.test.tsx`

- [ ] **Step 1: Add API client methods**

Edit `frontend/lib/api.ts`, add:

```typescript
import { Reminder, Document } from "./types";

export async function getReminders(): Promise<Reminder[]> {
  return request<Reminder[]>("GET", "/reminders");
}

export async function startReminder(
  reminderId: string
): Promise<{ id: string; status: string; document: Document }> {
  return request("POST", `/reminders/${reminderId}/start`);
}

export async function dismissReminder(reminderId: string): Promise<Reminder> {
  return request("POST", `/reminders/${reminderId}/dismiss`);
}

export async function patchMyAttributes(
  patch: Record<string, unknown>
): Promise<{ id: string; attributes: Record<string, unknown> }> {
  return request("PATCH", "/citizens/me/attributes", patch);
}

export async function resetDemo(citizenId?: string): Promise<unknown> {
  return request(
    "POST",
    "/demo/reset",
    { citizen_id: citizenId ?? null },
    { extraHeaders: { "X-Demo-Token": process.env.NEXT_PUBLIC_DEMO_TOKEN ?? "" } }
  );
}
```

(Match the existing `request` helper signature from Plan 1's `lib/api.ts`. If it doesn't accept `extraHeaders`, add support.)

- [ ] **Step 2: Write component tests**

Write `frontend/tests/ReminderCard.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ReminderCard } from "@/components/ReminderCard";
import * as api from "@/lib/api";

vi.mock("@/lib/api");
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));


const inScope = {
  id: "r1",
  citizen_id: "c1",
  kind: "in_scope_procedure" as const,
  procedure_id: "preschimbare-ci",
  title: "Preschimbare CI",
  status: "pending" as const,
  created_at: "2026-05-23T00:00:00Z",
};

const external = {
  id: "r2",
  citizen_id: "c1",
  kind: "external_redirect" as const,
  redirect_target: "DRPCIV",
  title: "Actualizare auto",
  status: "pending" as const,
  created_at: "2026-05-23T00:00:00Z",
};


describe("ReminderCard", () => {
  it("renders 'Start now' button for in_scope reminder", () => {
    render(<ReminderCard reminder={inScope} />);
    expect(screen.getByRole("button", { name: /start/i })).toBeInTheDocument();
  });

  it("renders 'Vezi detalii' disclosure for external_redirect", () => {
    render(<ReminderCard reminder={external} />);
    expect(screen.getByRole("button", { name: /vezi detalii/i })).toBeInTheDocument();
  });

  it("clicking 'Start now' calls startReminder and navigates", async () => {
    (api.startReminder as any).mockResolvedValue({
      id: "r1",
      status: "started",
      document: { id: "d99", procedure_id: "preschimbare-ci", status: "draft" },
    });
    render(<ReminderCard reminder={inScope} />);
    fireEvent.click(screen.getByRole("button", { name: /start/i }));
    await waitFor(() =>
      expect(api.startReminder).toHaveBeenCalledWith("r1")
    );
  });

  it("external_redirect disclosure shows contact info + roadmap note", () => {
    render(<ReminderCard reminder={external} />);
    fireEvent.click(screen.getByRole("button", { name: /vezi detalii/i }));
    expect(screen.getByText(/DRPCIV/)).toBeInTheDocument();
    expect(screen.getByText(/roadmap/i)).toBeInTheDocument();
  });

  it("overdue due_date shows red highlight", () => {
    const overdue = { ...inScope, due_date: "2020-01-01" };
    render(<ReminderCard reminder={overdue} />);
    const card = screen.getByTestId("reminder-card");
    expect(card.className).toMatch(/red/);
  });
});
```

- [ ] **Step 3: Write the component**

Edit `frontend/components/ReminderCard.tsx`:

```tsx
"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { Reminder } from "@/lib/types";
import { reminderItem, usePrefersReducedMotion, variantsWithReducedMotion }
  from "@/lib/motion";
import { startReminder, dismissReminder } from "@/lib/api";
import { i18n } from "@/lib/i18n";


const REDIRECT_CONTACT: Record<string, { name: string; url: string; phone?: string }> = {
  ANAF: { name: "ANAF", url: "https://anaf.ro/", phone: "031 403 91 60" },
  CNAS: { name: "CNAS", url: "https://cnas.ro/" },
  DRPCIV: { name: "DRPCIV", url: "https://drpciv.ro/" },
  ONRC: { name: "ONRC", url: "https://onrc.ro/" },
  SPCEP: { name: "SPCEP Cluj", url: "https://primariaclujnapoca.ro/" },
};


export function ReminderCard({ reminder }: { reminder: Reminder }) {
  const router = useRouter();
  const reduced = usePrefersReducedMotion();
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const overdue = reminder.due_date && new Date(reminder.due_date) < new Date();
  const variants = variantsWithReducedMotion(reminderItem, reduced);

  return (
    <motion.article
      data-testid="reminder-card"
      variants={variants}
      className={[
        "rounded-2xl border p-5 bg-white shadow-sm transition-colors",
        overdue
          ? "border-red-400 ring-1 ring-red-200"
          : "border-gray-200",
      ].join(" ")}
    >
      <header className="flex justify-between items-start gap-3 mb-3">
        <div>
          <p className="text-xs text-gray-500 mb-1">
            {reminder.kind === "in_scope_procedure"
              ? "Acțiune recomandată"
              : `Redirecționare către ${reminder.redirect_target ?? "instituție"}`}
          </p>
          <h3 className="font-semibold text-gray-900">{reminder.title}</h3>
          {reminder.due_date && (
            <p className={`text-xs mt-1 ${overdue ? "text-red-600" : "text-gray-500"}`}>
              Termen: {new Date(reminder.due_date).toLocaleDateString("ro-RO")}
              {overdue && " (depășit)"}
            </p>
          )}
        </div>
        <button
          aria-label="Respinge"
          className="text-gray-400 hover:text-gray-600 text-sm"
          onClick={async () => {
            await dismissReminder(reminder.id);
            // Parent should re-fetch via SWR / mutate; here we hide locally.
            const el = document.getElementById(`reminder-${reminder.id}`);
            if (el) el.style.display = "none";
          }}
        >
          ✕
        </button>
      </header>

      {reminder.kind === "in_scope_procedure" ? (
        <button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              const result = await startReminder(reminder.id);
              router.push(`/req/${result.document.id}`);
            } catch (e: any) {
              setError(e?.message ?? "Eroare necunoscută");
              setBusy(false);
            }
          }}
          className="px-4 py-2 rounded-xl bg-blue-600 text-white font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60"
        >
          {busy ? "Se inițiază..." : "Start acum"}
        </button>
      ) : (
        <div>
          <button
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="px-4 py-2 rounded-xl border border-gray-300 hover:bg-gray-50"
          >
            {expanded ? "Ascunde" : "Vezi detalii"}
          </button>
          {expanded && reminder.redirect_target && (
            <div className="mt-3 space-y-2 text-sm text-gray-700">
              <p>
                Această procedură nu este în scope-ul primăriei. O poți rezolva
                pe site-ul oficial:
              </p>
              <p>
                <a
                  href={REDIRECT_CONTACT[reminder.redirect_target]?.url ?? "#"}
                  className="text-blue-700 underline"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {REDIRECT_CONTACT[reminder.redirect_target]?.name ??
                   reminder.redirect_target}
                </a>
                {REDIRECT_CONTACT[reminder.redirect_target]?.phone && (
                  <> — Tel: {REDIRECT_CONTACT[reminder.redirect_target]?.phone}</>
                )}
              </p>
              <p className="text-xs text-gray-500 italic">
                Pe roadmap: integrare directă, astfel încât să nu mai fie nevoie
                să ieși din CivicAI.
              </p>
            </div>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">{error}</p>
      )}
    </motion.article>
  );
}
```

- [ ] **Step 4: Run tests; verify pass**

Run: `cd frontend && npx vitest run tests/ReminderCard.test.tsx`
Expected: 5/5 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ReminderCard.tsx frontend/lib/api.ts \
        frontend/tests/ReminderCard.test.tsx
git commit -m "feat(plan-4): reminder card kind-specific layouts + actions"
```

---

## Task 15: RemindersList container with stagger + sort + empty state

**Files:**
- Create: `frontend/components/RemindersList.tsx`
- Modify: `frontend/app/page.tsx` (mount the list)
- Test: `frontend/tests/RemindersList.test.tsx`

- [ ] **Step 1: Write tests**

Write `frontend/tests/RemindersList.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { RemindersList } from "@/components/RemindersList";
import * as api from "@/lib/api";

vi.mock("@/lib/api");


describe("RemindersList", () => {
  it("shows empty state in Romanian when no reminders", async () => {
    (api.getReminders as any).mockResolvedValue([]);
    render(<RemindersList />);
    await waitFor(() =>
      expect(screen.getByText(/nu ai acțiuni recomandate/i)).toBeInTheDocument()
    );
  });

  it("renders reminders sorted by due_date ascending, undated last", async () => {
    (api.getReminders as any).mockResolvedValue([
      { id: "a", title: "Far future", due_date: "2030-01-01", kind: "in_scope_procedure", status: "pending", citizen_id: "c", created_at: "" },
      { id: "b", title: "Near", due_date: "2026-06-01", kind: "in_scope_procedure", status: "pending", citizen_id: "c", created_at: "" },
      { id: "c", title: "Undated", kind: "external_redirect", status: "pending", citizen_id: "c", created_at: "", redirect_target: "ANAF" },
    ]);
    render(<RemindersList />);
    await waitFor(() => {
      const titles = screen.getAllByRole("article").map(el =>
        el.querySelector("h3")?.textContent
      );
      expect(titles).toEqual(["Near", "Far future", "Undated"]);
    });
  });

  it("renders counter with active count", async () => {
    (api.getReminders as any).mockResolvedValue([
      { id: "a", title: "x", kind: "in_scope_procedure", status: "pending", citizen_id: "c", created_at: "" },
      { id: "b", title: "y", kind: "in_scope_procedure", status: "pending", citizen_id: "c", created_at: "" },
    ]);
    render(<RemindersList />);
    await waitFor(() =>
      expect(screen.getByText(/2 active/i)).toBeInTheDocument()
    );
  });
});
```

- [ ] **Step 2: Implement RemindersList**

Create `frontend/components/RemindersList.tsx`:

```tsx
"use client";

import useSWR from "swr";
import { motion } from "framer-motion";
import { getReminders } from "@/lib/api";
import { ReminderCard } from "./ReminderCard";
import {
  reminderListContainer,
  variantsWithReducedMotion,
  usePrefersReducedMotion,
} from "@/lib/motion";


export function RemindersList() {
  const { data: reminders, isLoading } = useSWR("/reminders", getReminders);
  const reduced = usePrefersReducedMotion();

  if (isLoading) return <p className="text-sm text-gray-500">Se încarcă...</p>;
  if (!reminders) return null;

  if (reminders.length === 0) {
    return (
      <section aria-label="Acțiuni recomandate" className="py-6">
        <h2 className="text-lg font-semibold mb-2">Acțiuni recomandate</h2>
        <p className="text-gray-500 text-sm">
          Nu ai acțiuni recomandate momentan.
        </p>
      </section>
    );
  }

  const sorted = [...reminders].sort((a, b) => {
    if (a.due_date && b.due_date) {
      return new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
    }
    if (a.due_date) return -1;
    if (b.due_date) return 1;
    return 0;
  });

  const containerVariants = variantsWithReducedMotion(reminderListContainer, reduced);

  return (
    <section aria-label="Acțiuni recomandate" className="py-6">
      <header className="flex justify-between items-baseline mb-3">
        <h2 className="text-lg font-semibold">Următoarele acțiuni recomandate</h2>
        <span className="text-sm text-gray-500" aria-live="polite">
          {sorted.length} active
        </span>
      </header>
      <motion.div
        initial="hidden"
        animate="visible"
        variants={containerVariants}
        className="grid gap-3"
      >
        {sorted.map((r) => (
          <div key={r.id} id={`reminder-${r.id}`}>
            <ReminderCard reminder={r} />
          </div>
        ))}
      </motion.div>
    </section>
  );
}
```

- [ ] **Step 3: Mount in citizen home**

Edit `frontend/app/page.tsx` — add `RemindersList` above the documents list:

```tsx
import { RemindersList } from "@/components/RemindersList";

// inside the JSX:
<RemindersList />
<DocumentList />  // existing from Plan 1
```

- [ ] **Step 4: Run tests; verify pass**

Run: `cd frontend && npx vitest run tests/RemindersList.test.tsx`
Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/RemindersList.tsx frontend/app/page.tsx \
        frontend/tests/RemindersList.test.tsx
git commit -m "feat(plan-4): RemindersList with stagger animation + empty state"
```

---

## Task 16: Demo reset button (dev panel)

**Files:**
- Create: `frontend/components/DemoResetButton.tsx`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/components/DemoResetButton.tsx`:

```tsx
"use client";

import { useState } from "react";
import { resetDemo } from "@/lib/api";


export function DemoResetButton() {
  if (process.env.NEXT_PUBLIC_DEMO_MODE !== "1") return null;

  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <button
        onClick={async () => {
          if (busy) return;
          setBusy(true);
          setMsg("Se resetează...");
          try {
            await resetDemo();
            setMsg("Reset OK — se reîncarcă");
            setTimeout(() => window.location.reload(), 600);
          } catch (e: any) {
            setMsg(`Eroare: ${e?.message ?? "necunoscută"}`);
            setBusy(false);
          }
        }}
        className="px-4 py-2 rounded-full bg-yellow-400 text-black font-medium shadow-lg hover:bg-yellow-300 focus:outline-none focus:ring-2 focus:ring-yellow-600"
        aria-label="Resetează datele demo"
      >
        Reset demo
      </button>
      {msg && (
        <p className="absolute right-0 mt-2 px-3 py-1 bg-black text-white text-xs rounded">
          {msg}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Mount in layout**

Edit `frontend/app/layout.tsx`:

```tsx
import { DemoResetButton } from "@/components/DemoResetButton";

// Inside the <body> wrapper, after children:
<DemoResetButton />
```

- [ ] **Step 3: Manual smoke test**

With `NEXT_PUBLIC_DEMO_MODE=1` and `NEXT_PUBLIC_DEMO_TOKEN` set, navigate to citizen home; click the button; verify page reloads with seeded data.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/DemoResetButton.tsx frontend/app/layout.tsx
git commit -m "feat(plan-4): demo reset floating button (dev mode only)"
```

---

## Task 17: Accessibility toggles — wire behaviors

**Files:**
- Modify: `frontend/components/AccessibilityToggles.tsx`
- Modify: `frontend/lib/i18n.ts` (consume simple_language flag)
- Modify: `frontend/app/layout.tsx` (apply large_text class)
- Test: `frontend/tests/AccessibilityToggles.test.tsx`

Toggles tied to behavior:
- `voice_only` → persist via PATCH; on mount of procedure pages, call `useVoiceAgent().start()` and keep mic hot; TTS narrates state changes. (Behavior consumes Plan 3's hook.)
- `simple_language` → persist via PATCH; pass `simple_language: true` in `/agent/chat` body and `/voice/session` body; switch i18n strings to `.simple` variants.
- `large_text` → persist via PATCH; toggles `class="text-125"` on `<html>` (Tailwind utility scales root font-size).

- [ ] **Step 1: Write tests**

Write `frontend/tests/AccessibilityToggles.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AccessibilityToggles } from "@/components/AccessibilityToggles";
import * as api from "@/lib/api";

vi.mock("@/lib/api");


describe("AccessibilityToggles", () => {
  it("toggling large_text persists via PATCH and adds class to html", async () => {
    (api.patchMyAttributes as any).mockResolvedValue({
      id: "c1",
      attributes: { accessibility: { large_text: true } },
    });
    render(<AccessibilityToggles initial={{ large_text: false }} />);
    fireEvent.click(screen.getByRole("switch", { name: /text mai mare/i }));
    await waitFor(() => {
      expect(api.patchMyAttributes).toHaveBeenCalledWith({
        accessibility: { large_text: true },
      });
    });
    expect(document.documentElement.classList.contains("text-125")).toBe(true);
  });

  it("toggling simple_language persists via PATCH", async () => {
    (api.patchMyAttributes as any).mockResolvedValue({
      id: "c1",
      attributes: { accessibility: { simple_language: true } },
    });
    render(<AccessibilityToggles initial={{ simple_language: false }} />);
    fireEvent.click(screen.getByRole("switch", { name: /explică-mi mai simplu/i }));
    await waitFor(() =>
      expect(api.patchMyAttributes).toHaveBeenCalledWith({
        accessibility: { simple_language: true },
      })
    );
  });

  it("toggling voice_only persists via PATCH", async () => {
    (api.patchMyAttributes as any).mockResolvedValue({
      id: "c1",
      attributes: { accessibility: { voice_only: true } },
    });
    render(<AccessibilityToggles initial={{ voice_only: false }} />);
    fireEvent.click(screen.getByRole("switch", { name: /mod vocal/i }));
    await waitFor(() =>
      expect(api.patchMyAttributes).toHaveBeenCalledWith({
        accessibility: { voice_only: true },
      })
    );
  });

  it("removes text-125 class when large_text disabled", async () => {
    (api.patchMyAttributes as any).mockResolvedValue({
      id: "c1",
      attributes: { accessibility: { large_text: false } },
    });
    document.documentElement.classList.add("text-125");
    render(<AccessibilityToggles initial={{ large_text: true }} />);
    fireEvent.click(screen.getByRole("switch", { name: /text mai mare/i }));
    await waitFor(() =>
      expect(document.documentElement.classList.contains("text-125")).toBe(false)
    );
  });
});
```

- [ ] **Step 2: Implement the component**

Edit `frontend/components/AccessibilityToggles.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { patchMyAttributes } from "@/lib/api";


type Prefs = {
  voice_only?: boolean;
  simple_language?: boolean;
  large_text?: boolean;
};


export function AccessibilityToggles({ initial }: { initial?: Prefs }) {
  const [prefs, setPrefs] = useState<Prefs>(initial ?? {});

  // Apply large_text class to <html> on mount + every change.
  useEffect(() => {
    if (typeof document === "undefined") return;
    if (prefs.large_text) {
      document.documentElement.classList.add("text-125");
      announce("Mod text mărit activat.");
    } else {
      document.documentElement.classList.remove("text-125");
    }
  }, [prefs.large_text]);

  // Store voice_only and simple_language in a window-level store that the
  // procedure pages read at mount time to decide whether to start the
  // voice hook. (See useVoiceAgent in Plan 3 — it accepts a `preferences`
  // object in start(); RemindersList / procedure flow reads from prefs.)
  useEffect(() => {
    if (typeof window === "undefined") return;
    (window as any).__civicAccessibility = prefs;
  }, [prefs]);

  async function toggle(key: keyof Prefs) {
    const next = !prefs[key];
    setPrefs((p) => ({ ...p, [key]: next }));
    await patchMyAttributes({ accessibility: { [key]: next } });
  }

  return (
    <section
      aria-label="Setări accesibilitate"
      className="p-4 rounded-2xl bg-gray-50 border border-gray-200 space-y-3"
    >
      <h3 className="font-semibold">Accesibilitate</h3>

      <ToggleRow
        label="Mod vocal (mic pornit, narațiune)"
        checked={!!prefs.voice_only}
        onChange={() => toggle("voice_only")}
      />

      <ToggleRow
        label="Explică-mi mai simplu"
        description="Răspunsuri pentru clasa a 6-a, fără jargon"
        checked={!!prefs.simple_language}
        onChange={() => toggle("simple_language")}
      />

      <ToggleRow
        label="Text mai mare"
        checked={!!prefs.large_text}
        onChange={() => toggle("large_text")}
      />
    </section>
  );
}


function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label className="flex items-start gap-3 cursor-pointer">
      <input
        type="checkbox"
        role="switch"
        aria-label={label}
        checked={checked}
        onChange={onChange}
        className="mt-1 h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
      />
      <span>
        <span className="block font-medium">{label}</span>
        {description && (
          <span className="block text-sm text-gray-600">{description}</span>
        )}
      </span>
    </label>
  );
}


function announce(text: string) {
  if (typeof document === "undefined") return;
  const live = document.getElementById("a11y-live") ?? document.body;
  const el = document.createElement("div");
  el.setAttribute("aria-live", "assertive");
  el.style.position = "absolute";
  el.style.left = "-9999px";
  el.textContent = text;
  live.appendChild(el);
  setTimeout(() => el.remove(), 1500);
}
```

- [ ] **Step 3: Add the Tailwind utility for `text-125`**

Edit `frontend/tailwind.config.ts`. Add to `theme.extend`:

```typescript
theme: {
  extend: {
    // ... existing extensions ...
  },
  // outside extend, add a layer:
},
plugins: [
  function ({ addUtilities }: any) {
    addUtilities({
      ".text-125": {
        fontSize: "125%",
        lineHeight: "1.5",
      },
    });
  },
],
```

- [ ] **Step 4: Wire i18n.ts to read the simple_language flag**

Edit `frontend/lib/i18n.ts` so that strings have `.standard` and `.simple` variants and the active variant is selected based on `window.__civicAccessibility.simple_language`:

```typescript
type I18nKey =
  | "home.greeting"
  | "home.actions.title"
  | "procedure.continue"
  | "delivery.send"
  | "delivery.save"
  | "delivery.print";

type Variants = { standard: string; simple: string };


const STRINGS: Record<I18nKey, Variants> = {
  "home.greeting": {
    standard: "Bună ziua",
    simple: "Salut",
  },
  "home.actions.title": {
    standard: "Următoarele acțiuni recomandate",
    simple: "Ce e bine să faci în continuare",
  },
  "procedure.continue": {
    standard: "Continuă",
    simple: "Mai departe",
  },
  "delivery.send": {
    standard: "Trimite la primărie",
    simple: "Trimite",
  },
  "delivery.save": {
    standard: "Salvează ca PDF",
    simple: "Descarcă",
  },
  "delivery.print": {
    standard: "Tipărește",
    simple: "Printează",
  },
};


export function t(key: I18nKey): string {
  const variants = STRINGS[key];
  if (!variants) return key;
  const simple =
    typeof window !== "undefined" &&
    (window as any).__civicAccessibility?.simple_language;
  return simple ? variants.simple : variants.standard;
}
```

(If Plan 1 already shipped a richer i18n with more strings, only ADD the `simple` variant for each existing key — do not remove keys.)

- [ ] **Step 5: Pass simple_language flag to /agent/chat in ChatPanel**

Edit `frontend/components/ChatPanel.tsx` where it calls the chat endpoint:

```tsx
// Wherever ChatPanel posts to /agent/chat:
const prefs = (typeof window !== "undefined" && (window as any).__civicAccessibility) ?? {};

const res = await chat({
  conversation_id: conv,
  document_id: docId,
  message: text,
  preferences: { simple_language: !!prefs.simple_language },
});
```

- [ ] **Step 6: Pass voice_only + simple_language to useVoiceAgent in procedure flow**

Edit `frontend/components/VocalFillFlow.tsx` (or whichever component currently invokes `useVoiceAgent`):

```tsx
const prefs = (typeof window !== "undefined" && (window as any).__civicAccessibility) ?? {};

await voice.start({
  documentId,
  preferences: {
    voice_only: !!prefs.voice_only,
    simple_language: !!prefs.simple_language,
  },
  onAgentMessage: (text) => { /* render */ },
  onTranscript: (text) => { /* render */ },
});
```

(Note: Plan 3 owns the real `useVoiceAgent`. Until Plan 3 lands, the stub throws; that's expected — Plan 4 just passes preferences correctly so when Plan 3 lands voice-only mode works.)

- [ ] **Step 7: Run tests; verify pass**

Run: `cd frontend && npx vitest run tests/AccessibilityToggles.test.tsx`
Expected: 4/4 PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/components/AccessibilityToggles.tsx \
        frontend/lib/i18n.ts \
        frontend/components/ChatPanel.tsx \
        frontend/components/VocalFillFlow.tsx \
        frontend/tailwind.config.ts \
        frontend/tests/AccessibilityToggles.test.tsx
git commit -m "feat(plan-4): wire accessibility toggles to behaviors"
```

---

## Task 18: Framer-motion polish across the app

**Files:**
- Modify: `frontend/components/ChatPanel.tsx` (message fade-in)
- Modify: `frontend/components/FormPreview.tsx` (field highlight pulse on autofill)
- Modify: `frontend/components/CompletionModeSelector.tsx` (mode-switch transition)
- Modify: `frontend/app/layout.tsx` (page transitions via `AnimatePresence`)

Every animation calls `usePrefersReducedMotion()` and uses `variantsWithReducedMotion`.

- [ ] **Step 1: ChatPanel message fade-in**

In `ChatPanel.tsx`, wrap each rendered message:

```tsx
import { AnimatePresence, motion } from "framer-motion";
import { messageFadeIn, variantsWithReducedMotion, usePrefersReducedMotion } from "@/lib/motion";

// inside the component:
const reduced = usePrefersReducedMotion();
const variants = variantsWithReducedMotion(messageFadeIn, reduced);

<AnimatePresence initial={false}>
  {messages.map((m) => (
    <motion.div
      key={m.id}
      initial="hidden"
      animate="visible"
      variants={variants}
      className={m.role === "user" ? "self-end" : "self-start"}
    >
      {m.text}
    </motion.div>
  ))}
</AnimatePresence>
```

- [ ] **Step 2: FormPreview autofill pulse**

In `FormPreview.tsx`, track which fields were just autofilled, animate them with `fieldHighlightPulse`:

```tsx
import { motion, useAnimationControls } from "framer-motion";
import { fieldHighlightPulse, usePrefersReducedMotion } from "@/lib/motion";

function PreviewField({ name, value, autofilled }: {
  name: string; value: string; autofilled?: boolean;
}) {
  const controls = useAnimationControls();
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    if (autofilled && !reduced) {
      controls.start("pulse");
    }
  }, [autofilled, reduced]);

  return (
    <motion.div
      animate={controls}
      variants={fieldHighlightPulse}
      className="px-3 py-2 rounded-md border border-gray-200"
    >
      <span className="text-xs text-gray-500">{name}:</span>{" "}
      <span className="font-medium">{value}</span>
    </motion.div>
  );
}
```

- [ ] **Step 3: CompletionModeSelector mode-switch transition**

In `CompletionModeSelector.tsx`:

```tsx
import { AnimatePresence, motion } from "framer-motion";
import { modeSwitch, variantsWithReducedMotion, usePrefersReducedMotion } from "@/lib/motion";

// Wrap the selected mode's body in AnimatePresence:
<AnimatePresence mode="wait">
  <motion.div
    key={activeMode}
    initial="hidden"
    animate="visible"
    exit="exit"
    variants={variantsWithReducedMotion(modeSwitch, useReducedMotion())}
  >
    {activeMode === "manual" && <ManualFillForm ... />}
    {activeMode === "guided" && <GuidedFillFlow ... />}
    {activeMode === "vocal" && <VocalFillFlow ... />}
  </motion.div>
</AnimatePresence>
```

- [ ] **Step 4: Page transitions via app/template.tsx**

Next.js App Router uses `template.tsx` (not layout.tsx) for re-mounting on route changes. Create `frontend/app/template.tsx`:

```tsx
"use client";

import { motion } from "framer-motion";
import { pageTransition, usePrefersReducedMotion, variantsWithReducedMotion } from "@/lib/motion";

export default function Template({ children }: { children: React.ReactNode }) {
  const reduced = usePrefersReducedMotion();
  const variants = variantsWithReducedMotion(pageTransition, reduced);
  return (
    <motion.div
      initial="initial"
      animate="enter"
      exit="exit"
      variants={variants}
    >
      {children}
    </motion.div>
  );
}
```

- [ ] **Step 5: Visual smoke test**

Run `cd frontend && npm run dev`. Click through:
1. Login → home (page transition)
2. Reminder card stagger entrance
3. Procedure flow → autofill pulse on populated fields
4. Switch completion mode → mode-switch transition
5. Open chrome devtools, simulate `prefers-reduced-motion`, confirm animations are instant

- [ ] **Step 6: Commit**

```bash
git add frontend/components/ChatPanel.tsx \
        frontend/components/FormPreview.tsx \
        frontend/components/CompletionModeSelector.tsx \
        frontend/app/template.tsx
git commit -m "feat(plan-4): framer-motion polish (messages, autofill, mode-switch, pages)"
```

---

## Task 19: axe-core E2E + Lighthouse CI

**Files:**
- Create: `frontend/e2e/a11y.spec.ts`
- Create: `lighthouserc.json`
- Create: `.github/workflows/a11y.yml`

- [ ] **Step 1: Write axe-core Playwright test**

Create `frontend/e2e/a11y.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";


const ROUTES = [
  { path: "/", name: "citizen home" },
  { path: "/login", name: "login" },
  { path: "/req/demo-doc", name: "procedure flow" },
  { path: "/doc/demo-doc", name: "document detail" },
];


for (const route of ROUTES) {
  test(`a11y: ${route.name}`, async ({ page }) => {
    // Pre-auth helper (use Plan 1's storageState if available)
    await page.goto(route.path);
    await page.waitForLoadState("networkidle");

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    expect(
      results.violations.filter((v) => v.impact === "serious" || v.impact === "critical"),
      JSON.stringify(results.violations, null, 2),
    ).toEqual([]);
  });
}
```

- [ ] **Step 2: Write Lighthouse CI config**

Create `lighthouserc.json` at repo root:

```json
{
  "ci": {
    "collect": {
      "url": [
        "https://civicai-staging.vercel.app/",
        "https://civicai-staging.vercel.app/login"
      ],
      "numberOfRuns": 1,
      "settings": {
        "preset": "desktop",
        "throttlingMethod": "provided"
      }
    },
    "assert": {
      "assertions": {
        "categories:accessibility": ["error", { "minScore": 1.0 }],
        "categories:performance": ["warn", { "minScore": 0.8 }]
      }
    },
    "upload": { "target": "temporary-public-storage" }
  }
}
```

- [ ] **Step 3: GitHub Actions workflow**

Create `.github/workflows/a11y.yml`:

```yaml
name: Accessibility

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  axe-core:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20", cache: "npm", cache-dependency-path: "frontend/package-lock.json" }
      - run: cd frontend && npm ci
      - run: cd frontend && npx playwright install --with-deps chromium
      - run: cd frontend && npm run build
      - name: Start server
        run: cd frontend && (npm run start &) && npx wait-on http://localhost:3000
      - name: Run axe E2E
        run: cd frontend && npx playwright test e2e/a11y.spec.ts

  lighthouse:
    runs-on: ubuntu-latest
    needs: axe-core
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: npm install -g @lhci/cli@0.13.x
      - name: Lighthouse CI
        run: lhci autorun
        env:
          LHCI_GITHUB_APP_TOKEN: ${{ secrets.LHCI_GITHUB_APP_TOKEN }}
```

- [ ] **Step 4: Run axe locally; fix any findings**

Run:
```bash
cd frontend
npm run build
npm run start &
sleep 4
npx playwright test e2e/a11y.spec.ts
```

For any serious/critical violations: fix inline (ARIA labels, color contrast, focus order). Re-run until 0 serious/critical.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/a11y.spec.ts lighthouserc.json .github/workflows/a11y.yml
git commit -m "feat(plan-4): axe-core + Lighthouse CI for a11y"
```

---

## Task 20: Keyboard navigation audit

**Files:**
- Create: `frontend/e2e/keyboard-nav.spec.ts`

- [ ] **Step 1: Write keyboard-tab test**

Create `frontend/e2e/keyboard-nav.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";


test("login page is fully tab-navigable", async ({ page }) => {
  await page.goto("/login");
  // First tab should land on the ROeID button
  await page.keyboard.press("Tab");
  const active1 = await page.evaluate(() => document.activeElement?.textContent);
  expect(active1).toMatch(/ROeID/);

  // Activate via Enter key
  await page.keyboard.press("Enter");
  await page.waitForURL(/otp|login/);
});


test("home page reminders are keyboard-actionable", async ({ page, request }) => {
  // assumes test storage state is logged in
  await page.goto("/");
  await page.waitForSelector('[data-testid="reminder-card"]');

  // Tab until we focus the first Start button
  let attempts = 0;
  while (attempts++ < 30) {
    await page.keyboard.press("Tab");
    const active = await page.evaluate(() => document.activeElement?.textContent ?? "");
    if (active.includes("Start") || active.includes("Vezi detalii")) break;
  }
  expect(attempts).toBeLessThan(30);
});


test("accessibility toggles are reachable via keyboard", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  // Toggles section should be reachable within 50 tabs from page start
  let foundToggle = false;
  for (let i = 0; i < 50; i++) {
    const role = await page.evaluate(() => document.activeElement?.getAttribute("role"));
    if (role === "switch") { foundToggle = true; break; }
    await page.keyboard.press("Tab");
  }
  expect(foundToggle).toBe(true);
});
```

- [ ] **Step 2: Run and fix any focus-order issues**

Run:
```bash
cd frontend
npx playwright test e2e/keyboard-nav.spec.ts
```

Common fixes:
- Add `tabIndex={0}` to custom interactive divs
- Use semantic `<button>` instead of `<div onClick>`
- Skip-to-content link at top of `<body>` for screen readers

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/keyboard-nav.spec.ts
git commit -m "feat(plan-4): keyboard navigation E2E"
```

---

## Task 21: Production deploy hardening — env vars + EU region verification

**Files:**
- Modify: `.env.example` (verify completeness)
- Create: `docs/superpowers/deploy-checklist.md`

- [ ] **Step 1: Audit .env.example**

Open `.env.example` (from roadmap §7). Ensure ALL of the following are listed:

```
# Supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_DB_URL=

# Auth / OTP
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_VERIFY_SERVICE_SID=
TWILIO_PHONE_NUMBER=

# LLM / Voice
GEMINI_API_KEY=
OPENAI_API_KEY=

# Deployment / runtime
NEXT_PUBLIC_API_BASE_URL=
NEXT_PUBLIC_DEMO_MODE=1
NEXT_PUBLIC_DEMO_TOKEN=
JWT_SIGNING_SECRET=
APP_ENV=production
DEMO_RESET_TOKEN=

# Observability
SENTRY_DSN=
NEXT_PUBLIC_SENTRY_DSN=
SENTRY_ORG=
SENTRY_PROJECT=
```

- [ ] **Step 2: Verify env vars present in Vercel + Railway**

Manual checklist — run through both consoles:

```bash
# Vercel:
vercel env ls --environment production
# Confirm every NEXT_PUBLIC_* + SENTRY_* var listed.

# Railway:
railway variables
# Confirm every backend var listed.
```

If any missing: add via console.

- [ ] **Step 3: Confirm EU regions**

```
- Supabase project → Project Settings → General → Region: must be "Frankfurt (eu-central-1)" or similar EU
- Vercel project → Settings → Functions → Function Region: "Frankfurt (fra1)"
- Railway service → Settings → Region: "europe-west4" or "eu-west1"
```

Record findings in `docs/superpowers/deploy-checklist.md`:

```markdown
# Production Deploy Checklist

## EU region verification (run before each demo day)

- [ ] Supabase: <region> (recorded: ...)
- [ ] Vercel: <region> (recorded: ...)
- [ ] Railway: <region> (recorded: ...)

## Env vars

- [ ] All vars in `.env.example` present in Vercel production
- [ ] All backend vars present in Railway production
- [ ] `DEMO_RESET_TOKEN` rotated to a fresh random value
- [ ] `NEXT_PUBLIC_DEMO_MODE=1` for hackathon demo URL; `0` for any imagined "production" URL

## Smoke checks

- [ ] `curl https://api.civicai.../healthz` returns `{"ok": true, ...}`
- [ ] Frontend loads with no console errors at https://civicai.../
- [ ] Sentry receives a test error (run a force-throw + confirm event)
```

- [ ] **Step 4: Commit**

```bash
git add .env.example docs/superpowers/deploy-checklist.md
git commit -m "chore(plan-4): env var audit + EU region checklist"
```

---

## Task 22: Demo dry-run E2E smoke test

**Files:**
- Create: `frontend/e2e/demo-flow.spec.ts`

This is the FULL demo flow, automated via Playwright. Tagged `@demo` so it can be skipped if Plan 3 not yet merged (voice flow is mocked through `/agent/chat` test stub).

- [ ] **Step 1: Write the demo dry-run test**

Create `frontend/e2e/demo-flow.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";


test.describe("@demo Full demo flow", () => {
  test("schimbare-domiciliu end-to-end", async ({ page, request }) => {
    // 0. Reset demo state
    const tok = process.env.NEXT_PUBLIC_DEMO_TOKEN ?? "test-demo-token-abc";
    await request.post(`${process.env.API_BASE}/demo/reset`, {
      headers: { "X-Demo-Token": tok },
      data: {},
    });

    // 1. Login as Maria
    await page.goto("/login");
    await page.click("text=Login cu ROeID");
    // The demo persona chooser is open in dev mode
    await page.click("text=Maria Ionescu");
    await page.fill("[aria-label='Cod OTP']", "123456"); // demo OTP
    await page.click("text=Continuă");

    // 2. Home shows pre-seeded reminders
    await page.waitForSelector("[data-testid='reminder-card']");
    const initialReminders = await page.locator("[data-testid='reminder-card']").count();
    expect(initialReminders).toBeGreaterThanOrEqual(1);

    // 3. Start a new schimbare-domiciliu request
    await page.click("text=Start o cerere nouă");
    await page.fill("[aria-label='Descrie ce ai nevoie']", "Vreau să-mi schimb domiciliul");
    await page.click("text=Trimite");

    // 4. Wait for procedure recognition (canned response from Plan 2; real agent in Plan 3)
    await page.waitForURL(/\/req\//);

    // 5. Fill remaining fields via manual mode
    await page.click("text=Manual");
    await page.fill("[name='adresa_noua']", "Str. Plopilor 15, Cluj-Napoca");
    await page.selectOption("[name='tip_proprietate']", "chiriaș");
    await page.click("text=Salvează completarea");

    // 6. Generate PDF and deliver
    await page.click("text=Trimite la primărie");
    await expect(page.locator("text=trimisă")).toBeVisible({ timeout: 10000 });

    // 7. Wait for proactive reminder to appear (worker has 5s tick)
    await page.goto("/");
    await page.waitForTimeout(7000);
    const reminders = page.locator("[data-testid='reminder-card']");
    await expect(reminders).toHaveCount(initialReminders, { timeout: 8000 });
    // Among them, at least one is from the new delivery (Preschimbare CI or DRPCIV)
    const titles = await reminders.locator("h3").allTextContents();
    expect(
      titles.some((t) => /preschimbare|DRPCIV|CNAS|ANAF/i.test(t)),
    ).toBe(true);

    // 8. Click "Start acum" on the in-scope reminder
    const startButton = page.getByRole("button", { name: /start acum/i }).first();
    await startButton.click();
    await page.waitForURL(/\/req\//);
  });
});
```

- [ ] **Step 2: Add npm script**

In `frontend/package.json`:

```json
"scripts": {
  "test:demo": "playwright test e2e/demo-flow.spec.ts --grep @demo"
}
```

- [ ] **Step 3: Run locally end-to-end**

```bash
cd frontend && npm run test:demo
```

Expected: PASS (allow 60s for the full flow).

Note: this test requires the backend running with seeded data and the worker scheduler active. If voice is required for any step, those steps should already use the canned `/agent/chat` response from Plan 2's mock; once Plan 3 lands, the same test still passes (real agent returns equivalent confirmation text).

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/demo-flow.spec.ts frontend/package.json
git commit -m "feat(plan-4): demo dry-run E2E (@demo tag)"
```

---

## Task 23: Juror poke-list (demo readiness doc)

**Files:**
- Create: `docs/superpowers/demo-pokelist.md`

This is the prepared answer-list for the juror Q&A from spec §21.

- [ ] **Step 1: Write the poke-list**

Create `docs/superpowers/demo-pokelist.md`:

```markdown
# CivicAI — Juror Poke-List (Hackathon Demo)

Anticipated questions and the rehearsed answers. Practice these out loud before the demo.

## "Și pentru ANAF?" (out-of-scope handoff)

**What to do:** In the live demo, type or speak "Vreau să-mi schimb domiciliul fiscal" (or similar ANAF-flavored query).

**What the agent does:** Returns no in-scope match; surfaces the `redirect_candidate: "ANAF"` UI card with: contact info + roadmap note.

**Verbal answer:**
> "ANAF nu e în scope-ul nostru — am ales în mod deliberat să livrăm primăria perfect, nu o aplicație care face totul superficial. Aici am redirecționat cetățeanul către ghiseul.ro cu instrucțiuni clare. Pe roadmap avem integrarea directă cu ANAF, dar acea integrare presupune contracte cu altă instituție — nu o putem livra într-un weekend."

## "Cum știți că documentul nu poate fi falsificat?"

**What to do:** Open the just-delivered document at `/doc/[id]`; show the "Istoric integritate" timeline.

**Verbal answer:**
> "Fiecare eveniment important — creare, completare, generare PDF, livrare — e o intrare în ledger-ul nostru. Fiecare rând e legat hash-criptografic de cel precedent: dacă cineva încearcă să modifice o intrare retroactiv, lanțul se rupe. Verificatorul nostru rulează în background; dacă găsește o discrepanță, marchează documentul cu ⚠️ în loc de ✓. E o blockchain simulată — același principiu cu Bitcoin, dar într-o singură bază de date Postgres, cu funcția `append_ledger` care refuză inserții cu prev_hash invalid."

## "Poate să fie folosit de bunica mea?"

**What to do:** Toggle voice-only ON + simple-language ON. Re-start a flow with mic only.

**Verbal answer:**
> "Da. Două lucruri am construit pentru asta: mod vocal — agentul ascultă, vorbește, narrează tot ce face, nu trebuie atins ecranul; și «explică-mi mai simplu» — schimbă tonul agentului la nivelul unui copil de clasa a 6-a, fără jargon administrativ. Plus toate elementele standard: contrast AA, navigare cu tastatura, suport screen reader, mărime text 125%."

## "Câte primării ar putea folosi asta mâine?"

**Verbal answer:**
> "Forma noastră deep-demo (schimbare domiciliu) folosește formularul real al Primăriei Cluj-Napoca de pe primariaclujnapoca.ro. Adăugarea unei noi primării înseamnă: înlocuirea LaTeX-ului cu formularul lor, eventual ajustarea unor JSON-uri de proceduri. Modelul de embedding-uri RAG găsește automat procedura potrivită, fără cod nou. La 320 de UAT-uri urbane în România, o singură persoană tehnică poate adăuga 5-10 pe săptămână."

## "De ce nu ați folosit Claude / ElevenLabs?"

**Verbal answer:**
> "Gemini Live oferă realtime speech-to-speech sub 400ms în română, cu barge-in nativ. Alternativele sancționate încă merg pe pipeline cu latență 800ms+, ceea ce face conversația naturală imposibilă. Pentru text reasoning folosim însă tot ecosistemul standard — Pydantic AI, OpenAI embeddings. Avem și fallback pe OpenAI Realtime dacă Gemini are probleme."

## Backup demos

- Phone demo not working: pivot to the browser voice demo + describe the phone path verbally.
- WiFi flaky: switch to mobile hotspot (pre-tested).
- Demo state corrupted: click the yellow "Reset demo" button bottom-right.

## Practice script (timing target: 5 min)

1. (00:00) Open citizen home. Point at pre-seeded reminders. "Aplicația te aduce direct la pașii următori."
2. (00:30) Switch to tablet (kiosk). Scan buletinul (or use ROeID button). Wait for SMS OTP. Enter it.
3. (01:30) Say in Romanian "Vreau să-mi schimb domiciliul." Agent confirms.
4. (02:00) Choose "Vocal." Agent walks through adresa_noua, tip_proprietate. Preview fills live.
5. (03:30) Click "Trimite la primărie." Confirmation appears with ref number.
6. (04:00) Switch back to mobile. New proactive reminder visible. Click it. New procedure starts.
7. (04:30) Open `/doc/[id]`. Show audit timeline with green ✓.
8. (05:00) Pick up the phone. Dial Twilio number. Ask "De ce acte îmi trebuie pentru adeverința de venit?" Listen.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/demo-pokelist.md
git commit -m "docs(plan-4): juror poke-list with rehearsed answers"
```

---

## Task 24: Final verification + open PR

**Files:** none

- [ ] **Step 1: Full backend test suite**

```bash
cd backend && pytest -v
```
Expected: all tests pass (applies_if, reminders, demo, attributes, healthz, plus everything from Plan 2).

- [ ] **Step 2: Full frontend test suite**

```bash
cd frontend
npx vitest run
npx playwright test
```
Expected: vitest 100% pass; playwright passes (a11y, keyboard-nav, demo-flow).

- [ ] **Step 3: Manual checkpoint-2 verification**

Run through every item in roadmap §5 Checkpoint 2 (Plan 4 column):
- [ ] Background worker fires after delivery; reminders appear.
- [ ] Reminder cards have stagger animation on home.
- [ ] "Start now" creates a doc and routes to `/req/[id]`.
- [ ] External redirect cards show contact info + roadmap note.
- [ ] Voice-only mode toggle wires to `useVoiceAgent` (manual check; requires Plan 3 merged).
- [ ] Simple-language toggle sets PATCH + passes preference to `/agent/chat` and `/voice/session`.
- [ ] Large-text mode applies Tailwind class.
- [ ] axe-core CI passes; Lighthouse a11y = 1.0.
- [ ] `POST /demo/reset` works; dev panel button visible.
- [ ] Framer-motion transitions on page changes, field highlights, mode switches.
- [ ] Production env vars verified; Sentry installed; EU regions confirmed; error boundary + healthz live.

- [ ] **Step 4: Push branch + open PR**

```bash
git push -u origin wave2/plan-4-proactive-polish
gh pr create --title "Plan 4: proactive layer + polish + accessibility" --body "$(cat <<'EOF'
## Summary
- Background worker (APScheduler) reads `delivered` ledger events and writes proactive reminders.
- `applies_if` expression evaluator (TDD).
- New endpoints: `/reminders/*`, `/demo/reset`, `PATCH /citizens/me/attributes`, `/healthz`.
- Reminder card UI with kind-specific layouts and stagger animation.
- Accessibility toggles wired to real behaviors (voice-only, simple-language, large-text).
- Framer-motion polish across the app (page transitions, autofill pulse, message fade, mode switch).
- Production hardening: Sentry, error boundary, EU region checklist.
- E2E: axe-core, keyboard nav, full demo dry-run.

## Test plan
- [ ] `pytest backend/tests -v` passes
- [ ] `npx vitest run` in frontend passes
- [ ] `npx playwright test` passes including @demo tag
- [ ] Lighthouse a11y = 1.0 on /, /login, /req/[id], /doc/[id]
- [ ] Manual: Reset demo button works; reminders appear after delivery; voice-only mode works once Plan 3 merged

Closes the Plan 4 scope in `docs/superpowers/plans/2026-05-23-civicai-execution-roadmap.md` §6.
EOF
)"
```

- [ ] **Step 5: After PR review and merge: Checkpoint 2 dry-run**

Once both Plan 3 and Plan 4 are merged into `main`:
1. Re-run the full demo from `docs/superpowers/demo-pokelist.md` step-by-step.
2. Three team members each take a juror seat and ask a poke-list question.
3. Time the demo: must hit ≤ 5 min for the core walkthrough.
4. Reset demo button verified between rotations.
