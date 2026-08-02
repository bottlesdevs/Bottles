"""Unit tests for ManagerUtils."""

import shlex

import pytest

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils import manager
from bottles.backend.utils.manager import ManagerUtils


class DynamicLauncherPortal:
    def __init__(self):
        self.desktop_entry = None

    def dynamic_launcher_prepare_install(self, *args):
        args[-1](None, object())

    @staticmethod
    def dynamic_launcher_prepare_install_finish(_result):
        return {"token": "test-token"}

    def dynamic_launcher_install(self, _token, _launcher_id, desktop_entry):
        self.desktop_entry = desktop_entry


@pytest.mark.parametrize(
    ("flatpak_id", "expected_prefix"),
    [
        (None, ["bottles-cli"]),
        (
            "com.usebottles.bottles",
            [
                "flatpak",
                "run",
                "--command=bottles-cli",
                "com.usebottles.bottles",
            ],
        ),
    ],
)
def test_desktop_entry_uses_host_launch_command(
    tmp_path, monkeypatch, flatpak_id, expected_prefix
):
    portal = DynamicLauncherPortal()
    icon = tmp_path / "icon.svg"
    icon.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    if flatpak_id:
        monkeypatch.setenv("FLATPAK_ID", flatpak_id)
    else:
        monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(manager, "portal", portal)
    monkeypatch.setattr(manager.SignalManager, "send", lambda *_args: None)

    ManagerUtils.create_desktop_entry(
        BottleConfig(Name="Hero's bottle"),
        {
            "name": "Alice's Game",
            "executable": "game.exe",
            "path": "/bottle/game.exe",
        },
        custom_icon=str(icon),
    )

    exec_line = next(
        line.strip().removeprefix("Exec=")
        for line in portal.desktop_entry.splitlines()
        if line.strip().startswith("Exec=")
    )
    assert shlex.split(exec_line) == expected_prefix + [
        "run",
        "-p",
        "Alice's Game",
        "-b",
        "Hero's bottle",
        "--",
        "%u",
    ]


def test_desktop_entry_id_matches_dynamic_launcher_format(monkeypatch):
    monkeypatch.setattr(manager, "APP_ID", "com.usebottles.bottles")
    config = BottleConfig(Name="Issue4557Test")
    program = {"name": "Issue4557Dummy"}

    assert (
        ManagerUtils.get_desktop_entry_id(config, program)
        == "com.usebottles.bottles.App_1e37a76b8f4de7c4a872eedb8dcb800172bb98c6.desktop"
    )


def test_desktop_entry_filename_sanitizes_bottle_and_program_names():
    config = BottleConfig(Name="Test Bottle!")
    program = {"name": "Game Name!.exe"}

    assert (
        ManagerUtils.get_desktop_entry_filename(config, program)
        == "bottles-TestBottle-GameNameexe.desktop"
    )
