"""Unit tests for WineExecutor placeholder handling"""

import os
import shlex
from types import SimpleNamespace

import pytest

from bottles.backend.dlls.d7vk import D7VKComponent
from bottles.backend.dlls.dxvk import DXVKComponent
from bottles.backend.models.config import BottleConfig, BottleParams
from bottles.backend.models.result import Result
from bottles.backend.models.samples import Samples
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine import winecommand
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.winecommand import (
    WineCommand,
    WineEnv,
    apply_frame_rate_limit,
    apply_hidraw_preferences,
    apply_hdr_preferences,
    apply_wayland_preferences,
)


def _make_config(
    name: str = "TestBottle", path: str = "TestBottlePath"
) -> BottleConfig:
    return BottleConfig(Name=name, Path=path, Custom_Path="", Environment="Custom")


def test_build_placeholder_map_uses_program_values():
    config = _make_config()
    program = {
        "name": "My Game",
        "path": "/opt/games/my-game.exe",
    }

    placeholders = WineExecutor._build_placeholder_map(config, program)

    expected_bottle_path = ManagerUtils.get_bottle_path(config)
    assert placeholders["PROGRAM_NAME"] == "My Game"
    assert placeholders["PROGRAM_PATH"] == "/opt/games/my-game.exe"
    assert placeholders["PROGRAM_DIR"] == "/opt/games"
    assert placeholders["BOTTLE_NAME"] == "TestBottle"
    assert placeholders["BOTTLE_PATH"] == expected_bottle_path


def test_replace_placeholders_handles_unknown_tokens():
    placeholders = {"PROGRAM_NAME": "Example", "BOTTLE_NAME": "Bottle"}

    result = WineExecutor._replace_placeholders(
        "run-%PROGRAM_NAME%-on-%BOTTLE_NAME%-%UNKNOWN%",
        placeholders,
    )

    assert result == "run-Example-on-Bottle-%UNKNOWN%"


def test_run_program_substitutes_placeholders(monkeypatch):
    def fake_init(
        self,
        *,
        config,
        exec_path,
        args="",
        terminal=False,
        environment=None,
        move_file=False,
        move_upd_fn=None,
        pre_script=None,
        post_script=None,
        pre_script_args=None,
        post_script_args=None,
        cwd=None,
        monitoring=None,
        program_d7vk=None,
        program_dxvk=None,
        program_vkd3d=None,
        program_nvapi=None,
        program_gamescope=None,
        program_virt_desktop=None,
        program_winebridge=None,
        program_hide_console=False,
        sandbox_override=None,
    ):
        # mimic original __init__ contract enough for run() stub
        self.config = config
        self.use_winebridge = (
            program_winebridge
            if program_winebridge is not None
            else config.Parameters.winebridge
        )
        self.captured = {
            "config": config,
            "exec_path": exec_path,
            "args": args,
            "environment": environment,
            "pre_script": pre_script,
            "post_script": post_script,
            "pre_script_args": pre_script_args,
            "post_script_args": post_script_args,
            "cwd": cwd,
            "program_d7vk": program_d7vk,
            "program_dxvk": program_dxvk,
            "program_nvapi": program_nvapi,
            "program_hide_console": program_hide_console,
        }

    def fake_run(self):
        self.captured["use_winebridge"] = self.use_winebridge
        return Result(True, data=self.captured)

    monkeypatch.setattr(WineExecutor, "__init__", fake_init, raising=False)
    monkeypatch.setattr(WineExecutor, "run", fake_run, raising=False)

    config = _make_config(name="Bottle", path="BottlePath")
    config.Parameters.dxvk = True
    program = {
        "name": "Awesome Game",
        "path": "/games/awesome/game.exe",
        "arguments": "--title=%PROGRAM_NAME%",
        "pre_script": "/scripts/%BOTTLE_NAME%/%PROGRAM_NAME%.sh",
        "pre_script_args": "--prefix=%BOTTLE_PATH%",
        "post_script": None,
        "post_script_args": "--dir=%PROGRAM_DIR%",
        "folder": "%PROGRAM_DIR%",
        "environment": {
            "DXVK_HUD": "fps",
            "WINEDLLOVERRIDES": "version=n,b",
            "WINEARCH": "win32",
            "WINEPREFIX": "/tmp/other",
        },
        "dxvk": False,
        "dxvk_nvapi": True,
        "gamemode": True,
        "sync": "esync",
        "winebridge": True,
        "hide_console": True,
    }

    result = WineExecutor.run_program(config=config, program=program, terminal=False)

    assert result.status is True
    data = result.data
    assert data["exec_path"] == "/games/awesome/game.exe"
    assert data["args"] == "--title=Awesome Game"
    assert data["pre_script"] == "/scripts/Bottle/Awesome Game.sh"
    assert data["pre_script_args"] == f"--prefix={ManagerUtils.get_bottle_path(config)}"
    assert data["post_script_args"] == "--dir=/games/awesome"
    assert data["cwd"] == "/games/awesome"
    assert data["environment"] == {
        "DXVK_HUD": "fps",
        "WINEDLLOVERRIDES": "version=n,b",
    }
    assert data["program_dxvk"] is False
    assert data["program_nvapi"] is True
    assert data["program_hide_console"] is True
    assert data["config"] is not config
    assert data["config"].Parameters.dxvk is True
    assert data["config"].Parameters.dxvk_nvapi is False
    assert data["config"].Parameters.gamemode is True
    assert data["config"].Parameters.sync == "esync"
    assert data["use_winebridge"] is False
    assert config.Parameters.dxvk_nvapi is False
    assert config.Parameters.dxvk is True
    assert config.Parameters.gamemode is False
    assert config.Parameters.sync == "wine"


