import os
import sqlite3
import tempfile

from bottles.backend.managers.manager import Manager
from bottles.backend.managers.playtime import ProcessSessionTracker
from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.winepath import WinePath
from bottles.backend.models.result import Result


class _Settings:
    def get_boolean(self, key: str) -> bool:
        return True if key == "playtime-enabled" else False

    def get_int(self, key: str) -> int:
        return 5 if key == "playtime-heartbeat-interval" else 0


def _new_manager(tmpdir: str) -> Manager:
    os.environ["XDG_DATA_HOME"] = tmpdir
    m = Manager(g_settings=_Settings(), check_connection=False, is_cli=True)
    base_dir = os.path.join(tmpdir, "bottles")
    os.makedirs(base_dir, exist_ok=True)
    db_path = os.path.join(base_dir, "process_metrics.sqlite")
    m.playtime_tracker = ProcessSessionTracker(db_path=db_path, heartbeat_interval=5, enabled=True)
    try:
        m._launch_to_session.clear()
    except Exception:
        pass
    return m


def _config(name: str) -> BottleConfig:
    c = BottleConfig()
    c.Name = name
    c.Path = name
    return c


def test_wine_executor_emits_and_updates_totals(mocker):
    with tempfile.TemporaryDirectory() as tmp:
        m = _new_manager(tmp)

        # Stub the launch paths to avoid running wine; make them return success Result
        _stub_result = Result(True, data={"output": b"ok"})
        mocker.patch.object(WineExecutor, "_WineExecutor__launch_with_bridge", return_value=_stub_result)
        mocker.patch.object(WineExecutor, "_WineExecutor__launch_batch", return_value=_stub_result)
        mocker.patch.object(WineExecutor, "_WineExecutor__launch_with_starter", return_value=_stub_result)
        mocker.patch.object(WineExecutor, "_WineExecutor__launch_dll", return_value=_stub_result)

        # Stub WinePath conversions to avoid system calls / missing libs
        # Instance methods are bound; side_effect receives only the path argument
        mocker.patch.object(WinePath, "to_unix", side_effect=lambda path: path)
        mocker.patch.object(WinePath, "to_windows", side_effect=lambda path: path)

        execu = WineExecutor(
            config=_config("b1"),
            exec_path="C:/Game/game.exe",
        )
        res = execu.run()
        assert res.status is True

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

