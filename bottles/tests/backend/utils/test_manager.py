"""Unit tests for ManagerUtils."""

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils import manager
from bottles.backend.utils.manager import ManagerUtils


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
