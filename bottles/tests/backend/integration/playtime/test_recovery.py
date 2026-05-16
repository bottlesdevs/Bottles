"""Recovery should force-close running sessions on restart."""

import sqlite3
import time
from freezegun import freeze_time

from bottles.backend.managers.manager import Manager
from bottles.backend.managers.playtime import ProcessSessionTracker


def test_recovery_smoke(manager):
    tracker = manager.playtime_tracker
    assert tracker is not None

    with freeze_time("2025-01-01 05:00:00"):
        base = int(time.time())
        sid = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        # Simulate abrupt stop without finalizing
        tracker.shutdown()

        # New tracker instance simulates app restart and recovers open sessions
        new_tracker = ProcessSessionTracker(
            db_path=tracker.db_path, heartbeat_interval=5, enabled=True
        )
        new_tracker.recover_open_sessions()

    con = sqlite3.connect(new_tracker.db_path)
    cur = con.cursor()
    cur.execute("SELECT status, ended_at, last_seen FROM sessions WHERE id=?", (sid,))
    status, ended_at, last_seen = cur.fetchone()
    assert status == "forced"
    assert ended_at == last_seen

    cur.execute(
        "SELECT sessions_count FROM playtime_totals WHERE bottle_id=?",
        ("b1",),
    )
    assert cur.fetchone()[0] == 1


def test_recovery_different_bottles(manager):
    tracker = manager.playtime_tracker
    assert tracker is not None

    with freeze_time("2025-01-01 06:00:00"):
        sid1 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle1",
            bottle_path="/b1",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        sid2 = tracker.start_session(
            bottle_id="b2",
            bottle_name="Bottle2",
            bottle_path="/b2",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )

        tracker.shutdown()
        new_tracker = ProcessSessionTracker(
            db_path=tracker.db_path, heartbeat_interval=5, enabled=True
        )
        new_tracker.recover_open_sessions()

    con = sqlite3.connect(new_tracker.db_path)
    cur = con.cursor()
    # Both sessions forced
    cur.execute("SELECT COUNT(*) FROM sessions WHERE status='forced'")
    assert cur.fetchone()[0] == 2
    # Two totals rows
    cur.execute("SELECT COUNT(*) FROM playtime_totals")
    assert cur.fetchone()[0] == 2
    # Each bottle has sessions_count=1
    cur.execute("SELECT sessions_count FROM playtime_totals WHERE bottle_id=?", ("b1",))
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT sessions_count FROM playtime_totals WHERE bottle_id=?", ("b2",))
    assert cur.fetchone()[0] == 1


def test_recovery_same_bottle_different_programs(manager):
    tracker = manager.playtime_tracker
    assert tracker is not None

    with freeze_time("2025-01-01 07:00:00"):
        sid1 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game1",
            program_path="C:/Game1/game1.exe",
        )
        sid2 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game2",
            program_path="C:/Game2/game2.exe",
        )

        tracker.shutdown()
        new_tracker = ProcessSessionTracker(
            db_path=tracker.db_path, heartbeat_interval=5, enabled=True
        )
        new_tracker.recover_open_sessions()

    con = sqlite3.connect(new_tracker.db_path)
    cur = con.cursor()
    # Two forced sessions in same bottle
    cur.execute("SELECT COUNT(*) FROM sessions WHERE status='forced' AND bottle_id=?", ("b1",))
    assert cur.fetchone()[0] == 2
    # Two totals rows for the bottle
    cur.execute("SELECT COUNT(*) FROM playtime_totals WHERE bottle_id=?", ("b1",))
    assert cur.fetchone()[0] == 2


def test_cli_manager_init_does_not_recover_live_sessions(temp_xdg_home, test_settings_stub):
    Manager._instances.pop(Manager, None)
    manager = Manager(g_settings=test_settings_stub, check_connection=False, is_cli=True)
    tracker = manager.playtime_tracker
    assert tracker is not None

    sid = tracker.start_session(
        bottle_id="b1",
        bottle_name="Bottle",
        bottle_path="/bottle",
        program_name="Game",
        program_path="C:/Game/game.exe",
    )

    Manager._instances.pop(Manager, None)
    other_manager = Manager(
        g_settings=test_settings_stub,
        check_connection=False,
        is_cli=True,
    )

    con = sqlite3.connect(other_manager.playtime_tracker.db_path)
    cur = con.cursor()
    cur.execute("SELECT status FROM sessions WHERE id=?", (sid,))
    assert cur.fetchone()[0] == "running"

    tracker.shutdown()
    other_manager.playtime_tracker.shutdown()
    Manager._instances.pop(Manager, None)


