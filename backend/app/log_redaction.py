"""Mask personal identifiers in log output.

The app logs a lot of user content at INFO — chat messages, speech
transcripts, widget answers, tool arguments (`set_field(name='cnp',
value=...)`) — and those lines end up in `docker logs`, Railway and any log
drain. One filter on the handler redacts the identifiers that should never
be there, instead of auditing every call site.

Masked: CNP (13 digits starting 1-9), e-mail addresses, Romanian mobile
numbers. Names and street addresses are not reliably detectable and are not
masked — keep them out of new log lines.

Set LOG_REDACT_PII=0 to see raw values while debugging locally.
"""
from __future__ import annotations

import logging
import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<!\d)[1-9]\d{12}(?!\d)"), "[CNP]"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    (re.compile(r"(?<![\d+])(?:\+?40|0)7\d{8}(?!\d)"), "[tel]"),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


_EXC_FORMATTER = logging.Formatter()


class PiiRedactingFilter(logging.Filter):
    """Redacts the message and any traceback the record carries.

    `log.exception(...)` lines end in the exception's text, which is where
    database errors put row contents ("Failing row contains (..., CNP, ...)")
    — the formatter renders it from `exc_info` after filters have run, so it
    is rendered and redacted here and cached in `exc_text`, which formatters
    use as-is.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 — a bad format string is not our problem here
            return True
        redacted = redact(message)
        if redacted != message:
            record.msg, record.args = redacted, ()
        if record.exc_info and not record.exc_text:
            record.exc_text = _EXC_FORMATTER.formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        if record.stack_info:
            record.stack_info = redact(record.stack_info)
        return True
