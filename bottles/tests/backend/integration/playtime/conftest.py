import os
import tempfile
import contextlib
import sqlite3
import pytest
from gi.repository import GLib

from bottles.backend.managers.manager import Manager
from bottles.backend.utils.gsettings_stub import GSettingsStub
from bottles.backend.managers.playtime import ProcessSessionTracker


@pytest.fixture(autouse=True)
def synchronous_callbacks(monkeypatch):
    monkeypatch.setattr(GLib, "idle_add", lambda func, *args, **kwargs: func(*args))
    monkeypatch.setattr(GLib, "timeout_add", lambda *_args, **_kwargs: 0)


@pytest.fixture()
def temp_xdg_home(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("XDG_DATA_HOME", tmp)
        yield tmp


@pytest.fixture()
def test_settings_stub():
    class _S(GSettingsStub):
        def get_boolean(self, key: str) -> bool:
            return True if key == "playtime-enabled" else False

        def get_int(self, key: str) -> int:
            return 5 if key == "playtime-heartbeat-interval" else 0

    return _S()


@pytest.fixture()
def manager(temp_xdg_home, test_settings_stub):
    m = Manager(g_settings=test_settings_stub, check_connection=False, is_cli=True)
    # Override tracker per-test to avoid singleton reuse and cross-test DB conflicts
    db_dir = os.path.join(temp_xdg_home, "bottles")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "process_metrics.sqlite")
    tracker = ProcessSessionTracker(db_path=db_path, heartbeat_interval=5, enabled=True)
    m.playtime_tracker = tracker
    yield m
    with contextlib.suppress(Exception):
        tracker.shutdown()


def open_db(m: Manager) -> sqlite3.Connection:
    return sqlite3.connect(m.playtime_tracker.db_path)


