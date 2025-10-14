import os
import sqlite3
import tempfile

from bottles.backend.managers.manager import Manager
from bottles.backend.managers.playtime import ProcessSessionTracker
from bottles.backend.state import SignalManager, Signals
from bottles.backend.models.result import Result
from bottles.backend.models.process import (
    ProcessStartedPayload,
    ProcessFinishedPayload,
)


class _Settings:
    def get_boolean(self, key: str) -> bool:
        return True if key == "playtime-enabled" else False

    def get_int(self, key: str) -> int:
        return 5 if key == "playtime-heartbeat-interval" else 0


def _new_manager(tmpdir: str) -> Manager:
    os.environ["XDG_DATA_HOME"] = tmpdir
    m = Manager(g_settings=_Settings(), check_connection=False, is_cli=True)
    # Force a fresh tracker bound to this tmpdir DB
    base_dir = os.path.join(tmpdir, "bottles")
    os.makedirs(base_dir, exist_ok=True)
    db_path = os.path.join(base_dir, "process_metrics.sqlite")
    m.playtime_tracker = ProcessSessionTracker(db_path=db_path, heartbeat_interval=5, enabled=True)
    # Reset launch map if present
    try:
        m._launch_to_session.clear()
    except Exception:
        pass
    return m


def test_signals_flow_success():
    with tempfile.TemporaryDirectory() as tmp:
        m = _new_manager(tmp)

        started = ProcessStartedPayload(
            launch_id="test-launch-1",
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        SignalManager.send(Signals.ProgramStarted, Result(True, started))
        finished = ProcessFinishedPayload(
            launch_id=started.launch_id,
            status="success",
            ended_at=0,
        )
        SignalManager.send(Signals.ProgramFinished, Result(True, finished))

        con = sqlite3.connect(m.playtime_tracker.db_path)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM sessions WHERE bottle_id=?", ("b1",))
        assert cur.fetchone()[0] == 1
        cur.execute(
            "SELECT sessions_count FROM playtime_totals WHERE bottle_id=?",
            ("b1",),
        )
        assert cur.fetchone()[0] == 1
        m.playtime_tracker.shutdown()


def test_signals_flow_unknown_failure():
    with tempfile.TemporaryDirectory() as tmp:
        m = _new_manager(tmp)

        started = ProcessStartedPayload(
            launch_id="test-launch-2",
            bottle_id="b1",
            bottle_name="Bottle",
            bottle_path="/bottle",
            program_name="Game",
            program_path="C:/Game/game.exe",
        )
        SignalManager.send(Signals.ProgramStarted, Result(True, started))
        finished = ProcessFinishedPayload(
            launch_id=started.launch_id,
            status="unknown",
            ended_at=0,
        )
        SignalManager.send(Signals.ProgramFinished, Result(True, finished))

        con = sqlite3.connect(m.playtime_tracker.db_path)
        cur = con.cursor()
        cur.execute(
            "SELECT status FROM sessions WHERE bottle_id=? ORDER BY id DESC LIMIT 1",
            ("b1",),
        )
        assert cur.fetchone()[0] == "unknown"
        m.playtime_tracker.shutdown()

