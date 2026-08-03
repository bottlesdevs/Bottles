"""Dedicated sandbox tests."""

import pytest

from bottles.backend.managers import sandbox as sandbox_module
from bottles.backend.managers.sandbox import SandboxManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.winecommand import WineCommand


@pytest.mark.parametrize(
    ("version", "devices", "supported"),
    [
        ("1.16.6", "all;", False),
        ("1.18.0", "all;", True),
        ("1.18.0", "dri;", False),
    ],
)
def test_flatpak_input_capability(monkeypatch, tmp_path, version, devices, supported):
    flatpak_info = tmp_path / "flatpak-info"
    flatpak_info.write_text(
        f"[Instance]\nflatpak-version={version}\n[Context]\ndevices={devices}\n"
    )
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(sandbox_module, "FLATPAK_INFO", str(flatpak_info))

    assert SandboxManager.supports_input_devices() is supported


@pytest.mark.parametrize(
    ("version", "devices", "supported"),
    [
        ("1.16.6", "all;", False),
        ("1.17.1", "all;", True),
        ("1.17.1", "usb;", True),
        ("1.18.0", "dri;", False),
    ],
)
def test_flatpak_usb_capability(monkeypatch, tmp_path, version, devices, supported):
    flatpak_info = tmp_path / "flatpak-info"
    flatpak_info.write_text(
        f"[Instance]\nflatpak-version={version}\n[Context]\ndevices={devices}\n"
    )
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(sandbox_module, "FLATPAK_INFO", str(flatpak_info))

    assert SandboxManager.supports_usb_devices() is supported


@pytest.mark.parametrize(
    ("version", "devices", "supported"),
    [
        ("1.16.6", "all;", False),
        ("1.17.1", "all;", True),
        ("1.17.1", "input;usb;", False),
    ],
)
def test_flatpak_hidraw_capability(monkeypatch, tmp_path, version, devices, supported):
    flatpak_info = tmp_path / "flatpak-info"
    flatpak_info.write_text(
        f"[Instance]\nflatpak-version={version}\n[Context]\ndevices={devices}\n"
    )
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(sandbox_module, "FLATPAK_INFO", str(flatpak_info))

    assert SandboxManager.supports_hidraw_devices() is supported