def test_run_program_creates_configured_backup_after_exit(monkeypatch):
    events = []

    def fake_init(self, **_kwargs):
        self.use_winebridge = True

    def fake_run(self):
        events.append("run")
        return Result(True, data={"use_winebridge": self.use_winebridge})

    monkeypatch.setattr(WineExecutor, "__init__", fake_init, raising=False)
    monkeypatch.setattr(
        WineExecutor,
        "run",
        fake_run,
        raising=False,
    )
    monkeypatch.setattr(
        "bottles.backend.managers.backup.BackupManager.create_program_backup",
        lambda _config, _program: events.append("backup") or Result(True),
    )
    config = _make_config()
    program = {
        "name": "Game",
        "path": "/games/game.exe",
        "automatic_backup": {
            "enabled": True,
            "destination": "/backups",
            "paths": ["/saves"],
        },
    }

    result = WineExecutor.run_program(config, program)

    assert result.status
    assert result.data["use_winebridge"] is False
    assert events == ["run", "backup"]


def test_run_program_preserves_custom_steam_app_id(monkeypatch):
    captured = {}

    def fake_init(self, **kwargs):
        captured.update(kwargs)
        self.use_winebridge = False

    monkeypatch.setattr(WineExecutor, "__init__", fake_init, raising=False)
    monkeypatch.setattr(
        WineExecutor,
        "run",
        lambda _self: Result(True),
        raising=False,
    )

    config = _make_config()
    config.Runner = "soda-11.0-3"
    WineExecutor.run_program(
        config=config,
        program={
            "id": "game-id",
            "name": "Game",
            "path": "/games/game.exe",
            "environment": {"SteamAppId": "123456"},
        },
    )

    assert captured["environment"]["SteamAppId"] == "123456"


@pytest.mark.parametrize("runner", ["soda-11.0-3", "dwproton-9-1", "wine-ge-8-26"])
def test_run_program_does_not_advertise_steam_to_proton_runners(monkeypatch, runner):
    captured = {}

    def fake_init(self, **kwargs):
        captured.update(kwargs)
        self.use_winebridge = True

    def fake_run(self):
        return Result(True, data={"use_winebridge": self.use_winebridge})

    monkeypatch.setattr(WineExecutor, "__init__", fake_init, raising=False)
    monkeypatch.setattr(WineExecutor, "run", fake_run, raising=False)

    config = _make_config()
    config.Runner = runner
    config.Parameters.use_steam_runtime = False
    program = {
        "id": "game-id",
        "name": "Game",
        "path": "/games/game.exe",
        "winebridge": True,
    }

    result = WineExecutor.run_program(config=config, program=program)

    assert "SteamAppId" not in captured["environment"]
    assert result.data["use_winebridge"] is True


def test_program_dxvk_false_adds_builtin_override(tmp_path):
    executable = tmp_path / "program.exe"
    executable.touch()
    config = _make_config()
    config.Parameters.dxvk = True

    executor = WineExecutor(
        config=config,
        exec_path=str(executable),
        program_dxvk=False,
    )

    assert executor.environment["WINEDLLOVERRIDES"] == (
        f"{DXVKComponent.get_override_keys()}=b"
    )


def test_program_d7vk_false_adds_builtin_override(tmp_path):
    executable = tmp_path / "program.exe"
    executable.touch()
    config = _make_config()
    config.Parameters.d7vk = True

    executor = WineExecutor(
        config=config,
        exec_path=str(executable),
        program_d7vk=False,
    )

    assert executor.environment["WINEDLLOVERRIDES"] == (
        f"{D7VKComponent.get_override_keys()}=b"
    )


def test_soda_adaptive_launch_prepares_a_profile(tmp_path, monkeypatch):
    executable = tmp_path / "program.exe"
    executable.touch()
    bottle = tmp_path / "bottle"
    config = _make_config(path=str(bottle))
    config.Custom_Path = str(bottle)
    config.Runner = "soda-11.0-5"
    config.Parameters.adaptive_launch = True
    prepared = {}

    class FakeProfile:
        def __init__(self, _config, path):
            prepared["executable"] = path
            self.path = tmp_path / "profile"

        def prepare(self):
            prepared["called"] = True
            return 3

    monkeypatch.setattr("bottles.backend.wine.executor.AdaptiveLaunchProfile", FakeProfile)

    executor = WineExecutor(config=config, exec_path=str(executable))

    assert prepared == {"executable": str(executable), "called": True}
    assert executor.environment["SODA_ADAPTIVE_PROFILE"] == str(tmp_path / "profile")


def test_adaptive_launch_is_ignored_by_other_runners(tmp_path, monkeypatch):
    executable = tmp_path / "program.exe"
    executable.touch()
    config = _make_config()
    config.Runner = "wine-ge-8-26"
    config.Parameters.adaptive_launch = True
    monkeypatch.setattr(
        "bottles.backend.wine.executor.AdaptiveLaunchProfile",
        lambda *_args: pytest.fail("profile should not be created"),
    )

    executor = WineExecutor(config=config, exec_path=str(executable))

    assert "SODA_ADAPTIVE_PROFILE" not in executor.environment


