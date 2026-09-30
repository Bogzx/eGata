from __future__ import annotations

import logging

from app.log_redaction import PiiRedactingFilter, redact


def test_redacts_cnp_email_and_phone() -> None:
    line = "set_field(name='cnp', value='2851014123456') maria@example.com +40712345678 0712345678"
    out = redact(line)
    assert "2851014123456" not in out and "[CNP]" in out
    assert "maria@example.com" not in out and "[email]" in out
    assert "712345678" not in out


def test_leaves_ordinary_numbers_alone() -> None:
    assert redact("req=ab12cd took 1234ms, 12 fields, doc CV-3B66") == (
        "req=ab12cd took 1234ms, 12 fields, doc CV-3B66"
    )
    # A 14-digit number is not a CNP.
    assert redact("id 12345678901234") == "id 12345678901234"


def test_filter_rewrites_formatted_record() -> None:
    record = logging.LogRecord(
        "agent", logging.INFO, __file__, 1, "chat: msg=%r", ("CNP-ul meu e 1900512123456",), None
    )
    assert PiiRedactingFilter().filter(record) is True
    assert record.getMessage() == "chat: msg='CNP-ul meu e [CNP]'"


def test_app_handler_has_the_filter() -> None:
    import app.main  # noqa: F401 — configures logging

    handlers = logging.getLogger("agent").handlers
    assert any(isinstance(f, PiiRedactingFilter) for h in handlers for f in h.filters)


def test_traceback_text_is_redacted() -> None:
    """Database errors echo row contents; log.exception used to print them raw."""
    try:
        raise ValueError("Failing row contains (2851014123456, maria@example.com, +40712345678)")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "agent", logging.ERROR, __file__, 1, "set_field failed", (), sys.exc_info()
        )
    assert PiiRedactingFilter().filter(record) is True
    out = logging.Formatter().format(record)
    assert "2851014123456" not in out and "maria@example.com" not in out
    assert "712345678" not in out
    assert "Failing row contains ([CNP], [email], [tel])" in out


def test_every_app_logger_reaches_the_filtered_handler() -> None:
    import io

    import app.main  # noqa: F401 — configures logging

    names = {"offline_agent", "files", "storage", "some.new.module"}
    for name in names:
        handlers = logging.getLogger(name).handlers or logging.getLogger().handlers
        assert any(
            isinstance(f, PiiRedactingFilter) for h in handlers for f in h.filters
        ), name
    stream = io.StringIO()
    handler = next(h for h in logging.getLogger().handlers if h.filters)
    old = handler.setStream(stream)  # type: ignore[attr-defined]
    try:
        logging.getLogger("offline_agent").warning("value 2851014123456 rejected")
    finally:
        handler.setStream(old)  # type: ignore[attr-defined]
    assert "[CNP]" in stream.getvalue() and "2851014123456" not in stream.getvalue()
