from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

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


def _send_through_sentry(before_send: Callable[[Any, Any], Any] | None) -> str:
    """Capture one exception (and a breadcrumb) with a real sentry_sdk client
    whose transport keeps the envelope; return everything it would send."""
    import sentry_sdk
    from sentry_sdk.envelope import Envelope
    from sentry_sdk.transport import Transport

    class Keep(Transport):
        def __init__(self, options: dict[str, Any] | None = None) -> None:
            super().__init__(options)
            self.envelopes: list[Envelope] = []

        def capture_envelope(self, envelope: Envelope) -> None:
            self.envelopes.append(envelope)

    client = sentry_sdk.Client(
        dsn="https://public@o0.ingest.sentry.io/1",
        transport=Keep,
        before_send=before_send,
        send_default_pii=False,
    )
    with sentry_sdk.new_scope() as scope:
        scope.set_client(client)
        logging.getLogger("auth").warning("login for maria@example.com")
        try:
            cnp = "2851014123456"
            raise ValueError(f"Failing row contains ({cnp}, 0712345678)")
        except ValueError:
            sentry_sdk.capture_exception()
    client.flush()
    transport = client.transport
    assert isinstance(transport, Keep)
    return "".join(
        item.payload.get_bytes().decode() for env in transport.envelopes for item in env.items
    )


def test_sentry_events_leave_with_identifiers_masked() -> None:
    from app.log_redaction import scrub_sentry_event

    raw = _send_through_sentry(None)
    # The exception text, the frame's locals and the log breadcrumb all carry
    # them without the hook — this is what it is for.
    assert "2851014123456" in raw and "maria@example.com" in raw and "0712345678" in raw

    sent = _send_through_sentry(scrub_sentry_event)
    assert "2851014123456" not in sent and "[CNP]" in sent
    assert "maria@example.com" not in sent
    assert "0712345678" not in sent


def test_main_registers_the_sentry_scrubber() -> None:
    import inspect

    import app.main

    source = inspect.getsource(app.main)
    assert "before_send=scrub_sentry_event" in source
    assert "before_send_transaction=scrub_sentry_event" in source


def test_sentry_identifiers_survive_the_scrub() -> None:
    """32-hex ids sometimes hold 13 consecutive digits; they must not be read
    as CNPs (nor a release tag as an e-mail) — that would break the link
    between an event and its trace. Personal data next to them is masked."""
    from app.log_redaction import scrub_sentry_event

    trace = "0cb6792c3052405081607d5ed023ff11"  # contains 3052405081607
    span = "a1b2c3d4e5f6a7b8"
    event = {
        "event_id": trace,
        "release": "egata@1.4.2",
        "contexts": {"trace": {"trace_id": trace, "span_id": span, "parent_span_id": span}},
        "spans": [{"span_id": span, "trace_id": trace, "description": "row 2851014123456"}],
        "exception": {"values": [{"value": "Failing row contains (2851014123456)",
                                  "stacktrace": {"frames": [{"vars": {"cnp": "'2851014123456'"}}]}}]},
        "user": {"id": trace, "email": "maria@example.com"},
    }
    out = scrub_sentry_event(event, {})

    assert out["event_id"] == trace and out["release"] == "egata@1.4.2"
    assert out["contexts"]["trace"] == {"trace_id": trace, "span_id": span, "parent_span_id": span}
    assert out["spans"][0]["trace_id"] == trace and out["spans"][0]["span_id"] == span
    assert out["user"]["id"] == trace
    # ...while the personal data beside them is still masked.
    assert out["spans"][0]["description"] == "row [CNP]"
    assert "2851014123456" not in str(out["exception"])
    assert out["user"]["email"] == "[email]"
