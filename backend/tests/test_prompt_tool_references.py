"""The system prompts must only name tools that are actually registered.

prompts.py:99 instructed the model to call `set_reminder`, which was never
registered — any call would have been a hard dispatch error. The same block
claimed "26 de proceduri" when there are 23.
"""
from __future__ import annotations

import re

import pytest

import app.agent_tools  # noqa: F401 — registers every tool as a side effect
from app.agent_tools import REGISTRY as TOOLS_REGISTRY
from app.procedures import get_registry
from app.prompts import CONVERSATIONAL_SYSTEM, PHONE_SYSTEM

PROMPTS = {
    "CONVERSATIONAL_SYSTEM": CONVERSATIONAL_SYSTEM,
    "PHONE_SYSTEM": PHONE_SYSTEM,
}

# Backtick-quoted snake_case identifiers are how the prompts refer to tools.
BACKTICKED = re.compile(r"`([a-z][a-z0-9_]*)`")

# Backticked identifiers that are field names or JSON keys, not tools.
NOT_TOOLS = {
    "acte_necesare",
    "scenario_plan",
    "target_field",
    "procedure_id",
    "confirming_match",
    "delivered",
    "exploring",
    "filling",
    "reviewing",
    "redirected",
    "category",
    "query",
    "email",
    "telefon",
    "nume_complet",
    "ap_domiciliu",
    "strada_domiciliu",
    "nr_domiciliu",
    "cnp",
    "apartament",
    "numar",
    "strada",
    "bloc",
    "scara",
    "etaj",
    "judet",
    "localitate",
}


@pytest.mark.parametrize("name", sorted(PROMPTS))
def test_prompt_only_references_registered_tools(name: str) -> None:
    referenced = set(BACKTICKED.findall(PROMPTS[name])) - NOT_TOOLS
    unknown = {r for r in referenced if r not in TOOLS_REGISTRY}
    assert not unknown, (
        f"{name} tells the model to use {sorted(unknown)}, which "
        f"{'is' if len(unknown) == 1 else 'are'} not registered — a call would "
        f"be a hard error. Registered: {sorted(TOOLS_REGISTRY)}"
    )


@pytest.mark.parametrize("name", sorted(PROMPTS))
def test_prompt_states_no_wrong_procedure_count(name: str) -> None:
    """A hardcoded count goes stale the moment a procedure is added or
    removed. If one is stated, it has to be right."""
    actual = len(get_registry())
    for match in re.finditer(r"(\d+)\s+(?:de\s+)?proceduri", PROMPTS[name]):
        assert int(match.group(1)) == actual, (
            f"{name} says {match.group(1)} procedures; the registry holds {actual}"
        )
