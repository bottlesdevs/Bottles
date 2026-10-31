"""Tests for ProcessSessionTracker.delete_program_stats()."""

import os

import pytest

from bottles.backend.managers.playtime import (
    ProcessSessionTracker,
    ResetResult,
    _compute_program_id,
)

BOTTLE_PATH = "/tmp/bottles/bottle"


@pytest.fixture
def tracker(tmp_path):
    t = ProcessSessionTracker(db_path=str(tmp_path / "playtime.sqlite"))
    yield t
    t.shutdown()


def _play(tracker, bottle_id, program_path, seconds=60):
    """Run one finished session and return the program id."""
    session_id = tracker.start_session(
        bottle_id=bottle_id,
        bottle_name=bottle_id,
        bottle_path=BOTTLE_PATH,
        program_name=os.path.basename(program_path),
        program_path=program_path,
    )
    row = tracker._conn.execute(
        "SELECT started_at FROM sessions WHERE id=?", (session_id,)
    ).fetchone()
    tracker.mark_exit(session_id, ended_at=int(row[0]) + seconds)
    return _compute_program_id(bottle_id, BOTTLE_PATH, program_path)


def _counts(tracker, bottle_id, program_id):
    sessions = tracker._conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE bottle_id=? AND program_id=?",
        (bottle_id, program_id),
    ).fetchone()[0]
    totals = tracker._conn.execute(
        "SELECT COUNT(*) FROM playtime_totals WHERE bottle_id=? AND program_id=?",
        (bottle_id, program_id),
    ).fetchone()[0]
    return sessions, totals


def test_reset_removes_sessions_and_totals(tracker):
    program_id = _play(tracker, "b1", f"{BOTTLE_PATH}/drive_c/a.exe")
    assert _counts(tracker, "b1", program_id) == (1, 1)

    assert tracker.delete_program_stats("b1", program_id) is ResetResult.OK
    assert _counts(tracker, "b1", program_id) == (0, 0)


def test_reset_keeps_other_program_in_same_bottle(tracker):
    a = _play(tracker, "b1", f"{BOTTLE_PATH}/drive_c/a.exe")
    b = _play(tracker, "b1", f"{BOTTLE_PATH}/drive_c/b.exe")

    assert tracker.delete_program_stats("b1", a) is ResetResult.OK

    assert _counts(tracker, "b1", a) == (0, 0)
    assert _counts(tracker, "b1", b) == (1, 1)


def test_reset_keeps_same_program_in_other_bottle(tracker):
    path = f"{BOTTLE_PATH}/drive_c/a.exe"
    first = _play(tracker, "b1", path)
    second = _play(tracker, "b2", path)
    assert first != second

    assert tracker.delete_program_stats("b1", first) is ResetResult.OK

    assert _counts(tracker, "b1", first) == (0, 0)
    assert _counts(tracker, "b2", second) == (1, 1)


def test_reset_is_refused_while_program_is_running(tracker):
    path = f"{BOTTLE_PATH}/drive_c/a.exe"
    program_id = _play(tracker, "b1", path)
    session_id = tracker.start_session(
        bottle_id="b1",
        bottle_name="b1",
        bottle_path=BOTTLE_PATH,
        program_name="a.exe",
        program_path=path,
    )

    assert tracker.delete_program_stats("b1", program_id) is ResetResult.RUNNING

    # Nothing was deleted and the running session is still tracked
    assert _counts(tracker, "b1", program_id) == (2, 1)
    assert session_id in tracker._tracked

    # The session can still finish normally, and the program can be reset after
    tracker.mark_exit(session_id)
    assert session_id not in tracker._tracked
    assert tracker.delete_program_stats("b1", program_id) is ResetResult.OK
    assert _counts(tracker, "b1", program_id) == (0, 0)


def test_running_program_does_not_block_reset_of_another(tracker):
    a = _play(tracker, "b1", f"{BOTTLE_PATH}/drive_c/a.exe")
    tracker.start_session(
        bottle_id="b1",
        bottle_name="b1",
        bottle_path=BOTTLE_PATH,
        program_name="b.exe",
        program_path=f"{BOTTLE_PATH}/drive_c/b.exe",
    )

    assert tracker.delete_program_stats("b1", a) is ResetResult.OK


def test_reset_is_atomic(tracker):
    program_id = _play(tracker, "b1", f"{BOTTLE_PATH}/drive_c/a.exe")
    # Make the second DELETE fail after the first one succeeded
    tracker._conn.execute("DROP TABLE playtime_totals")
    tracker._conn.commit()

    assert tracker.delete_program_stats("b1", program_id) is ResetResult.ERROR

    remaining = tracker._conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE bottle_id=? AND program_id=?",
        ("b1", program_id),
    ).fetchone()[0]
    assert remaining == 1


def test_reset_when_tracking_disabled(tmp_path):
    t = ProcessSessionTracker(db_path=str(tmp_path / "playtime.sqlite"), enabled=False)
    try:
        assert t.delete_program_stats("b1", "x") is ResetResult.DISABLED
    finally:
        t.shutdown()
