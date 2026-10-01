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
from typing import Any

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<!\d)[1-9]\d{12}(?!\d)"), "[CNP]"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    (re.compile(r"(?<![\d+])(?:\+?40|0)7\d{8}(?!\d)"), "[tel]"),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_structure(value: Any) -> Any:
    """`redact` applied to every string inside nested dicts, lists and tuples."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: redact_structure(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_structure(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_structure(v) for v in value)
    return value


def scrub_sentry_event(event: Any, _hint: Any) -> Any:
    """Sentry `before_send` / `before_send_transaction` hook.

    `send_default_pii=False` keeps Sentry from attaching request bodies and
    user info, but the event still carries exception messages, breadcrumbs
    (copies of log lines, taken before our handler filter runs) and frame
    variables — where a CNP or phone number ends up when a database error
    quotes the failing row. Every string in the event is masked before it
    leaves the process. Applied regardless of LOG_REDACT_PII: this data goes
    to a third party, not to a local terminal.
    """
    return redact_structure(event)


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