def test_winecommand_reports_nonzero_exit_status(monkeypatch):
    process = SimpleNamespace(
        returncode=7,
        communicate=lambda: (b"registry failed", None),
    )
    monkeypatch.setattr(
        winecommand.subprocess, "Popen", lambda *_args, **_kwargs: process
    )

    command = WineCommand.__new__(WineCommand)
    command.runner = "/usr/bin/wine"
    command.env = {}
    command.command = "wine reg import test.reg"
    command.config = _make_config()
    command.terminal = False
    command.sandbox_override = None
    command.communicate = True
    command.cwd = None

    result = command.run()

    assert not result.ok
    assert result.data == "registry failed"
    assert result.message == "Command exited with status 7."


def test_component_override_bypasses_winebridge(monkeypatch):
    def fake_init(self, **kwargs):
        self.use_winebridge = kwargs["program_winebridge"]

    def fake_run(self):
        return Result(True, data={"use_winebridge": self.use_winebridge})

    monkeypatch.setattr(WineExecutor, "__init__", fake_init, raising=False)
    monkeypatch.setattr(WineExecutor, "run", fake_run, raising=False)

    result = WineExecutor.run_program(
        config=_make_config(),
        program={
            "path": "/games/example.exe",
            "dxvk": False,
            "winebridge": True,
        },
    )

    assert result.data["use_winebridge"] is False


def test_hide_console_bypasses_winebridge(monkeypatch):
    def fake_init(self, **kwargs):
        self.use_winebridge = kwargs["program_winebridge"]

    def fake_run(self):
        return Result(True, data={"use_winebridge": self.use_winebridge})

    monkeypatch.setattr(WineExecutor, "__init__", fake_init, raising=False)
    monkeypatch.setattr(WineExecutor, "run", fake_run, raising=False)

    result = WineExecutor.run_program(
        config=_make_config(),
        program={
            "path": "/games/example.exe",
            "hide_console": True,
            "winebridge": True,
        },
    )

    assert result.data["use_winebridge"] is False


def test_hide_console_routes_exe_through_start(monkeypatch):
    calls = []

    class FakeWinePath:
        def __init__(self, _config):
            pass

        @staticmethod
        def is_unix(_path):
            return False

        @staticmethod
        def is_windows(_path):
            return False

    def fake_start(self, host_cwd=False):
        assert host_cwd is False
        calls.append("start")
        return Result(True)

    def fake_exe(self):
        calls.append("exe")
        return Result(True)

    monkeypatch.setattr("bottles.backend.wine.executor.WinePath", FakeWinePath)
    monkeypatch.setattr(
        WineExecutor,
        "_WineExecutor__launch_with_starter",
        fake_start,
    )
    monkeypatch.setattr(WineExecutor, "_WineExecutor__launch_exe", fake_exe)

    executor = WineExecutor.__new__(WineExecutor)
    executor.config = _make_config()
    executor.use_winebridge = False
    executor.use_virt_desktop = False
    executor.hide_console = True
    executor.exec_type = "exe"
    executor._raw_exec_path = r"C:\games\example.exe"
    executor.exec_path = "/games/example.exe"

    result = executor._WineExecutor__launch_with_bridge()

    assert result.status is True
    assert calls == ["start"]


def test_winebridge_preserves_terminal_launch(monkeypatch):
    captured = {}

    class FakeWineBridge:
        def __init__(self, _config):
            pass

        @staticmethod
        def is_available():
            return True

        @staticmethod
        def run_exe(exec_path, **kwargs):
            captured["exec_path"] = exec_path
            captured.update(kwargs)
            return Result(True)

    class FakeWinePath:
        def __init__(self, _config):
            pass

        @staticmethod
        def is_unix(_path):
            return False

    monkeypatch.setattr("bottles.backend.wine.executor.WineBridge", FakeWineBridge)
    monkeypatch.setattr("bottles.backend.wine.executor.WinePath", FakeWinePath)

    executor = WineExecutor.__new__(WineExecutor)
    executor.config = _make_config()
    executor.use_winebridge = True
    executor.exec_type = "exe"
    executor._raw_exec_path = r"C:\Games\example.exe"
    executor.terminal = True
    executor.environment = {"GAME_MODE": "1"}
    executor.cwd = r"C:\Games"
    executor.sandbox_override = "off"

    result = executor._WineExecutor__launch_with_bridge()

    assert result.status is True
    assert captured == {
        "exec_path": r"C:\Games\example.exe",
        "terminal": True,
        "environment": {"GAME_MODE": "1"},
        "cwd": r"C:\Games",
        "sandbox_override": "off",
    }


def test_hide_console_virtual_desktop_uses_background_explorer(monkeypatch):
    captured = {}

    class FakeExplorer:
        def __init__(self, _config):
            pass

        def launch_desktop(self, **kwargs):
            captured.update(kwargs)
            return Result(True, data="output")

    monkeypatch.setattr("bottles.backend.wine.executor.Explorer", FakeExplorer)

    executor = WineExecutor.__new__(WineExecutor)
    executor.config = _make_config()
    executor.config.Parameters.virtual_desktop_res = "1280x720"
    executor.exec_path = r"'C:\Program Files\Example\example.exe'"
    executor.args = "--safe-mode"
    executor.environment = {"DXVK_HUD": "fps"}
    executor.cwd = r"C:\Program Files\Example"
    executor.hide_console = True
    executor.sandbox_override = "off"
    executor.monitoring = []

    result = executor._WineExecutor__launch_with_explorer()

    assert result.status is True
    assert captured["background"] is True
    assert captured["sandbox_override"] == "off"


