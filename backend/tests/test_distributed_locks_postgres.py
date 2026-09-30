"""Replica-safe coordination against a real Postgres (opt-in, TEST_DATABASE_URL).

Another backend replica is simulated by a second connection holding the
same advisory lock.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any
from uuid import UUID, uuid4

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set; skipping real-Postgres lock tests"
)

psycopg = pytest.importorskip("psycopg")


@pytest.fixture(autouse=True)
def _distributed(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    from app.config import get_settings

    monkeypatch.setenv("SUPABASE_DB_URL", os.environ.get("APP_DATABASE_URL") or TEST_DATABASE_URL or "")
    monkeypatch.setenv("DISTRIBUTED_LOCKS", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _other_replica_holds(key: str) -> Any:
    conn = psycopg.connect(TEST_DATABASE_URL, autocommit=True)
    assert conn.execute("select pg_try_advisory_lock(hashtextextended(%s, 0));", (key,)).fetchone()[0]
    return conn


def test_session_lock_waits_for_another_replica() -> None:
    from app.sessions import SessionBusyError, session_lock

    sid = f"sess_{uuid4().hex[:8]}"
    other = _other_replica_holds(f"egata:session:{sid}")

    async def attempt() -> None:
        async with session_lock(sid, wait_seconds=0.3):
            pass

    with pytest.raises(SessionBusyError):
        asyncio.run(attempt())

    async def attempt_after_release() -> bool:
        async def release_soon() -> None:
            await asyncio.sleep(0.2)
            other.close()  # closing the other session releases its lock

        release = asyncio.create_task(release_soon())
        async with session_lock(sid, wait_seconds=5):
            await release
            return True

    assert asyncio.run(attempt_after_release())


def test_session_lock_is_released_after_the_turn() -> None:
    from app.sessions import session_lock

    sid = f"sess_{uuid4().hex[:8]}"

    async def turn() -> None:
        async with session_lock(sid):
            pass

    asyncio.run(turn())
    probe = psycopg.connect(TEST_DATABASE_URL, autocommit=True)
    try:
        got = probe.execute(
            "select pg_try_advisory_lock(hashtextextended(%s, 0));", (f"egata:session:{sid}",)
        ).fetchone()[0]
        assert got
    finally:
        probe.close()


def _delivered_event() -> int:
    from app.ledger import LedgerEventType, append_ledger

    cid, did = uuid4(), uuid4()
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute(
            "insert into citizens (id, cnp, nume, prenume, data_nasterii, phone) "
            "values (%s, %s, 'W', 'Worker', '1990-01-01', '+40700000000');",
            (str(cid), f"7{cid.int % 10**12:012d}"),
        )
        conn.execute(
            "insert into documents (id, citizen_id, procedure_id) values (%s, %s, 'schimbare-domiciliu');",
            (str(did), str(cid)),
        )
    row = append_ledger(
        citizen_id=cid, event_type=LedgerEventType.DELIVERED,
        payload={"document_id": str(did)}, document_id=did,
    )
    return int(row["id"])


def _processed(ledger_id: int) -> bool:
    with psycopg.connect(TEST_DATABASE_URL) as conn:
        return conn.execute(
            "select 1 from processed_events where ledger_id = %s;", (ledger_id,)
        ).fetchone() is not None


def test_reminders_worker_skips_a_tick_another_replica_is_running() -> None:
    from app.worker import WORKER_LOCK_KEY, _process_pending_events

    ledger_id = _delivered_event()
    other = _other_replica_holds(WORKER_LOCK_KEY)
    try:
        _process_pending_events()
        assert not _processed(ledger_id)
    finally:
        other.close()
    _process_pending_events()
    assert _processed(ledger_id)


def test_review_confirmation_survives_a_reload() -> None:
    from app.sessions import (
        PendingWidget,
        SessionState,
        apply_review_confirmation,
        fetch_session,
        insert_session,
        update_session,
    )

    cid = uuid4()
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute(
            "insert into citizens (id, cnp, nume, prenume, data_nasterii, phone) "
            "values (%s, %s, 'R', 'Review', '1990-01-01', '+40700000000');",
            (str(cid), f"6{cid.int % 10**12:012d}"),
        )
    sess = insert_session(UUID(str(cid)))
    sess.state = SessionState.REVIEWING
    assert apply_review_confirmation(sess, PendingWidget("w", "confirm", "Sunt corecte?"), "Da")
    update_session(sess)
    reloaded = fetch_session(sess.id)  # e.g. on another replica
    assert reloaded is not None and reloaded.review_confirmed
