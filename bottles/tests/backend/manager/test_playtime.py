import os
import sqlite3
import tempfile
import time

from bottles.backend.managers.playtime import ProcessSessionTracker


def _new_tracker(tmpdir, enabled=True, heartbeat_interval=5):
    db_path = os.path.join(tmpdir, "process_metrics.sqlite")
    return ProcessSessionTracker(
        db_path=db_path, heartbeat_interval=heartbeat_interval, enabled=enabled
    )


def test_schema_created_and_wal():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        conn = sqlite3.connect(tracker.db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        assert "sessions" in tables
        assert "playtime_totals" in tables
        cur.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0].lower()
        assert mode in ("wal", "wal2") or mode == "wal"  # wal expected
        tracker.shutdown()


def test_start_and_heartbeat_and_exit_updates_totals():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        sid = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        assert sid > 0

        time.sleep(1.0)  # simulate some playtime
        tracker._flush_heartbeats()  # update last_seen deterministically
        tracker.mark_exit(sid, status="success")

        conn = sqlite3.connect(tracker.db_path)
        cur = conn.cursor()
        cur.execute("SELECT status, duration_seconds FROM sessions WHERE id=?", (sid,))
        status, duration = cur.fetchone()
        assert status == "success"
        assert duration >= 1

        cur.execute(
            "SELECT total_seconds, sessions_count FROM playtime_totals WHERE bottle_id=?",
            ("b1",),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] >= 1
        assert row[1] == 1
        tracker.shutdown()


def test_recovery_finalizes_running_sessions():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        sid = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        time.sleep(0.5)
        tracker.shutdown()  # simulate abrupt stop

        # new tracker recovers
        tracker2 = _new_tracker(tmp)
        tracker2.recover_open_sessions()

        conn = sqlite3.connect(tracker2.db_path)
        cur = conn.cursor()
        cur.execute("SELECT status, ended_at, last_seen FROM sessions WHERE id=?", (sid,))
        status, ended_at, last_seen = cur.fetchone()
        assert status == "forced"
        assert ended_at == last_seen

        cur.execute(
            "SELECT sessions_count FROM playtime_totals WHERE bottle_id=?",
            ("b1",),
        )
        assert cur.fetchone()[0] == 1
        tracker2.shutdown()


def test_disabled_tracker_is_noop():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp, enabled=False)
        sid = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        assert sid == -1
        tracker.shutdown()


def test_mark_failure():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        sid = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        time.sleep(0.5)
        tracker.mark_failure(sid, status="crash")

        conn = sqlite3.connect(tracker.db_path)
        cur = conn.cursor()
        cur.execute("SELECT status FROM sessions WHERE id=?", (sid,))
        assert cur.fetchone()[0] == "crash"
        tracker.shutdown()


def test_multiple_sessions_aggregate():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        # First session
        sid1 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        time.sleep(1.0)
        tracker.mark_exit(sid1, status="success")

        # Second session, same program
        sid2 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        time.sleep(1.0)
        tracker.mark_exit(sid2, status="success")

        conn = sqlite3.connect(tracker.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT total_seconds, sessions_count FROM playtime_totals WHERE bottle_id=? AND program_name=?",
            ("b1", "Game"),
        )
        total_seconds, sessions_count = cur.fetchone()
        assert sessions_count == 2
        assert total_seconds >= 2
        tracker.shutdown()


def test_different_programs_separate_totals():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        sid1 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game1",
            program_path="C:/Game1/game1.exe",
        )
        tracker.mark_exit(sid1, status="success")

        sid2 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game2",
            program_path="C:/Game2/game2.exe",
        )
        tracker.mark_exit(sid2, status="success")

        conn = sqlite3.connect(tracker.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM playtime_totals WHERE bottle_id=?", ("b1",))
        assert cur.fetchone()[0] == 2
        tracker.shutdown()


def test_program_id_consistency():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        sid1 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        tracker.mark_exit(sid1, status="success")

        # Same path, different name → same program_id
        sid2 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game Renamed",
            program_path="C:/Game/game.exe",
        )
        tracker.mark_exit(sid2, status="success")

        conn = sqlite3.connect(tracker.db_path)
        cur = conn.cursor()
        # Should have aggregated into one total
        cur.execute("SELECT sessions_count FROM playtime_totals WHERE bottle_id=?", ("b1",))
        assert cur.fetchone()[0] == 2
        tracker.shutdown()


def test_indices_exist():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        conn = sqlite3.connect(tracker.db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indices = {r[0] for r in cur.fetchall()}
        assert "idx_sessions_bottle_program" in indices
        assert "idx_sessions_status" in indices
        assert "idx_totals_last_played" in indices
        tracker.shutdown()


def test_user_version_set():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        conn = sqlite3.connect(tracker.db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA user_version")
        assert cur.fetchone()[0] == 1
        tracker.shutdown()


def test_unique_constraint():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        sid1 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        # Try to insert duplicate at same timestamp (will use started_at from first session)
        conn = sqlite3.connect(tracker.db_path)
        cur = conn.cursor()
        cur.execute("SELECT program_id, started_at FROM sessions WHERE id=?", (sid1,))
        program_id, started_at = cur.fetchone()

        # Attempt duplicate insert (should fail)
        try:
            cur.execute(
                """INSERT INTO sessions (
                    bottle_id, bottle_name, bottle_path, program_id, program_name, program_path,
                    started_at, last_seen, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("b1", "Bottle", "/bottle", program_id, "Game", "C:/Game/game.exe", started_at, started_at, "running")
            )
            conn.commit()
            assert False, "Expected UNIQUE constraint violation"
        except sqlite3.IntegrityError:
            pass  # Expected
        tracker.shutdown()


def test_disable_tracking_method():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        sid = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        assert sid > 0

        tracker.disable_tracking()
        # After disabling, new sessions should be no-op
        sid2 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game2",
            program_path="C:/Game2/game2.exe",
        )
        assert sid2 == -1


def test_start_session_collapses_duplicate_running_session():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        sid1 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        # Second start without finalize should return the same session id
        sid2 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game (alias)",
            program_path="C:/Game/game.exe",
        )
        assert sid2 == sid1

        conn = sqlite3.connect(tracker.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM sessions WHERE bottle_id=? AND status='running'",
            ("b1",),
        )
        assert cur.fetchone()[0] == 1
        tracker.shutdown()

