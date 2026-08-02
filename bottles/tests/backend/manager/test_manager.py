"""Core Manager tests"""

import contextlib

import pytest

from bottles.backend.managers import manager as manager_module
from bottles.backend.managers.data import DataManager, UserDataKeys
from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig, BottleParams
from bottles.backend.utils.connection import ConnectionUtils
from bottles.backend.utils.gsettings_stub import GSettingsStub


@pytest.fixture(autouse=True)
def reset_manager_singleton():
    existing = Manager._instances.pop(Manager, None)
    if existing and getattr(existing, "playtime_tracker", None):
        with contextlib.suppress(Exception):
            existing.playtime_tracker.shutdown()

    yield

    existing = Manager._instances.pop(Manager, None)
    if existing and getattr(existing, "playtime_tracker", None):
        with contextlib.suppress(Exception):
            existing.playtime_tracker.shutdown()


def test_manager_is_singleton():
    assert Manager(is_cli=True) is Manager(
        is_cli=True
    ), "Manager should be singleton object"
    assert Manager(is_cli=True) is Manager(
        g_settings=GSettingsStub(), is_cli=True
    ), "Manager should be singleton even with different argument"


def test_manager_default_gsettings_stub():
    assert Manager().settings.get_boolean("anything") is False


def test_manager_cli_skips_connection_check(mocker):
    check_connection = mocker.patch.object(
        ConnectionUtils,
        "check_connection",
        autospec=True,
        return_value=True,
    )

    Manager(is_cli=True)
    check_connection.assert_not_called()


def test_manager_forced_offline_setting_skips_connection_check(mocker):
    class ForcedOfflineSettings(GSettingsStub):
        @staticmethod
        def get_boolean(key: str) -> bool:
            if key == "force-offline":
                return True
            return GSettingsStub.get_boolean(key)

    class EmptyChecksResult:
        data = {}

    check_connection = mocker.patch.object(
        ConnectionUtils,
        "check_connection",
        autospec=True,
        return_value=True,
    )
    checks = mocker.patch.object(
        Manager,
        "checks",
        autospec=True,
        return_value=EmptyChecksResult(),
    )

    manager = Manager(g_settings=ForcedOfflineSettings(), is_cli=False)

    assert manager.utils_conn.force_offline is True
    check_connection.assert_not_called()
    checks.assert_called_once()


def test_check_runners_ignores_failed_system_wine(mocker):
    run = mocker.patch.object(manager_module.subprocess, "run")
    run.return_value.returncode = 126
    run.return_value.stdout = b""
    mocker.patch.object(manager_module.shutil, "which", return_value="/app/bin/wine")
    mocker.patch.object(manager_module, "glob", return_value=[])
    manager = object.__new__(Manager)

    assert manager.check_runners(install_latest=False) is True
    assert manager.runners_available == []


def test_check_runners_ignores_unexecutable_system_wine(mocker):
    mocker.patch.object(
        manager_module.subprocess,
        "run",
        side_effect=OSError(8, "Exec format error"),
    )
    mocker.patch.object(manager_module.shutil, "which", return_value="/app/bin/wine")
    mocker.patch.object(manager_module, "glob", return_value=[])
    manager = object.__new__(Manager)

    assert manager.check_runners(install_latest=False) is True
    assert manager.runners_available == []


def test_check_runners_adds_usable_system_wine(mocker):
    run = mocker.patch.object(manager_module.subprocess, "run")
    run.return_value.returncode = 0
    run.return_value.stdout = b"wine-11.0\n"
    mocker.patch.object(manager_module.shutil, "which", return_value="/app/bin/wine")
    mocker.patch.object(manager_module, "glob", return_value=[])
    manager = object.__new__(Manager)

    assert manager.check_runners(install_latest=False) is True
    assert manager.runners_available == ["sys-wine-11.0"]
    run.assert_called_once_with(
        ["/app/bin/wine", "--version"],
        stdout=manager_module.subprocess.PIPE,
        stderr=manager_module.subprocess.PIPE,
    )


def test_manager_rejects_file_as_custom_bottles_path(monkeypatch, tmp_path):
    custom_path = tmp_path / "custom-path"
    custom_path.write_text("")
    default_path = tmp_path / "bottles"

    for name in (
        "runners",
        "runtimes",
        "winebridge",
        "dxvk",
        "vkd3d",
        "nvapi",
        "templates",
        "temp",
        "latencyflex",
    ):
        monkeypatch.setattr(manager_module.Paths, name, str(tmp_path / name))
    monkeypatch.setattr(manager_module.Paths, "bottles", str(default_path))
    monkeypatch.setattr(
        DataManager,
        "get",
        lambda _self, key, default=None: (
            str(custom_path) if key == UserDataKeys.CustomBottlesPath else default
        ),
    )

    manager = Manager(check_connection=False, is_cli=True)
    manager.check_app_dirs()

    assert manager_module.Paths.bottles == str(default_path)
    assert default_path.is_dir()


