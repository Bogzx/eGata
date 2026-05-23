"""Strip internal-thought artifacts from LLM output.

Reasoning models occasionally leak their scratchpad into the user-facing
stream, e.g.:

    **Initiating Communication Strategy**

    I've got a tricky starting point here, an ellipsis alone! ...

    Bună ziua! Cu ce te pot ajuta?

We strip a leading ``**English Title**`` heading followed by one or more
paragraphs, repeated up to three times, then trim. Romanian bold headings
(which always contain diacritics like ăâîșț) are left alone.

We also strip ``<thinking>``/``<scratchpad>``/``<reasoning>`` XML blocks
anywhere in the text — some models still emit these despite instructions.

The frontend has the same logic as belt-and-braces; this is the server-side
defence so the same cleaned text is what we persist into history.
"""
from __future__ import annotations

import re

_XML_THINKING_RE = re.compile(
    r"<(?:thinking|scratchpad|reasoning)>.*?</(?:thinking|scratchpad|reasoning)>",
    re.DOTALL | re.IGNORECASE,
)

_LEADING_THINKING_RE = re.compile(
    r"^\s*\*\*([^*\n]+)\*\*[^\n]*\n(?:\s*\n)*(?:[^\n]+\n)+(?:\s*\n)*"
)

_RO_DIACRITICS = set("ăâîșțĂÂÎȘȚ")


def strip_thinking(text: str | None) -> str | None:
    if text is None:
        return None
    if not text:
        return text
    out = _XML_THINKING_RE.sub("", text)
    for _ in range(3):
        m = _LEADING_THINKING_RE.match(out)
        if not m:
            break
        heading = m.group(1)
        if any(c in _RO_DIACRITICS for c in heading):
            break
        out = out[m.end():]
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()
