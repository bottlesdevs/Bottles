from types import SimpleNamespace

import pytest

from bottles.backend.globals import Paths
from bottles.backend.managers import dependency
from bottles.backend.managers.dependency import DependencyManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.state import TaskManager


class Recorder:
    """Collects what the dependency manager does around an installer."""

    def __init__(self, installer_result: Result):
        self.installer_result = installer_result
        self.executors: list[dict] = []
        self.config_updates: list[str] = []
        self.rules_applied: list[str] = []


@pytest.fixture
def recorder(monkeypatch, tmp_path):
    state = Recorder(Result(True))

    class FakeExecutor:
        def __init__(self, config, **kwargs):
            state.executors.append(kwargs)

        def run(self):
            return state.installer_result

    monkeypatch.setattr(Paths, "temp", str(tmp_path))
    monkeypatch.setattr(dependency, "WineExecutor", FakeExecutor)
    monkeypatch.setattr(
        dependency,
        "WineDbg",
        lambda _config: SimpleNamespace(wait_for_process=lambda _file: True),
    )
    monkeypatch.setattr(
        dependency.RegistryRuleManager,
        "apply_rules",
        lambda _config, trigger: state.rules_applied.append(trigger),
    )
    return state


def _dependency_manager(state: Recorder, download_ok: bool = True):
    manager = SimpleNamespace(
        component_manager=SimpleNamespace(
            download=lambda **_kwargs: Result(download_ok)
        ),
        update_config=lambda config, key, value, scope="": state.config_updates.append(
            key
        ),
        versioning_manager=SimpleNamespace(create_state=lambda **_kwargs: None),
        supported_dependencies={},
    )
    dependency_manager = DependencyManager.__new__(DependencyManager)
    dependency_manager._DependencyManager__manager = manager
    dependency_manager._DependencyManager__manifests = {}
    return dependency_manager


def _manifest(**step):
    return {
        "Dependencies": [],
        "Steps": [
            {
                "action": "install_exe",
                "url": "https://example.invalid/setup.exe",
                "file_name": "setup.exe",
                "arguments": "/quiet",
                **step,
            }
        ],
    }


def _install(dependency_manager, manifest):
    dependency_manager.get_dependency = lambda _name: manifest
    config = BottleConfig(Name="Bottle")
    return config, dependency_manager.install(config, ["example", manifest])


@pytest.mark.parametrize("action", ["install_exe", "install_msi"])
def test_failed_installer_does_not_mark_the_dependency_installed(recorder, action):
    recorder.installer_result = Result(False, message="Command exited with status 67.")
    tasks_before = set(TaskManager._TASKS)

    config, result = _install(_dependency_manager(recorder), _manifest(action=action))

    assert not result.ok
    assert result.message == (
        "One or more steps failed for example. Command exited with status 67."
    )
    assert config.Installed_Dependencies == []
    assert recorder.config_updates == []
    assert recorder.rules_applied == []
    assert set(TaskManager._TASKS) == tasks_before


def test_successful_installer_marks_the_dependency_installed(recorder):
    recorder.installer_result = Result(True)

    _, result = _install(_dependency_manager(recorder), _manifest())

    assert result.ok
    assert recorder.config_updates == ["Installed_Dependencies", "example"]
    assert recorder.rules_applied == ["dependencies"]


def test_installer_is_run_with_the_default_success_codes(recorder):
    _install(_dependency_manager(recorder), _manifest())

    assert recorder.executors[0]["success_codes"] == [1638, 1641, 3010, 3011]


def test_step_can_accept_more_success_codes(recorder):
    _install(
        _dependency_manager(recorder),
        _manifest(success_codes=[5100, True, "3", None]),
    )

    assert recorder.executors[0]["success_codes"] == [
        1638,
        1641,
        3010,
        3011,
        5100,
    ]


def test_invalid_success_codes_are_ignored(recorder):
    _install(_dependency_manager(recorder), _manifest(success_codes=3010))

    assert recorder.executors[0]["success_codes"] == [1638, 1641, 3010, 3011]


def test_failed_download_reports_the_reason(recorder):
    config, result = _install(
        _dependency_manager(recorder, download_ok=False), _manifest()
    )

    assert not result.ok
    assert "Failed to download setup.exe" in result.message
    assert recorder.executors == []
    assert config.Installed_Dependencies == []


def test_failed_prerequisite_stops_the_dependent_install(recorder):
    recorder.installer_result = Result(False, message="Command exited with status 67.")
    dependency_manager = _dependency_manager(recorder)
    manifests = {
        "main": {**_manifest(), "Dependencies": ["prerequisite"]},
        "prerequisite": _manifest(),
    }
    dependency_manager.get_dependency = lambda name: manifests[name]
    dependency_manager._DependencyManager__manager.supported_dependencies = manifests
    config = BottleConfig(Name="Bottle")

    result = dependency_manager.install(config, ["main", manifests["main"]])

    assert not result.ok
    assert len(recorder.executors) == 1
    assert config.Installed_Dependencies == []
