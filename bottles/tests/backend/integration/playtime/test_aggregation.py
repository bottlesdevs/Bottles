"""Aggregation scenarios (same program vs different programs)."""

import sqlite3
import time
from freezegun import freeze_time


def test_same_program_aggregates_into_one_row(manager):
    tracker = manager.playtime_tracker
    assert tracker is not None

    with freeze_time("2025-01-01 00:00:00") as ft:
        base = int(time.time())
        # First session, 60s
        sid1 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        tracker.mark_exit(sid1, status="success", ended_at=base + 60)

        # Advance time, second session same path but different name, 60s
        ft.tick(120)
        base2 = int(time.time())
        sid2 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game Renamed",
            program_path="C:/Game/game.exe",
        )
        tracker.mark_exit(sid2, status="success", ended_at=base2 + 60)

    con = sqlite3.connect(tracker.db_path)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM playtime_totals WHERE bottle_id=?", ("b1",))
    assert cur.fetchone()[0] == 1
    cur.execute(
        "SELECT total_seconds, sessions_count FROM playtime_totals WHERE bottle_id=?",
        ("b1",),
    )
    total_seconds, sessions_count = cur.fetchone()
    assert sessions_count == 2
    assert total_seconds >= 120


def test_different_programs_separate_rows(manager):
    tracker = manager.playtime_tracker
    assert tracker is not None

    with freeze_time("2025-01-01 01:00:00"):
        base = int(time.time())
        sid1 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game1",
            program_path="C:/Game1/game1.exe",
        )
        tracker.mark_exit(sid1, status="success", ended_at=base + 30)

        sid2 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game2",
            program_path="C:/Game2/game2.exe",
        )
        tracker.mark_exit(sid2, status="success", ended_at=base + 60)

    con = sqlite3.connect(tracker.db_path)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM playtime_totals WHERE bottle_id=?", ("b1",))
    assert cur.fetchone()[0] == 2

