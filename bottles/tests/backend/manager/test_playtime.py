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


def test_get_totals_returns_program_stats():
    """Test get_totals retrieves per-program aggregated data."""
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        from bottles.backend.managers.playtime import _compute_program_id

        program_id = _compute_program_id("b1", "/bottle", "C:/Game/game.exe")

        sid = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        time.sleep(1.0)
        tracker.mark_exit(sid, status="success")

        result = tracker.get_totals("b1", program_id)
        assert result is not None
        assert result["bottle_id"] == "b1"
        assert result["program_id"] == program_id
        assert result["program_name"] == "Game"
        assert result["total_seconds"] >= 1
        assert result["sessions_count"] == 1
        assert result["last_played"] is not None
        tracker.shutdown()


def test_get_totals_returns_none_when_not_found():
    """Test get_totals returns None for non-existent program."""
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        result = tracker.get_totals("b1", "nonexistent_program_id")
        assert result is None
        tracker.shutdown()


def test_get_totals_returns_none_when_disabled():
    """Test get_totals returns None when tracking is disabled."""
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp, enabled=False)
        result = tracker.get_totals("b1", "any_program_id")
        assert result is None
        tracker.shutdown()


def test_get_all_program_totals_returns_all_programs():
    """Test get_all_program_totals retrieves all programs for a bottle."""
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)

        # Create two sessions for different programs in same bottle
        sid1 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game1",
            program_path="C:/Game1/game1.exe",
        )
        time.sleep(0.5)
        tracker.mark_exit(sid1, status="success")

        sid2 = tracker.start_session(
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game2",
            program_path="C:/Game2/game2.exe",
        )
        time.sleep(0.5)
        tracker.mark_exit(sid2, status="success")

        results = tracker.get_all_program_totals("b1")
        assert len(results) == 2
        program_names = {r["program_name"] for r in results}
        assert "Game1" in program_names
        assert "Game2" in program_names
        tracker.shutdown()


def test_get_all_program_totals_returns_empty_when_disabled():
    """Test get_all_program_totals returns empty list when disabled."""
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp, enabled=False)
        results = tracker.get_all_program_totals("b1")
        assert results == []
        tracker.shutdown()


def test_normalize_path_to_windows():
    """Test path normalization converts Unix paths to Windows format."""
    from bottles.backend.managers.playtime import _normalize_path_to_windows
    
    # Already Windows format - should remain unchanged
    assert _normalize_path_to_windows("/bottle", "C:\\Program Files\\game.exe") == "C:\\Program Files\\game.exe"
    assert _normalize_path_to_windows("/bottle", "D:\\Games\\game.exe") == "D:\\Games\\game.exe"
    
    # Unix path with drive_c - bottle_path must match the path prefix
    bottle_path = "/var/home/user/.local/share/bottles/MyBottle"
    unix_path = "/var/home/user/.local/share/bottles/MyBottle/drive_c/Program Files/game.exe"
    assert _normalize_path_to_windows(bottle_path, unix_path) == "C:\\Program Files\\game.exe"
    
    # Unix path with drive_d - should convert to D:\
    unix_path_d = "/path/to/bottle/drive_d/Games/game.exe"
    assert _normalize_path_to_windows("/path/to/bottle", unix_path_d) == "D:\\Games\\game.exe"
    
    # Test with different drive letters
    assert _normalize_path_to_windows("/bottle", "/bottle/drive_z/test.exe") == "Z:\\test.exe"


def test_database_stores_normalized_paths():
    """Test that program_path is stored in normalized Windows format in the database."""
    with tempfile.TemporaryDirectory() as tmp:
        tracker = _new_tracker(tmp)
        
        bottle_id = "test-bottle"
        bottle_name = "Test Bottle"
        bottle_path = "/home/user/.local/share/bottles/TestBottle"
        
        # Start session with Unix-format path
        unix_path = f"{bottle_path}/drive_c/Program Files/TestGame/game.exe"
        session_id = tracker.start_session(
            bottle_id=bottle_id,
            bottle_name=bottle_name,
            bottle_path=bottle_path,
            program_name="TestGame",
            program_path=unix_path,
        )
        
        # Check sessions table has normalized path
        conn = sqlite3.connect(tracker.db_path)
        cur = conn.cursor()
        cur.execute("SELECT program_path FROM sessions WHERE id=?", (session_id,))
        row = cur.fetchone()
        assert row is not None
        stored_path = row[0]
        # Should be Windows format, not Unix format
        assert stored_path == "C:\\Program Files\\TestGame\\game.exe"
        assert not stored_path.startswith("/home/")
        
        # Exit session to trigger totals update
        tracker.mark_exit(session_id, status="success")
        
        # Check playtime_totals table also has normalized path
        cur.execute("SELECT program_path FROM playtime_totals WHERE bottle_id=?", (bottle_id,))
        row = cur.fetchone()
        assert row is not None
        totals_path = row[0]
        assert totals_path == "C:\\Program Files\\TestGame\\game.exe"
        assert not totals_path.startswith("/home/")
        
        tracker.shutdown()


