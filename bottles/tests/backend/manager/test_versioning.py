from concurrent.futures import CancelledError
from types import SimpleNamespace

import pytest

from bottles.backend.managers import versioning as versioning_module
from bottles.backend.managers.versioning import VersioningManager
from bottles.backend.state import SignalManager, TaskManager


@pytest.fixture(autouse=True)
def isolated_tasks():
    tasks = TaskManager._TASKS
    signals = SignalManager._SIGNALS
    TaskManager._TASKS = {}
    SignalManager._SIGNALS = {}
    yield
    TaskManager._TASKS = tasks
    SignalManager._SIGNALS = signals


@pytest.fixture
def snapshot_config():
    return SimpleNamespace(
        Name="Test",
        Parameters=SimpleNamespace(
            versioning_compression=False,
            versioning_exclusion_patterns=False,
        ),
        Versioning_Exclusion_Patterns=[],
    )


def test_create_state_cancellation_does_not_refresh_repository(
    tmp_path, monkeypatch, snapshot_config
):
    bottle = tmp_path / "bottle"
    drive_c = bottle / "drive_c"
    drive_c.mkdir(parents=True)
    head = bottle / ".fvs2" / "HEAD.json"
    index = bottle / ".fvs2" / "index.json"
    ref = bottle / ".fvs2" / "refs" / "heads" / "main"
    head.parent.mkdir()
    ref.parent.mkdir(parents=True)
    head.write_text("old-head")
    index.write_text("old-index")
    ref.write_text("old-ref")

    repositories = []

    class RepoStub:
        def __init__(self, **_kwargs):
            self.refreshed = False
            repositories.append(self)

        def commit(self, _message, **kwargs):
            assert kwargs["cancel_event"] is not None
            kwargs["cancel_event"].set()
            raise CancelledError

        def _refresh(self):
            self.refreshed = True

    monkeypatch.setattr(
        versioning_module.ManagerUtils,
        "get_bottle_path",
        lambda _config: str(bottle),
    )
    monkeypatch.setattr(versioning_module, "FVSRepo", RepoStub)
    monkeypatch.setattr(
        versioning_module.FileUtils,
        "get_disk_size",
        lambda *_args, **_kwargs: {"free": 1024 * 1024 * 1024},
    )

    result = VersioningManager(SimpleNamespace()).create_state(
        snapshot_config, "snapshot"
    )

    assert not result.status
    assert result.message == "cancelled"
    assert head.read_text() == "old-head"
    assert index.read_text() == "old-index"
    assert ref.read_text() == "old-ref"
    assert not repositories[0].refreshed
    assert TaskManager._TASKS == {}


def test_create_state_removes_task_after_error(tmp_path, monkeypatch, snapshot_config):
    bottle = tmp_path / "bottle"
    (bottle / "drive_c").mkdir(parents=True)

    class RepoStub:
        def __init__(self, **_kwargs):
            pass

        def commit(self, *_args, **_kwargs):
            raise RuntimeError("failure")

    monkeypatch.setattr(
        versioning_module.ManagerUtils,
        "get_bottle_path",
        lambda _config: str(bottle),
    )
    monkeypatch.setattr(versioning_module, "FVSRepo", RepoStub)
    monkeypatch.setattr(
        versioning_module.FileUtils,
        "get_disk_size",
        lambda *_args, **_kwargs: {"free": 1024 * 1024 * 1024},
    )

    result = VersioningManager(SimpleNamespace()).create_state(snapshot_config)

    assert not result.status
    assert TaskManager._TASKS == {}


def test_create_state_can_cancel_initial_size_scan(
    tmp_path, monkeypatch, snapshot_config
):
    bottle = tmp_path / "bottle"
    (bottle / "drive_c").mkdir(parents=True)

    def cancel_scan(_self, _path, human=True, cancel_event=None):
        task_id = next(iter(TaskManager._TASKS))
        assert TaskManager.cancel(task_id)
        assert cancel_event.is_set()
        raise CancelledError

    monkeypatch.setattr(
        versioning_module.ManagerUtils,
        "get_bottle_path",
        lambda _config: str(bottle),
    )
    monkeypatch.setattr(versioning_module.FileUtils, "get_path_size", cancel_scan)
    monkeypatch.setattr(
        versioning_module,
        "FVSRepo",
        lambda **_kwargs: pytest.fail("repository should not be created"),
    )

    result = VersioningManager(SimpleNamespace()).create_state(snapshot_config)

    assert not result.status
    assert result.message == "cancelled"
    assert TaskManager._TASKS == {}