def test_virtual_desktop_converts_raw_unix_path_before_quoting(monkeypatch):
    captured = {}

    class FakeWinePath:
        def __init__(self, _config):
            pass

        @staticmethod
        def is_unix(path):
            captured["checked_path"] = path
            return True

        @staticmethod
        def to_windows(path, native=False, sandbox_override=None):
            captured["converted_path"] = path
            captured["native"] = native
            captured["sandbox_override"] = sandbox_override
            return r"Z:\tmp\Test App.exe"

    def fake_explorer(self):
        return Result(True, data={"exec_path": self.exec_path})

    monkeypatch.setattr("bottles.backend.wine.executor.WinePath", FakeWinePath)
    monkeypatch.setattr(
        WineExecutor,
        "_WineExecutor__launch_with_explorer",
        fake_explorer,
    )

    executor = WineExecutor.__new__(WineExecutor)
    executor.config = _make_config()
    executor.use_winebridge = False
    executor.use_virt_desktop = True
    executor.hide_console = True
    executor.exec_type = "exe"
    executor._raw_exec_path = "/tmp/Test App.exe"
    executor.exec_path = "'/tmp/Test App.exe'"
    executor.sandbox_override = "off"

    result = executor._WineExecutor__launch_with_bridge()

    assert result.status is True
    assert captured["checked_path"] == "/tmp/Test App.exe"
    assert captured["converted_path"] == "/tmp/Test App.exe"
    assert captured["native"] is False
    assert captured["sandbox_override"] == "off"
    assert result.data["exec_path"] == r"'Z:\tmp\Test App.exe'"


def test_windows_executable_cwd_uses_its_parent(monkeypatch):
    captured = {}

    class FakeWinePath:
        def __init__(self, _config):
            pass

        @staticmethod
        def is_windows(path):
            return ":" in path

        @staticmethod
        def to_unix(path, native=False):
            captured["windows_parent"] = path
            captured["native"] = native
            return "/prefix/drive_c/Program Files/Example"

    monkeypatch.setattr("bottles.backend.wine.executor.WinePath", FakeWinePath)

    executor = WineExecutor(
        config=_make_config(),
        exec_path=r"C:\Program Files\Example\example.exe",
    )

    assert captured["windows_parent"] == r"C:\Program Files\Example"
    assert captured["native"] is True
    assert executor.cwd == "/prefix/drive_c/Program Files/Example"


def test_winebridge_launch_preserves_spaces_in_executable_path(monkeypatch):
    executable = "/mnt/storage/DO NOT RENAME OR MOVE/Games/Poly Bridge 2.exe"
    captured = {}

    class FakeWineBridge:
        def __init__(self, _config):
            pass

        @staticmethod
        def is_available():
            return True

        @staticmethod
        def run_exe(exec_path, **kwargs):
            captured["exec_path"] = exec_path
            captured.update(kwargs)
            return ""

    class FakeWinePath:
        def __init__(self, _config):
            pass

        @staticmethod
        def is_unix(exec_path):
            return exec_path.startswith("/")

        @staticmethod
        def to_windows(exec_path, native=False):
            assert native is True
            return exec_path.replace("/", "\\")

    monkeypatch.setattr("bottles.backend.wine.executor.WineBridge", FakeWineBridge)
    monkeypatch.setattr("bottles.backend.wine.executor.WinePath", FakeWinePath)
    monkeypatch.setattr(
        "bottles.backend.wine.executor.ManagerUtils.get_bottle_path",
        lambda _config: "/mnt/storage/DO NOT RENAME OR MOVE",
    )

    executor = WineExecutor.__new__(WineExecutor)
    executor.config = _make_config()
    executor.use_winebridge = True
    executor.exec_type = "exe"
    executor._raw_exec_path = executable
    executor.exec_path = f"'{executable}'"
    executor.terminal = False
    executor.environment = {}
    executor.cwd = None
    executor.sandbox_override = None

    result = executor._WineExecutor__launch_with_bridge()

    assert result.status is True
    assert captured["exec_path"] == executable.replace("/", "\\")
    assert captured["terminal"] is False


def test_external_executable_uses_wine_start(monkeypatch):
    executable = "/games/KeePass Portable/KeePass.exe"
    captured = {}

    class FakeWineBridge:
        def __init__(self, _config):
            pass

        @staticmethod
        def is_available():
            return True

    class FakeWinePath:
        def __init__(self, _config):
            pass

        @staticmethod
        def is_unix(path):
            return path.startswith("/")

        @staticmethod
        def is_windows(_path):
            return False

    monkeypatch.setattr("bottles.backend.wine.executor.WineBridge", FakeWineBridge)
    monkeypatch.setattr("bottles.backend.wine.executor.WinePath", FakeWinePath)
    monkeypatch.setattr(
        "bottles.backend.wine.executor.ManagerUtils.get_bottle_path",
        lambda _config: "/prefix",
    )
    monkeypatch.setattr(
        "bottles.backend.wine.executor.Start.run",
        lambda _self, **kwargs: captured.update(kwargs) or Result(True),
    )
    monkeypatch.setattr(
        WineExecutor,
        "_WineExecutor__set_monitors",
        lambda _self: None,
    )

    executor = WineExecutor.__new__(WineExecutor)
    executor.config = _make_config()
    executor.use_winebridge = True
    executor.use_virt_desktop = False
    executor.hide_console = False
    executor.exec_type = "exe"
    executor._raw_exec_path = executable
    executor.exec_path = shlex.quote(executable)
    executor.terminal = False
    executor.args = "--test"
    executor.environment = {"WINEDEBUG": "+seh"}
    executor.pre_script = None
    executor.post_script = None
    executor.pre_script_args = None
    executor.post_script_args = None
    executor.cwd = "/games/KeePass Portable"
    executor.sandbox_override = None

    result = executor._WineExecutor__launch_with_bridge()

    assert result.status is True
    assert captured["file"] == shlex.quote(executable)
    assert captured["cwd"] == "/games/KeePass Portable"
    assert captured["args"] == "--test"
    assert captured["environment"] == {"WINEDEBUG": "+seh"}
    assert captured["host_cwd"] is True


