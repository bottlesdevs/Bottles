from types import SimpleNamespace
from unittest.mock import patch

from gi.repository import Gio

from bottles.backend.models.config import BottleConfig

with patch.object(Gio.Settings, "new", return_value=object()):
    from bottles.frontend.cli import cli as cli_module


class FakeManager:
    configs = {}

    def __init__(self, **_kwargs):
        self.local_bottles = self.configs

    def check_bottles(self):
        return True

    def checks(self):
        return True

    def get_programs(self, _config):
        return [
            {"id": "first", "name": "Service", "path": "/first.exe"},
            {"id": "second", "name": "Service", "path": "/second.exe"},
        ]


def test_parser_accepts_autostart_and_program_id(monkeypatch):
    monkeypatch.setattr(
        cli_module.CLI,
        "_CLI__process_args",
        lambda _self: None,
    )
    parser = cli_module.CLI().parser

    assert parser.parse_args(["autostart"]).command == "autostart"
    args = parser.parse_args(["run", "-b", "Services", "--program-id", "service"])
    assert args.program_id == "service"
    args = parser.parse_args(["umu", "status", "--game", "PKHeX"])
    assert args.command == "umu"
    assert args.action == "status"
    assert args.game == "PKHeX"


def test_autostart_launches_each_enabled_program_by_id(monkeypatch):
    FakeManager.configs = {
        "Services": SimpleNamespace(
            Name="Services",
            External_Programs={
                "first": {"id": "first", "autostart": True},
                "disabled": {"id": "disabled", "autostart": False},
            },
        ),
        "Tools": SimpleNamespace(
            Name="Tools",
            External_Programs={
                "second": {"id": "second", "autostart": True},
            },
        ),
    }
    calls = []
    monkeypatch.setattr(cli_module, "Manager", FakeManager)
    monkeypatch.setattr(
        cli_module.subprocess,
        "Popen",
        lambda args, **kwargs: calls.append((args, kwargs)),
    )

    command = object.__new__(cli_module.CLI)
    command.settings = object()
    command.autostart_programs()

    assert calls == [
        (
            [
                "bottles-cli",
                "run",
                "-b",
                "Services",
                "--program-id",
                "first",
            ],
            {"start_new_session": True},
        ),
        (
            ["bottles-cli", "run", "-b", "Tools", "--program-id", "second"],
            {"start_new_session": True},
        ),
    ]


def test_run_program_selects_exact_program_id(monkeypatch):
    config = BottleConfig(Name="Services")
    FakeManager.configs = {"Services": config}
    launches = []
    monkeypatch.setattr(cli_module, "Manager", FakeManager)
    monkeypatch.setattr(
        cli_module.WineExecutor,
        "run_program",
        lambda bottle, program: launches.append((bottle, program)),
    )

    command = object.__new__(cli_module.CLI)
    command.settings = object()
    command.args = SimpleNamespace(
        bottle="Services",
        program=None,
        program_id="second",
        executable=None,
        keep_args=True,
        args=[],
    )
    command.run_program()

    assert launches[0][0] is config
    assert launches[0][1]["id"] == "second"
    assert launches[0][1]["path"] == "/second.exe"