def test_create_state_does_not_initialize_after_cancellation(
    tmp_path, monkeypatch, snapshot_config
):
    bottle = tmp_path / "bottle"
    (bottle / "drive_c").mkdir(parents=True)

    def cancel_before_init(*_args, **_kwargs):
        task_id = next(iter(TaskManager._TASKS))
        assert TaskManager.cancel(task_id)
        return {"free": 1024 * 1024 * 1024}

    monkeypatch.setattr(
        versioning_module.ManagerUtils,
        "get_bottle_path",
        lambda _config: str(bottle),
    )
    monkeypatch.setattr(versioning_module.FileUtils, "get_disk_size", cancel_before_init)
    monkeypatch.setattr(
        versioning_module,
        "FVSRepo",
        lambda **_kwargs: pytest.fail("repository should not be initialized"),
    )

    result = VersioningManager(SimpleNamespace()).create_state(snapshot_config)

    assert not result.status
    assert result.message == "cancelled"
    assert TaskManager._TASKS == {}


def test_create_state_keeps_success_result(tmp_path, monkeypatch, snapshot_config):
    bottle = tmp_path / "bottle"
    (bottle / "drive_c").mkdir(parents=True)
    refreshed = []

    class RepoStub:
        active_state_id = "state-id"
        states = {"state-id": {"message": "snapshot"}}
        branches = ["main"]
        active_branch = "main"

        def __init__(self, **_kwargs):
            self.refreshed = False

        def commit(self, _message, **kwargs):
            assert kwargs["cancel_event"] is not None

        def _refresh(self):
            self.refreshed = True
            refreshed.append(True)

    monkeypatch.setattr(
        versioning_module.ManagerUtils,
        "get_bottle_path",
        lambda _config: str(bottle),
    )
    monkeypatch.setattr(versioning_module, "FVSRepo", RepoStub)
    monkeypatch.setattr(
        versioning_module.FileUtils,
        "get_disk_size",
        lambda *_args, **_kwargs: {"free": 1024 * 1024 * 1024},
    )

    result = VersioningManager(SimpleNamespace()).create_state(snapshot_config)

    assert result.status
    assert result.data == {
        "state_id": "state-id",
        "states": {"state-id": {"message": "snapshot"}},
        "branches": ["main"],
        "active_branch": "main",
    }
    assert refreshed == [True]
    assert TaskManager._TASKS == {}


def test_list_states_handles_missing_bottle(tmp_path, monkeypatch, snapshot_config):
    missing_bottle = tmp_path / "missing"
    snapshot_config.Versioning = False

    monkeypatch.setattr(
        versioning_module.ManagerUtils,
        "get_bottle_path",
        lambda _config: str(missing_bottle),
    )

    result = VersioningManager(SimpleNamespace()).list_states(snapshot_config)

    assert not result.status
    assert not missing_bottle.exists()
    assert result.data == {
        "state_id": None,
        "states": {},
        "branches": [],
        "active_branch": "",
        "dirty": False,
        "changed_files": 0,
    }


def test_list_states_handles_bottle_removed_during_recovery(
    tmp_path, monkeypatch, snapshot_config
):
    bottle = tmp_path / "bottle"
    bottle.mkdir()
    snapshot_config.Versioning = False
    attempts = []

    class RepoStub:
        def __init__(self, **_kwargs):
            attempts.append(True)
            if len(attempts) == 1:
                raise versioning_module.FVSStateNotFound
            bottle.rmdir()
            raise FileNotFoundError

    monkeypatch.setattr(
        versioning_module.ManagerUtils,
        "get_bottle_path",
        lambda _config: str(bottle),
    )
    monkeypatch.setattr(versioning_module, "FVSRepo", RepoStub)

    result = VersioningManager(SimpleNamespace()).list_states(snapshot_config)

    assert len(attempts) == 2
    assert not result.status
    assert result.data["states"] == {}