def test_wine_env_respects_allowed_keys(monkeypatch):
    monkeypatch.setenv("KEEP_ONLY", "1")
    monkeypatch.setenv("DROP_ME", "2")

    env = WineEnv(clean=False, allowed_keys=["KEEP_ONLY"])
    resolved = env.get()["envs"]

    assert resolved["KEEP_ONLY"] == "1"
    assert "DROP_ME" not in resolved


def test_default_wine_environment_inherits_xmodifiers(monkeypatch):
    monkeypatch.setenv("XMODIFIERS", "@im=fcitx")

    env = WineEnv(allowed_keys=Samples.default_inherited_environment)

    assert env.get()["envs"]["XMODIFIERS"] == "@im=fcitx"


@pytest.mark.parametrize(
    ("sync", "ntsync_available", "expected"),
    [
        ("wine", True, {"WINENTSYNC": "1"}),
        ("wine", False, {}),
        ("ntsync", True, {"WINENTSYNC": "1"}),
        ("ntsync", False, {"WINEFSYNC": "1"}),
        ("esync", False, {"WINEESYNC": "1"}),
        ("fsync", False, {"WINEFSYNC": "1"}),
    ],
)
def test_winecommand_applies_selected_sync_environment(
    monkeypatch, sync, ntsync_available, expected
):
    monkeypatch.setattr(
        winecommand,
        "is_ntsync_available",
        lambda _runner: ntsync_available,
    )
    env = WineEnv(clean=True)

    WineCommand._apply_sync_environment(env, sync, "/runner/bin/wine")

    assert env.get()["envs"] == expected


def test_frame_rate_limit_applies_to_dxvk_and_vkd3d():
    env = WineEnv(clean=True)
    env.add("DXVK_CONFIG", "dxgi.syncInterval = 0")

    apply_frame_rate_limit(env, BottleParams(frame_rate_limit=120))

    resolved = env.get()["envs"]
    assert resolved["DXVK_CONFIG"] == (
        "dxgi.syncInterval = 0; dxgi.maxFrameRate = 120; "
        "d3d9.maxFrameRate = 120"
    )
    assert resolved["VKD3D_FRAME_RATE"] == "120"


def test_frame_rate_limit_preserves_manual_environment_when_disabled():
    env = WineEnv(clean=True)
    env.add("DXVK_CONFIG", "dxgi.maxFrameRate = 90")
    env.add("VKD3D_FRAME_RATE", "90")

    apply_frame_rate_limit(env, BottleParams())

    resolved = env.get()["envs"]
    assert resolved["DXVK_CONFIG"] == "dxgi.maxFrameRate = 90"
    assert resolved["VKD3D_FRAME_RATE"] == "90"


def test_hidraw_preferences_enable_only_selected_devices():
    env = WineEnv(clean=True)
    params = BottleParams(
        hidraw_devices=["0x044f/0xb10a", "1", "0x231D/0x0200"]
    )

    apply_hidraw_preferences(env, params)

    assert env.get()["envs"]["PROTON_ENABLE_HIDRAW"] == (
        "0x044F/0xB10A,0x231D/0x0200"
    )


def test_hidraw_preferences_preserve_manual_environment_when_unset():
    env = WineEnv(clean=True)
    env.add("PROTON_ENABLE_HIDRAW", "0x3344/0x0001")

    apply_hidraw_preferences(env, BottleParams())

    assert env.get()["envs"]["PROTON_ENABLE_HIDRAW"] == "0x3344/0x0001"


def test_hdr_preferences_enable_dxvk_without_automatic_wayland_layer(monkeypatch):
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.DisplayUtils.display_server_type",
        lambda: "wayland",
    )
    env = WineEnv(clean=True)
    env.add("WAYLAND_DISPLAY", "wayland-0")
    params = BottleParams(hdr=True, wayland=True)

    apply_hdr_preferences(env, params, gamescope_activated=False)

    resolved = env.get()["envs"]
    assert resolved["DXVK_HDR"] == "1"
    assert "ENABLE_HDR_WSI" not in resolved


def test_hdr_preferences_do_not_enable_wayland_layer_for_gamescope():
    env = WineEnv(clean=True)
    env.add("ENABLE_HDR_WSI", "1")
    env.add("DISABLE_GAMESCOPE_WSI", "1")
    params = BottleParams(hdr=True, wayland=True)

    apply_hdr_preferences(env, params, gamescope_activated=True)

    resolved = env.get()["envs"]
    assert resolved["DXVK_HDR"] == "1"
    assert resolved["ENABLE_GAMESCOPE_WSI"] == "1"
    assert "ENABLE_HDR_WSI" not in resolved
    assert "DISABLE_GAMESCOPE_WSI" not in resolved


def test_gamescope_removes_hdr_wsi_when_hdr_is_disabled():
    env = WineEnv(clean=True)
    env.add("ENABLE_HDR_WSI", "1")

    apply_hdr_preferences(env, BottleParams(), gamescope_activated=True)

    assert "ENABLE_HDR_WSI" not in env.get()["envs"]


