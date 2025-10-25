"""Successful run should finalize session and update totals."""

import sqlite3
import time
from freezegun import freeze_time


def test_successful_run_finalizes_and_updates_totals(manager):
    tracker = manager.playtime_tracker
    assert tracker is not None

    with freeze_time("2025-01-01 00:00:00"):
        base = int(time.time())
        sid = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        tracker.mark_exit(sid, status="success", ended_at=base + 60)

    con = sqlite3.connect(tracker.db_path)
    cur = con.cursor()
    cur.execute("SELECT status, duration_seconds FROM sessions WHERE id=?", (sid,))
    status, duration = cur.fetchone()
    assert status == "success"
    assert duration >= 60

    cur.execute(
        "SELECT total_seconds, sessions_count FROM playtime_totals WHERE bottle_id=?",
        ("b1",),
    )
    total_seconds, sessions_count = cur.fetchone()
    assert sessions_count == 1
    assert total_seconds >= 60


def test_success_multiple_apps_two_same_bottle_one_other(manager):
    """Simulate overlapping runs: start a second and third app before prior ones ended."""
    tracker = manager.playtime_tracker
    assert tracker is not None

    with freeze_time("2025-01-01 10:00:00") as ft:
        t0 = int(time.time())
        # Start b1/Game1 at t0 (will run 30s)
        sid1 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle1",
            bottle_path="/b1",
            program_name="Game1",
            program_path="C:/Game1/game1.exe",
        )

        # After 5s, start b1/Game2 (overlaps with Game1), runs 45s from its own start
        ft.tick(5)
        t1 = int(time.time())
        sid2 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle1",
            bottle_path="/b1",
            program_name="Game2",
            program_path="C:/Game2/game2.exe",
        )

        # After 10s more, start b2/Game1 (overlaps with both), runs 60s from its own start
        ft.tick(10)
        t2 = int(time.time())
        sid3 = tracker.start_session(
            bottle_id="b2",
            bottle_name="Bottle2",
            bottle_path="/b2",
            program_name="Game1",
            program_path="C:/Game1/game1.exe",
        )

        # Now finalize in order with explicit end times
        tracker.mark_exit(sid1, status="success", ended_at=t0 + 30)
        tracker.mark_exit(sid2, status="success", ended_at=t1 + 45)
        tracker.mark_exit(sid3, status="success", ended_at=t2 + 60)

    con = sqlite3.connect(tracker.db_path)
    cur = con.cursor()

    # Totals rows: 2 for b1 (Game1, Game2), 1 for b2 (Game1)
    cur.execute("SELECT COUNT(*) FROM playtime_totals WHERE bottle_id=?", ("b1",))
    assert cur.fetchone()[0] == 2
    cur.execute("SELECT COUNT(*) FROM playtime_totals WHERE bottle_id=?", ("b2",))
    assert cur.fetchone()[0] == 1

    # Check durations/sessions_count
    cur.execute(
        "SELECT total_seconds, sessions_count FROM playtime_totals WHERE bottle_id=? AND program_name=?",
        ("b1", "Game1"),
    )
    tsec, scount = cur.fetchone()
    assert scount == 1 and tsec >= 30

    cur.execute(
        "SELECT total_seconds, sessions_count FROM playtime_totals WHERE bottle_id=? AND program_name=?",
        ("b1", "Game2"),
    )
    tsec, scount = cur.fetchone()
    assert scount == 1 and tsec >= 45

    cur.execute(
        "SELECT total_seconds, sessions_count FROM playtime_totals WHERE bottle_id=? AND program_name=?",
        ("b2", "Game1"),
    )
    tsec, scount = cur.fetchone()
    assert scount == 1 and tsec >= 60


