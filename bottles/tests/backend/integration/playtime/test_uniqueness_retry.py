"""Uniqueness retry for same-second launches."""

import sqlite3
import time
from freezegun import freeze_time


def test_uniqueness_retry_smoke(manager):
    """Two sessions of same bottle/program starting in the same second should succeed.

    First session finalizes, second begins at the same timestamp. Unique(bottle_id, program_id, started_at)
    would collide, but start_session should bump started_at to avoid IntegrityError.
    """
    tracker = manager.playtime_tracker
    assert tracker is not None

    with freeze_time("2025-01-02 00:00:00"):
        base = int(time.time())
        # Start and finalize first session
        sid1 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        tracker.mark_exit(sid1, status="success", ended_at=base + 1)

        # Start second session at the exact same second (same started_at candidate)
        sid2 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )

    con = sqlite3.connect(tracker.db_path)
    cur = con.cursor()
    cur.execute(
        "SELECT id, started_at FROM sessions WHERE bottle_id=? ORDER BY started_at",
        ("b1",),
    )
    rows = cur.fetchall()
    assert len(rows) == 2
    first_started = int(rows[0][1])
    second_started = int(rows[1][1])
    # Ensure the retry bumped the second started_at by at least 1 second
    assert second_started >= first_started + 1

