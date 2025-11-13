import os
import sys
import types
import tempfile
import contextlib
import sqlite3
import pytest

_glib_stub = types.SimpleNamespace(
    SOURCE_REMOVE=False,
    idle_add=lambda func, *args, **kwargs: func(),
    timeout_add=lambda *_a, **_k: 0,
)
_gi_repository = types.SimpleNamespace(GLib=_glib_stub)
sys.modules.setdefault("gi", types.SimpleNamespace(repository=_gi_repository))
sys.modules.setdefault("gi.repository", _gi_repository)

class _FVSRepoStub:
    def __init__(self, *args, **kwargs):
        self.active_state_id = 0
        self.states = []
        self.has_no_states = True

    def commit(self, *_args, **_kwargs):
        return None

    def restore_state(self, *_args, **_kwargs):
        return None


class _FVSError(Exception):
    pass


_fvs_exceptions = types.SimpleNamespace(
    FVSNothingToCommit=_FVSError,
    FVSStateNotFound=_FVSError,
    FVSNothingToRestore=_FVSError,
    FVSStateZeroNotDeletable=_FVSError,
)
_fvs_repo = types.SimpleNamespace(FVSRepo=_FVSRepoStub)
sys.modules.setdefault("fvs", types.SimpleNamespace(repo=_fvs_repo, exceptions=_fvs_exceptions))
sys.modules.setdefault("fvs.repo", _fvs_repo)
sys.modules.setdefault("fvs.exceptions", _fvs_exceptions)

from bottles.backend.managers.manager import Manager
from bottles.backend.managers.playtime import ProcessSessionTracker


@pytest.fixture()
def temp_xdg_home(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("XDG_DATA_HOME", tmp)
        yield tmp


@pytest.fixture()
def test_settings_stub():
    class _S:
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


