# ruff: noqa: E402
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from gi.repository import Gio

from bottles.backend.models.result import Result
from bottles.backend.state import Events

with patch.object(Gio.Settings, "new", return_value=object()):
    from bottles.frontend.cli import cli


class FakeManager:
    def __init__(self, create_result=Result(True)):
        self.create_result = create_result
        self.calls = []
        self.runners_available = []
        self.dxvk_available = []
        self.vkd3d_available = []
        self.nvapi_available = []
        self.latencyflex_available = []

    def checks(self, **kwargs):
        self.calls.append(("checks", kwargs))
        return Result(True)

    def check_app_dirs(self):
        self.calls.append(("check_app_dirs", {}))

    def organize_components(self):
        self.calls.append(("organize_components", {}))

    def check_runners(self, _install_latest):
        self.calls.append(("check_runners", {}))

    def check_dxvk(self, _install_latest):
        self.calls.append(("check_dxvk", {}))

    def check_vkd3d(self, _install_latest):
        self.calls.append(("check_vkd3d", {}))

    def check_nvapi(self, _install_latest):
        self.calls.append(("check_nvapi", {}))

    def check_latencyflex(self, _install_latest):
        self.calls.append(("check_latencyflex", {}))

    def create_bottle(self, **kwargs):
        self.calls.append(("create_bottle", kwargs))
        return self.create_result


def _new_cli():
    instance = object.__new__(cli.CLI)
    instance.settings = object()
    instance.args = SimpleNamespace(
        bottle_name="Test",
        environment="application",
        custom_environment=None,
        arch="win64",
        runner=None,
        dxvk=None,
        vkd3d=None,
        nvapi=None,
        latencyflex=None,
    )
    return instance


def test_new_bottle_waits_for_catalogs_before_installing(monkeypatch):
    manager = FakeManager()
    waits = []
    monkeypatch.setattr(cli, "Manager", lambda **_kwargs: manager)
    monkeypatch.setattr(cli.EventManager, "wait", waits.append)

    _new_cli().new_bottle()

    assert manager.calls[0] == (
        "checks",
        {"install_latest": False, "first_run": True},
    )
    assert waits == [
        Events.ComponentsOrganizing,
        Events.DependenciesOrganizing,
        Events.InstallersOrganizing,
    ]
    assert manager.calls[1] == (
        "checks",
        {"install_latest": True, "first_run": False},
    )
    assert manager.calls[2][0] == "create_bottle"


def test_new_bottle_reports_creation_failure(monkeypatch, capsys):
    manager = FakeManager(Result(False, message="Prefix initialization failed"))
    monkeypatch.setattr(cli, "Manager", lambda **_kwargs: manager)
    monkeypatch.setattr(cli.EventManager, "wait", lambda _event: None)

    with pytest.raises(SystemExit) as error:
        _new_cli().new_bottle()

    assert error.value.code == 1
    assert capsys.readouterr().err == "Prefix initialization failed\n"


def test_list_components_prepares_directories(monkeypatch, capsys):
    manager = FakeManager()
    instance = object.__new__(cli.CLI)
    instance.settings = object()
    instance.args = SimpleNamespace(json=False)
    monkeypatch.setattr(cli, "Manager", lambda **_kwargs: manager)

    instance.list_components()

    assert manager.calls[0][0] == "check_app_dirs"
    assert "Found 0 runners" in capsys.readouterr().out


def test_umu_waits_for_components_catalog(monkeypatch, capsys):
    manager = FakeManager()
    manager.umu_repository = SimpleNamespace(list_games=lambda: ())
    waits = []
    instance = object.__new__(cli.CLI)
    instance.settings = object()
    instance.args = SimpleNamespace(action="list", json=False)
    monkeypatch.setattr(cli, "Manager", lambda **_kwargs: manager)
    monkeypatch.setattr(cli.EventManager, "wait", waits.append)

    instance.manage_umu()

    assert manager.calls[:2] == [
        ("check_app_dirs", {}),
        ("organize_components", {}),
    ]
    assert waits == [Events.ComponentsOrganizing]
    assert capsys.readouterr().out == ""