def test_flatpak_input_flag_requires_capability(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(
        SandboxManager,
        "supports_input_devices",
        staticmethod(lambda: False),
    )

    command = SandboxManager(share_input=True).get_cmd("true")

    assert "--sandbox-flag=32" not in command


def test_flatpak_input_flag_is_added_when_supported(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(
        SandboxManager,
        "supports_input_devices",
        staticmethod(lambda: True),
    )

    command = SandboxManager(share_input=True).get_cmd("true")

    assert "--sandbox-flag=32" in command


def test_flatpak_session_bus_is_shared_for_portal_access(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")

    command = SandboxManager().get_cmd("true")

    assert "--sandbox-flag=allow-dbus" in command


def test_flatpak_clear_environment_uses_env_command(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")

    command = SandboxManager(
        envs={"PATH": "/usr/bin", "VALUE": "with spaces"},
        clear_env=True,
    ).get_cmd("true")

    assert "--clear-env" not in command
    assert "env -i" in command
    assert "PATH=/usr/bin" in command
    assert "'VALUE=with spaces'" in command


def test_flatpak_clear_environment_quotes_variable_names(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")

    command = SandboxManager(
        envs={"VALUE; touch /tmp/not-run": "content"},
        clear_env=True,
    ).get_cmd("true")

    assert "'VALUE; touch /tmp/not-run=content'" in command


def test_flatpak_usb_flag_requires_capability(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(
        SandboxManager,
        "supports_usb_devices",
        staticmethod(lambda: False),
    )

    command = SandboxManager(share_usb=True).get_cmd("true")

    assert "--sandbox-flag=64" not in command


def test_flatpak_usb_flag_is_added_when_supported(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(
        SandboxManager,
        "supports_usb_devices",
        staticmethod(lambda: True),
    )

    command = SandboxManager(share_usb=True).get_cmd("true")

    assert "--sandbox-flag=64" in command


def test_flatpak_usb_flag_is_opt_in_when_supported(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(
        SandboxManager,
        "supports_usb_devices",
        staticmethod(lambda: True),
    )

    command = SandboxManager(share_usb=False).get_cmd("true")

    assert "--sandbox-flag=64" not in command


def test_flatpak_hidraw_flag_is_added_when_supported(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(
        SandboxManager,
        "supports_hidraw_devices",
        staticmethod(lambda: True),
    )

    command = SandboxManager(share_hidraw=True).get_cmd("true")

    assert "--sandbox-flag=512" in command


def test_flatpak_hidraw_flag_requires_capability(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(
        SandboxManager,
        "supports_hidraw_devices",
        staticmethod(lambda: False),
    )

    command = SandboxManager(share_hidraw=True).get_cmd("true")

    assert "--sandbox-flag=512" not in command


def test_bwrap_input_devices_are_opt_in(monkeypatch):
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(
        "bottles.backend.managers.sandbox.os.path.isdir", lambda _: True
    )

    restricted = SandboxManager(share_input=False).get_cmd("true")
    shared = SandboxManager(share_input=True).get_cmd("true")

    assert "--tmpfs /dev/input" in restricted
    assert "--tmpfs /dev/input" not in shared


def test_bwrap_usb_devices_are_opt_in(monkeypatch):
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(
        "bottles.backend.managers.sandbox.os.path.isdir", lambda _: True
    )

    restricted = SandboxManager(share_usb=False).get_cmd("true")
    shared = SandboxManager(share_usb=True).get_cmd("true")

    assert "--tmpfs /dev/bus/usb" in restricted
    assert "--tmpfs /dev/bus/usb" not in shared


def test_input_devices_are_opt_in():
    assert BottleConfig().Sandbox.share_input is False

    result = BottleConfig._fill_with({"Sandbox": {"share_input": True}})

    assert result.status is True
    assert result.data.Sandbox.share_input is True


def test_usb_devices_are_opt_in():
    assert BottleConfig().Sandbox.share_usb is False

    legacy = BottleConfig._fill_with({"Sandbox": {"share_input": True}})
    result = BottleConfig._fill_with({"Sandbox": {"share_usb": True}})

    assert legacy.status is True
    assert legacy.data.Sandbox.share_usb is False
    assert result.status is True
    assert result.data.Sandbox.share_usb is True


def test_wine_command_passes_input_permission(monkeypatch, tmp_path):
    command = object.__new__(WineCommand)
    command.config = BottleConfig(Name="Test", Path=str(tmp_path), Runner="sys-wine")
    command.config.Sandbox.share_input = True
    command.env = {}
    command.cwd = str(tmp_path)
    command.runner_runtime = None
    command.steam_runtime_root = None

    monkeypatch.setattr(ManagerUtils, "get_bottle_path", lambda _config: str(tmp_path))
    monkeypatch.setattr(ManagerUtils, "get_runner_path", lambda _runner: "sys-wine")

    sandbox = WineCommand._get_sandbox_manager(command)

    assert sandbox.share_input is True


def test_wine_command_passes_usb_permission(monkeypatch, tmp_path):
    command = object.__new__(WineCommand)
    command.config = BottleConfig(Name="Test", Path=str(tmp_path), Runner="sys-wine")
    command.config.Sandbox.share_usb = True
    command.env = {}
    command.cwd = str(tmp_path)
    command.runner_runtime = None
    command.steam_runtime_root = None

    monkeypatch.setattr(ManagerUtils, "get_bottle_path", lambda _config: str(tmp_path))
    monkeypatch.setattr(ManagerUtils, "get_runner_path", lambda _runner: "sys-wine")

    sandbox = WineCommand._get_sandbox_manager(command)

    assert sandbox.share_usb is True


def test_wine_command_coordinates_hidraw_sandbox_permissions(monkeypatch, tmp_path):
    command = object.__new__(WineCommand)
    command.config = BottleConfig(Name="Test", Path=str(tmp_path), Runner="sys-wine")
    command.config.Parameters.hidraw_devices = ["0x044F/0xB10A"]
    command.env = {}
    command.cwd = str(tmp_path)
    command.runner_runtime = None
    command.steam_runtime_root = None

    monkeypatch.setattr(ManagerUtils, "get_bottle_path", lambda _config: str(tmp_path))
    monkeypatch.setattr(ManagerUtils, "get_runner_path", lambda _runner: "sys-wine")

    sandbox = WineCommand._get_sandbox_manager(command)

    assert sandbox.share_input is True
    assert sandbox.share_usb is True
    assert sandbox.share_hidraw is True


def test_wine_command_rejects_invalid_hidraw_sandbox_permissions(monkeypatch, tmp_path):
    command = object.__new__(WineCommand)
    command.config = BottleConfig(Name="Test", Path=str(tmp_path), Runner="sys-wine")
    command.config.Parameters.hidraw_devices = ["1"]
    command.env = {}
    command.cwd = str(tmp_path)
    command.runner_runtime = None
    command.steam_runtime_root = None

    monkeypatch.setattr(ManagerUtils, "get_bottle_path", lambda _config: str(tmp_path))
    monkeypatch.setattr(ManagerUtils, "get_runner_path", lambda _runner: "sys-wine")

    sandbox = WineCommand._get_sandbox_manager(command)

    assert sandbox.share_input is False
    assert sandbox.share_usb is False
    assert sandbox.share_hidraw is False
