"""Core Manager tests"""

import contextlib

import pytest

from bottles.backend.managers import manager as manager_module
from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig
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
