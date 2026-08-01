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


def test_bwrap_input_devices_are_opt_in(monkeypatch):
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(
        "bottles.backend.managers.sandbox.os.path.isdir", lambda _: True
    )

    restricted = SandboxManager(share_input=False).get_cmd("true")
    shared = SandboxManager(share_input=True).get_cmd("true")

    assert "--tmpfs /dev/input" in restricted
    assert "--tmpfs /dev/input" not in shared


def test_input_devices_are_opt_in():
    assert BottleConfig().Sandbox.share_input is False

    result = BottleConfig._fill_with({"Sandbox": {"share_input": True}})

    assert result.status is True
    assert result.data.Sandbox.share_input is True


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