def test_hdr_preferences_require_native_wayland_for_hdr():
    env = WineEnv(clean=True)
    params = BottleParams(hdr=True, wayland=False)

    apply_hdr_preferences(env, params, gamescope_activated=False)

    resolved = env.get()["envs"]
    assert "DXVK_HDR" not in resolved
    assert "ENABLE_HDR_WSI" not in resolved


def test_hdr_preferences_preserve_manual_environment_when_disabled():
    env = WineEnv(clean=True)
    env.add("DXVK_HDR", "1")
    env.add("ENABLE_HDR_WSI", "1")

    apply_hdr_preferences(env, BottleParams(), gamescope_activated=False)

    resolved = env.get()["envs"]
    assert resolved["DXVK_HDR"] == "1"
    assert resolved["ENABLE_HDR_WSI"] == "1"


def test_proton_hdr_and_wayland_options_are_translated(monkeypatch):
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.DisplayUtils.display_server_type",
        lambda: "wayland",
    )
    env = WineEnv(clean=True)
    env.add("DISPLAY", ":1")
    env.add("WAYLAND_DISPLAY", "wayland-0")
    env.add("PROTON_ENABLE_HDR", "1")
    env.add("PROTON_ENABLE_WAYLAND", "1")
    env.add("PROTON_WAYLAND_MONITOR", "DP-1")
    env.add("WINEDLLOVERRIDES", "version=n")
    env.add("SteamVirtualGamepadInfo", "device")
    env.add("SDL_GAMECONTROLLER_IGNORE_DEVICES", "device")
    env.add("SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD", "1")
    params = BottleParams()

    apply_wayland_preferences(env, params, "/runner/share/X11/locale")
    apply_hdr_preferences(env, params, gamescope_activated=False)

    resolved = env.get()["envs"]
    assert "DISPLAY" not in resolved
    assert resolved["DXVK_HDR"] == "1"
    assert "ENABLE_HDR_WSI" not in resolved
    assert resolved["WINEDLLOVERRIDES"] == ("version=n;winex11.drv=d;winewayland.drv=b")
    assert resolved["WINE_USE_EGL"] == "1"
    assert resolved["WINE_DISABLE_FULLSCREEN_HACK"] == "1"
    assert resolved["WINE_MOVE_HACK"] == "1"
    assert resolved["PROTON_USE_XALIA"] == "0"
    assert resolved["PROTON_NO_STEAMINPUT"] == "1"
    assert resolved["WAYLANDDRV_PRIMARY_MONITOR"] == "DP-1"
    assert resolved["XLOCALEDIR"] == "/runner/share/X11/locale"
    assert "SteamVirtualGamepadInfo" not in resolved
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in resolved
    assert "SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD" not in resolved


def test_disabled_proton_options_are_not_translated(monkeypatch):
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.DisplayUtils.display_server_type",
        lambda: "wayland",
    )
    env = WineEnv(clean=True)
    env.add("DISPLAY", ":1")
    env.add("WAYLAND_DISPLAY", "wayland-0")
    env.add("PROTON_ENABLE_HDR", "1")
    env.add("PROTON_USE_HDR", "0")
    env.add("PROTON_ENABLE_WAYLAND", "1")
    env.add("PROTON_USE_WAYLAND", "0")
    params = BottleParams()

    apply_wayland_preferences(env, params)
    apply_hdr_preferences(env, params, gamescope_activated=False)

    resolved = env.get()["envs"]
    assert resolved["DISPLAY"] == ":1"
    assert "DXVK_HDR" not in resolved
    assert "ENABLE_HDR_WSI" not in resolved


def test_winecommand_filters_host_environment(monkeypatch, tmp_path):
    bottle_path = tmp_path / "TestBottle"
    bottle_path.mkdir()
    runner_path = tmp_path / "runner"
    for sub in [
        "lib",
        "lib64",
        "lib/wine/x86_64-unix",
        "lib32/wine/x86_64-unix",
        "lib32",
        "lib64/wine/x86_64-unix",
        "lib/wine/i386-unix",
        "lib32/wine/i386-unix",
        "lib64/wine/i386-unix",
    ]:
        (runner_path / sub).mkdir(parents=True, exist_ok=True)

    config = BottleConfig(Name="Test", Path=str(bottle_path), Runner="test")
    params = BottleParams()
    params.use_runtime = False
    params.use_eac_runtime = False
    params.use_be_runtime = False
    params.hdr = True
    config.Parameters = params
    config.Limit_System_Environment = True
    config.Inherited_Environment_Variables = ["DISPLAY"]

    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setenv("SHOULD_NOT_PASS", "secret")

    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.get_runner_path",
        lambda _runner: str(runner_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.SteamUtils.is_proton", lambda *_: False
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.DisplayUtils.check_nvidia_device",
        lambda: None,
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.DisplayUtils.display_server_type",
        lambda: "x11",
    )

    def _fake_gpu(self):
        return {
            "prime": {
                "discrete": None,
                "integrated": {"icd": "/tmp/icd", "envs": {}},
            },
            "vendors": {"generic": {"icd": "/tmp/icd", "envs": {}}},
        }

    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.GPUUtils.get_gpu",
        _fake_gpu,
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.RuntimeManager.get_runtime_env",
        lambda *_: [],
    )

    winecmd = WineCommand.__new__(WineCommand)
    winecmd.config = config
    winecmd.minimal = True
    winecmd.arguments = ""
    winecmd.runner = "/usr/bin/wine"
    winecmd.runner_runtime = ""
    winecmd.gamescope_activated = False
    winecmd.terminal = False

    env = winecmd.get_env()
    assert env["DISPLAY"] == ":1"
    assert "DXVK_HDR" not in env
    assert "SHOULD_NOT_PASS" not in env


