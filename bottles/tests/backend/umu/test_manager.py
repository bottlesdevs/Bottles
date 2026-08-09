from pathlib import Path
from types import SimpleNamespace

from bottles.backend.managers import manager as manager_module
from bottles.backend.managers.manager import Manager
from bottles.backend.umu import UmuInstallation, UmuProviderError


def _manager(executor=None, installation=None):
    instance = object.__new__(Manager)
    instance.settings = SimpleNamespace(get_string=lambda _key: "")
    instance.umu_repository = SimpleNamespace(
        root=Path("/data/umu"),
        list_games=lambda: (),
    )
    instance.umu_executor = executor
    instance._umu_installation = installation
    instance._umu_probe_complete = installation is not None
    instance.umu_error = ""
    return instance


def test_refresh_keeps_running_executor_for_lifecycle_only(monkeypatch):
    current = UmuInstallation(Path("/old/umu-run"), "1.4.3", "system")
    updated = UmuInstallation(Path("/new/umu-run"), "1.4.4", "system")
    executor = SimpleNamespace(has_running_processes=lambda: True)
    manager = _manager(executor, current)
    provider = SimpleNamespace(resolve=lambda: updated)
    monkeypatch.setattr(manager_module, "UmuProvider", lambda **_kwargs: provider)

    assert manager.get_umu_installation(refresh=True) is None
    assert manager.umu_executor is executor
    assert manager.get_umu_executor() is None
    assert manager.get_umu_executor(for_launch=False) is executor


def test_failed_refresh_discards_idle_executor(monkeypatch):
    current = UmuInstallation(Path("/old/umu-run"), "1.4.3", "system")
    executor = SimpleNamespace(has_running_processes=lambda: False)
    manager = _manager(executor, current)

    class Provider:
        @staticmethod
        def resolve():
            raise UmuProviderError("missing")

    monkeypatch.setattr(manager_module, "UmuProvider", lambda **_kwargs: Provider())

    assert manager.get_umu_installation(refresh=True) is None
    assert manager.umu_executor is None
    assert manager.get_umu_executor(for_launch=False) is None