def test_get_programs_preserves_per_program_runtime_options(monkeypatch):
    class Settings:
        @staticmethod
        def get_boolean(_key):
            return False

    class WindowsPath:
        @staticmethod
        def is_windows(_path):
            return False

    class WindowsSteam:
        is_steam_supported = False

    manager = object.__new__(Manager)
    manager._programs_cache = {}
    manager.settings = Settings()
    config = BottleConfig(
        Name="Test",
        External_Programs={
            "program-id": {
                "id": "program-id",
                "name": "Example",
                "executable": "example.exe",
                "path": "/games/example.exe",
                "environment": {"DXVK_HUD": "fps"},
                "arguments": "--safe-mode",
                "arguments_enabled": False,
                "discrete_gpu": True,
                "fsr": True,
                "gamemode": True,
                "latencyflex": False,
                "sync": "esync",
            }
        },
    )

    monkeypatch.setattr(manager_module, "glob", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(manager_module, "WinePath", lambda _config: WindowsPath())
    monkeypatch.setattr(
        manager_module.ManagerUtils, "get_bottle_path", lambda _config: "/bottle"
    )
    monkeypatch.setattr(
        manager_module, "SteamManager", lambda *_args, **_kwargs: WindowsSteam()
    )

    program = Manager.get_programs(manager, config)[0]

    assert program["environment"] == {"DXVK_HUD": "fps"}
    assert program["arguments"] == "--safe-mode"
    assert program["arguments_enabled"] is False
    assert program["discrete_gpu"] is True
    assert program["fsr"] is True
    assert program["gamemode"] is True
    assert program["latencyflex"] is False
    assert program["sync"] == "esync"


def test_component_updates_can_be_disabled(mocker):
    manager = object.__new__(Manager)
    manager._Manager__collect_runner_update = mocker.Mock()
    manager._Manager__collect_winebridge_update = mocker.Mock()
    config = BottleConfig(
        Parameters=BottleParams(show_component_updates=False),
    )

    assert Manager.get_component_updates(manager, config) == []
    manager._Manager__collect_runner_update.assert_not_called()
    manager._Manager__collect_winebridge_update.assert_not_called()


def test_component_update_checks_are_enabled_by_default():
    manager = object.__new__(Manager)
    manager.settings = GSettingsStub()
    manager.supported_wine_runners = {"soda-11.0-1": {}}
    manager.supported_proton_runners = {}
    config = BottleConfig(Runner="soda-10.0-1")

    assert config.Parameters.show_component_updates is True
    assert Manager.get_component_updates(manager, config) == [
        {
            "id": "runner",
            "title": "Runner",
            "current": "soda-10.0-1",
            "latest": "soda-11.0-1",
            "component_type": "runner",
        }
    ]


def test_custom_runner_is_not_compared_with_an_unrelated_family():
    manager = object.__new__(Manager)
    manager.settings = GSettingsStub()
    manager.supported_wine_runners = {"wine-ge-proton8-27-lol": {}}
    manager.supported_proton_runners = {}

    assert manager._Manager__latest_runner_for("wine-10.19-staging-tkg-amd64") == (
        None,
        "",
    )


def _make_update_manager(release_candidate: bool) -> Manager:
    class Settings:
        @staticmethod
        def get_boolean(key: str) -> bool:
            assert key == "release-candidate"
            return release_candidate

    manager = object.__new__(Manager)
    manager.settings = Settings()
    manager.supported_wine_runners = {}
    manager.supported_proton_runners = {}
    manager.supported_dxvk = {}
    manager.supported_vkd3d = {}
    manager.supported_nvapi = {}
    manager.supported_latencyflex = {}
    manager.supported_winebridge = {}
    manager.winebridge_available = []
    return manager


@pytest.mark.parametrize("prerelease_channel", ["rc", "unstable"])
@pytest.mark.parametrize(
    ("release_candidate", "expected"),
    [(False, "dxvk-2.7.1"), (True, "dxvk-3.0-1")],
)
def test_component_updates_respect_release_channel(
    prerelease_channel, release_candidate, expected
):
    manager = _make_update_manager(release_candidate)
    manager.supported_dxvk = {
        "dxvk-3.0-1": {"Channel": prerelease_channel},
        "dxvk-2.7.1": {"Channel": "stable"},
    }
    config = BottleConfig(DXVK="dxvk-2.6.2")
    config.Parameters.dxvk = True

    updates = Manager.get_component_updates(manager, config)

    assert {update["id"]: update["latest"] for update in updates} == {"dxvk": expected}


@pytest.mark.parametrize(
    ("release_candidate", "expected"),
    [(False, "soda-9.0-2"), (True, "soda-10.0-1")],
)
def test_runner_updates_respect_release_channel(release_candidate, expected):
    manager = _make_update_manager(release_candidate)
    manager.supported_wine_runners = {
        "soda-10.0-1": {"Channel": "unstable"},
        "soda-9.0-2": {"Channel": "stable"},
    }
    config = BottleConfig(Runner="soda-9.0-1")

    updates = Manager.get_component_updates(manager, config)

    assert {update["id"]: update["latest"] for update in updates} == {
        "runner": expected
    }


def test_get_programs_can_refresh_cached_results(monkeypatch):
    class Settings:
        @staticmethod
        def get_boolean(_key):
            return False

    class WindowsPath:
        @staticmethod
        def is_windows(_path):
            return False

    class WindowsSteam:
        is_steam_supported = False

    cached = [{"name": "Cached program"}]
    manager = object.__new__(Manager)
    manager._programs_cache = {"Test": cached}
    manager.settings = Settings()
    config = BottleConfig(Name="Test")

    monkeypatch.setattr(manager_module, "glob", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(manager_module, "WinePath", lambda _config: WindowsPath())
    monkeypatch.setattr(
        manager_module.ManagerUtils, "get_bottle_path", lambda _config: "/bottle"
    )
    monkeypatch.setattr(
        manager_module, "SteamManager", lambda *_args, **_kwargs: WindowsSteam()
    )

    assert Manager.get_programs(manager, config) is cached
    assert Manager.get_programs(manager, config, force_update=True) == []
