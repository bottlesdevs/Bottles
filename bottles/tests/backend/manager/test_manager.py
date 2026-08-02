"""Core Manager tests"""

import contextlib
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from bottles.backend.managers import manager as manager_module
from bottles.backend.managers import steam as steam_module
from bottles.backend.managers.data import DataManager, UserDataKeys
from bottles.backend.managers.manager import Manager
from bottles.backend.managers.steam import SteamManager
from bottles.backend.models.config import BottleConfig, BottleParams
from bottles.backend.utils.connection import ConnectionUtils
from bottles.backend.utils.gsettings_stub import GSettingsStub
from bottles.backend.utils.manager import ManagerUtils


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


def test_check_runners_discovers_external_steam_proton(tmp_path, monkeypatch):
    runners = tmp_path / "runners"
    (runners / "soda-11.0").mkdir(parents=True)
    external = (
        tmp_path
        / ".local"
        / "share"
        / "Steam"
        / "compatibilitytools.d"
        / "GE-Proton10-4"
    )
    external.mkdir(parents=True)
    (external / "toolmanifest.vdf").write_text(
        '"manifest"\n{\n'
        '    "commandline" "/proton run"\n'
        '    "compatmanager_layer_name" "proton"\n'
        "}\n"
    )
    monkeypatch.setattr(manager_module.Paths, "runners", str(runners))
    monkeypatch.setattr(manager_module.shutil, "which", lambda _command: None)
    monkeypatch.setattr(ManagerUtils, "external_runner_paths", {})
    monkeypatch.setattr(steam_module, "STEAM_COMPATIBILITY_TOOL_PATHS", ())
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    manager = object.__new__(Manager)
    manager.steam_manager = SteamManager(check_only=True)

    assert manager.check_runners(install_latest=False)
    assert "GE-Proton10-4" in manager.runners_available
    assert manager.external_runners == {"GE-Proton10-4"}
    assert ManagerUtils.get_runner_path("GE-Proton10-4") == str(external)


def test_managed_runner_takes_precedence_over_steam_copy(tmp_path, monkeypatch):
    runners = tmp_path / "runners"
    managed = runners / "GE-Proton10-4"
    managed.mkdir(parents=True)
    external = tmp_path / "Steam" / "compatibilitytools.d" / "GE-Proton10-4"
    external.mkdir(parents=True)
    monkeypatch.setattr(manager_module.Paths, "runners", str(runners))
    monkeypatch.setattr(manager_module.shutil, "which", lambda _command: None)
    monkeypatch.setattr(ManagerUtils, "external_runner_paths", {})
    manager = object.__new__(Manager)
    manager.steam_manager = SimpleNamespace(
        list_compatibility_tools=lambda: {"GE-Proton10-4": str(external)}
    )

    assert manager.check_runners(install_latest=False)
    assert manager.external_runners == set()
    assert ManagerUtils.get_runner_path("GE-Proton10-4") == str(managed)


def test_manager_cli_checks_connection_when_online(mocker):
    check_connection = mocker.patch.object(
        ConnectionUtils,
        "check_connection",
        autospec=True,
        return_value=True,
    )

    Manager(is_cli=True)
    check_connection.assert_called_once()


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
    manager.steam_manager = SimpleNamespace(list_compatibility_tools=lambda: {})

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
    manager.steam_manager = SimpleNamespace(list_compatibility_tools=lambda: {})

    assert manager.check_runners(install_latest=False) is True
    assert manager.runners_available == []


def test_check_runners_adds_usable_system_wine(mocker):
    run = mocker.patch.object(manager_module.subprocess, "run")
    run.return_value.returncode = 0
    run.return_value.stdout = b"wine-11.0\n"
    mocker.patch.object(manager_module.shutil, "which", return_value="/app/bin/wine")
    mocker.patch.object(manager_module, "glob", return_value=[])
    manager = object.__new__(Manager)
    manager.steam_manager = SimpleNamespace(list_compatibility_tools=lambda: {})

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


@pytest.mark.parametrize(
    ("environment", "runners", "expected"),
    [
        ("Gaming", ["soda-11.0-1", "sys-wine-11.0"], "sys-wine-11.0"),
        ("Gaming", ["soda-11.0-1"], "sys-wine-10.20"),
        (
            "Gaming",
            ["soda-11.0-1", "sys-wine-11.0", "sys-wine-current"],
            "sys-wine-10.20",
        ),
        ("Steam", ["soda-11.0-1", "sys-wine-11.0"], "sys-wine-10.20"),
    ],
)
def test_check_bottles_updates_versioned_system_runner(
    mocker, monkeypatch, tmp_path, environment, runners, expected
):
    bottles_path = tmp_path / "bottles"
    bottle_path = bottles_path / "Test"
    bottle_path.mkdir(parents=True)
    config_path = bottle_path / "bottle.yml"
    BottleConfig(
        Name="Test",
        Path="Test",
        Runner="sys-wine-10.20",
        Environment=environment,
        session_arguments="--from-desktop",
        run_in_terminal=True,
    ).dump(str(config_path))

    manager = object.__new__(Manager)
    manager.runners_available = runners
    manager.settings = GSettingsStub()
    manager.is_cli = True
    manager.steam_manager = mocker.Mock(is_steam_supported=False)
    wineboot = mocker.patch.object(manager_module, "WineBoot")
    wineserver = mocker.patch.object(manager_module, "WineServer")
    apply_rules = mocker.patch.object(manager_module.RegistryRuleManager, "apply_rules")
    monkeypatch.setattr(manager_module.Paths, "bottles", str(bottles_path))

    manager.check_bottles(silent=True)

    assert manager.local_bottles["Test"].Runner == expected
    assert manager.local_bottles["Test"].session_arguments == ""
    assert manager.local_bottles["Test"].run_in_terminal is False
    persisted = BottleConfig.load(str(config_path)).data
    assert persisted.Runner == expected
    assert persisted.session_arguments == "--from-desktop"
    assert persisted.run_in_terminal is True
    wineboot.assert_not_called()
    wineserver.assert_not_called()
    apply_rules.assert_not_called()


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
                "hide_console": True,
                "file_extensions": [".txt", ".json"],
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
    assert program["hide_console"] is True
    assert program["file_extensions"] == [".txt", ".json"]


def test_create_bottle_checks_every_essential_component_before_retry():
    manager = object.__new__(Manager)
    manager.runners_available = []
    manager.dxvk_available = []
    manager.vkd3d_available = []
    manager.nvapi_available = ["nvapi"]
    manager.latencyflex_available = ["latencyflex"]
    calls = []

    def make_available(name, values):
        def check():
            calls.append(name)
            values.append(name)
            return True

        return check

    manager.check_runners = make_available("runner", manager.runners_available)
    manager.check_dxvk = make_available("dxvk", manager.dxvk_available)
    manager.check_vkd3d = make_available("vkd3d", manager.vkd3d_available)
    manager.organize_components = lambda: None
    cancelled = Event()
    cancelled.set()

    result = manager.create_bottle(
        name="Test",
        environment="application",
        cancel_event=cancelled,
    )

    assert not result.ok
    assert calls == ["runner", "dxvk", "vkd3d"]
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
