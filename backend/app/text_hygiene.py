"""Tiny shared helpers for stripping internal-thought artifacts from LLM output.

Some Gemini models emit <thinking> / <scratchpad> / <reasoning> blocks even
when asked not to. The frontend should never display those; this is the
server-side defense (frontend has its own as belt-and-braces).
"""
from __future__ import annotations

import re

_THINKING_RE = re.compile(
    r"<(?:thinking|scratchpad|reasoning)>.*?</(?:thinking|scratchpad|reasoning)>",
    re.DOTALL | re.IGNORECASE,
)


def strip_thinking(text: str | None) -> str | None:
    """Remove <thinking>/<scratchpad>/<reasoning> blocks; trim whitespace.

    Returns the input unchanged when it's None or empty.
    """
    if text is None:
        return None
    if not text:
        return text
    return _THINKING_RE.sub("", text).strip()