def test_winecommand_syncs_proton_vkd3d(monkeypatch, tmp_path):
    bottle_path = tmp_path / "TestBottle"
    bottle_path.mkdir()
    proton_path = tmp_path / "GE-Proton"
    dist_path = proton_path / "files"
    for sub in [
        "share/default_pfx/drive_c/windows/system32",
        "share/default_pfx/drive_c/windows/syswow64",
    ]:
        (dist_path / sub).mkdir(parents=True, exist_ok=True)
    for dll in ["libvkd3d-1.dll", "libvkd3d-shader-1.dll"]:
        (dist_path / "share/default_pfx/drive_c/windows/system32" / dll).write_bytes(
            b"win64"
        )
        (dist_path / "share/default_pfx/drive_c/windows/syswow64" / dll).write_bytes(
            b"win32"
        )
    stale_dll = bottle_path / "drive_c/windows/system32/libvkd3d-1.dll"
    stale_dll.parent.mkdir(parents=True)
    stale_dll.write_bytes(b"stale")

    config = BottleConfig(Name="Test", Path=str(bottle_path), Runner="GE-Proton")
    config.Parameters = BottleParams()
    config.Parameters.use_runtime = False
    config.Parameters.use_eac_runtime = False
    config.Parameters.use_be_runtime = False
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.get_runner_path",
        lambda _runner: str(proton_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.SteamUtils.is_proton", lambda *_: True
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.SteamUtils.get_dist_directory",
        lambda _runner: str(dist_path),
    )
    prepared = {}

    def _prepare_fsr4(path, prefix, env, sandbox):
        prepared.update({"path": path, "prefix": prefix, "sandbox": sandbox})
        env["FSR4_UPGRADE"] = "1"
        return True

    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.SteamUtils.prepare_proton_fsr4",
        _prepare_fsr4,
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.DisplayUtils.check_nvidia_device",
        lambda: None,
    )

    def _fake_gpu(self):
        return {
            "prime": {"discrete": None, "integrated": None},
            "vendors": {},
        }

    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.GPUUtils.get_gpu",
        _fake_gpu,
    )

    winecmd = WineCommand.__new__(WineCommand)
    winecmd.config = config
    winecmd.minimal = True
    winecmd.runner = str(dist_path / "bin/wine")
    winecmd.runner_runtime = "sniper"
    winecmd.gamescope_activated = False
    winecmd.terminal = False

    winecmd.get_env(return_clean_env=True)

    for dll in ["libvkd3d-1.dll", "libvkd3d-shader-1.dll"]:
        assert (bottle_path / "drive_c/windows/system32" / dll).read_bytes() == b"win64"
        assert (bottle_path / "drive_c/windows/syswow64" / dll).read_bytes() == b"win32"
    assert prepared == {}

    config.Environment_Variables = {"PROTON_FSR4_UPGRADE": "1"}
    winecmd.minimal = False
    env = winecmd.get_env()

    assert prepared == {
        "path": str(proton_path),
        "prefix": str(bottle_path),
        "sandbox": None,
    }
    assert env["FSR4_UPGRADE"] == "1"

    prepared.clear()
    config.Parameters.sandbox = True
    env = winecmd.get_env()

    sandbox = prepared.pop("sandbox")
    assert prepared == {"path": str(proton_path), "prefix": str(bottle_path)}
    assert sandbox.chdir == str(bottle_path)
    assert sandbox.clear_env is True
    assert sandbox.share_paths_ro == [str(proton_path)]
    assert sandbox.share_paths_rw == [str(bottle_path)]
    assert sandbox.share_net is False
    assert env["FSR4_UPGRADE"] == "1"


def test_wayland_sandbox_clears_parent_display(monkeypatch, tmp_path):
    bottle_path = tmp_path / "TestBottle"
    bottle_path.mkdir()
    config = BottleConfig(Name="Test", Path=str(bottle_path), Runner="sys-wine")

    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.get_runner_path",
        lambda _runner: "sys-wine",
    )

    winecmd = WineCommand.__new__(WineCommand)
    winecmd.config = config
    winecmd.env = {"WAYLAND_DISPLAY": "wayland-0"}
    winecmd.cwd = str(bottle_path)
    winecmd.runner_runtime = ""
    winecmd.steam_runtime_root = None

    command = winecmd._get_sandbox_manager().get_cmd("wine")

    assert "--clear-env" not in command
    assert "env -i" in command
    assert "WAYLAND_DISPLAY=wayland-0" in command
    assert not any(token.startswith("DISPLAY=") for token in shlex.split(command))

    monkeypatch.delenv("FLATPAK_ID")
    command = winecmd._get_sandbox_manager().get_cmd("wine")

    assert command.index("--clearenv") < command.index(
        "--setenv WAYLAND_DISPLAY wayland-0"
    )


@pytest.mark.parametrize("use_steam_runtime", [False, True])
def test_dedicated_sandbox_uses_selected_runtime_path(
    monkeypatch, tmp_path, use_steam_runtime
):
    bottle_path = tmp_path / "TestBottle"
    bottle_path.mkdir()
    runner_path = tmp_path / "ge-proton"
    runner_path.mkdir()
    runtime_path = tmp_path / "SteamLinuxRuntime_sniper"
    runtime_path.mkdir()
    entry_point = runtime_path / "_v2-entry-point"
    entry_point.touch()

    config = BottleConfig(
        Name="Test",
        Path=str(bottle_path),
        Runner="ge-proton",
        Environment="Custom",
    )
    config.Parameters.use_steam_runtime = use_steam_runtime

    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.get_runner_path",
        lambda _runner: str(runner_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.resolve_portal_path",
        lambda path: path,
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.RuntimeManager.get_runtimes",
        lambda _category: {
            "sniper": {
                "name": "sniper",
                "entry_point": str(entry_point),
            }
        },
    )

    winecmd = WineCommand.__new__(WineCommand)
    winecmd.config = config
    winecmd.minimal = True
    winecmd.arguments = ""
    winecmd.runner = str(runner_path / "files/bin/wine")
    winecmd.runner_runtime = "sniper"
    winecmd.gamescope_activated = False
    winecmd.cwd = str(bottle_path)
    winecmd.env = {}

    command = winecmd.get_cmd("cmd")
    sandbox = winecmd._get_sandbox_manager()

    invalid_runtime_path = os.path.realpath("sniper")
    assert invalid_runtime_path not in sandbox.share_paths_ro
    assert (str(runtime_path) in sandbox.share_paths_ro) is use_steam_runtime
    assert (str(entry_point) in command) is use_steam_runtime


@pytest.mark.parametrize(
    ("parameter", "wrapper"),
    (("gamemode", "/usr/bin/gamemoderun"), ("mangohud", "/usr/bin/mangohud")),
)
def test_host_wrappers_run_outside_steam_runtime(
    monkeypatch, tmp_path, parameter, wrapper
):
    runtime_path = tmp_path / "SteamLinuxRuntime_sniper"
    runtime_path.mkdir()
    entry_point = runtime_path / "_v2-entry-point"
    entry_point.touch()
    config = BottleConfig(Name="Test", Runner="ge-proton")
    config.Parameters.use_steam_runtime = True
    setattr(config.Parameters, parameter, True)

    monkeypatch.setattr(winecommand, "gamemode_available", "/usr/bin/gamemoderun")
    monkeypatch.setattr(winecommand, "mangohud_available", "/usr/bin/mangohud")
    monkeypatch.setattr(winecommand, "gamescope_available", False)
    monkeypatch.setattr(winecommand, "obs_vkc_available", False)
    monkeypatch.setattr(
        winecommand.RuntimeManager,
        "get_runtimes",
        lambda _category: {
            "sniper": {"name": "sniper", "entry_point": str(entry_point)}
        },
    )

    winecmd = WineCommand.__new__(WineCommand)
    winecmd.config = config
    winecmd.minimal = False
    winecmd.arguments = ""
    winecmd.runner = "/runner/files/bin/wine"
    winecmd.runner_runtime = "sniper"
    winecmd.gamescope_activated = False

    command = winecmd.get_cmd("game.exe")

    assert command.index(wrapper) < command.index(str(entry_point))
    assert command.index(str(entry_point)) < command.index(winecmd.runner)


@pytest.mark.parametrize(
    ("runtime", "entry_point", "separator"),
    (
        ("sniper", "_v2-entry-point", " -- "),
        ("scout", "run.sh", " "),
    ),
)
def test_steam_runtime_uses_supported_command_separator(
    monkeypatch, tmp_path, runtime, entry_point, separator
):
    runtime_path = tmp_path / runtime
    runtime_path.mkdir()
    entry_point = runtime_path / entry_point
    entry_point.touch()
    config = BottleConfig(Name="Test", Runner="wine")
    config.Parameters.use_steam_runtime = True

    monkeypatch.setattr(
        winecommand.RuntimeManager,
        "get_runtimes",
        lambda _category: {
            runtime: {"name": runtime, "entry_point": str(entry_point)}
        },
    )

    winecmd = WineCommand.__new__(WineCommand)
    winecmd.config = config
    winecmd.minimal = True
    winecmd.arguments = ""
    winecmd.runner = "/runner/bin/wine"
    winecmd.runner_runtime = runtime
    winecmd.gamescope_activated = False

    command = winecmd.get_cmd("game.exe")

    assert command == f"{entry_point}{separator}{winecmd.runner} game.exe"


def test_dedicated_sandbox_shares_forwarded_document_read_write(monkeypatch, tmp_path):
    bottle_path = tmp_path / "TestBottle"
    bottle_path.mkdir()
    document = "/run/user/1000/doc/abc123/My Document.txt"
    command_document = "/run/user/1000/doc/def456/Batch Document.txt"
    other_path = "/home/user/Other Document.txt"
    config = BottleConfig(Name="Test", Path=str(bottle_path), Runner="sys-wine")

    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.get_runner_path",
        lambda _runner: "sys-wine",
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.resolve_portal_path",
        lambda path: path,
    )
    monkeypatch.setattr(
        "bottles.backend.wine.winecommand.ManagerUtils.is_portal_document_path",
        lambda path: path in (document, command_document),
    )

    winecmd = WineCommand.__new__(WineCommand)
    winecmd.config = config
    winecmd.arguments = " ".join(shlex.quote(arg) for arg in (document, other_path))
    winecmd.command = "cmd /c {} {}".format(
        shlex.quote("C:\\probe.bat"),
        shlex.quote(command_document),
    )
    winecmd.cwd = str(bottle_path)
    winecmd.runner_runtime = ""
    winecmd.steam_runtime_root = None
    winecmd.env = {}

    sandbox = winecmd._get_sandbox_manager()

    assert document in sandbox.share_paths_rw
    assert command_document in sandbox.share_paths_rw
    assert other_path not in sandbox.share_paths_rw
