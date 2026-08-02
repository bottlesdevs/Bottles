"""Unit tests for ManagerUtils."""

import shlex
from types import SimpleNamespace

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


class PortalProxyStub:
    def __init__(self, mount, host_paths):
        self.mount = mount
        self.host_paths = host_paths

    def call_sync(self, method, *_args):
        if method == "GetMountPoint":
            return SimpleNamespace(unpack=lambda: (self.mount,))
        if method == "GetHostPaths":
            return SimpleNamespace(unpack=lambda: (self.host_paths,))
        raise AssertionError(method)


def test_get_portal_host_path_resolves_exported_directory(monkeypatch):
    proxy = PortalProxyStub(
        b"/run/user/1000/doc\x00",
        {"document-id": b"/media/Games/My Bottles\x00"},
    )
    monkeypatch.setattr(manager.Gio, "bus_get_sync", lambda *_args: object())
    monkeypatch.setattr(manager.Gio.DBusProxy, "new_sync", lambda *_args: proxy)

    assert (
        ManagerUtils.get_portal_host_path("/run/user/1000/doc/document-id/My Bottles")
        == "/media/Games/My Bottles"
    )


def test_get_portal_host_path_preserves_nested_path(monkeypatch):
    proxy = PortalProxyStub(
        b"/run/user/1000/doc\x00",
        {"document-id": b"/media/Games/My Bottles\x00"},
    )
    monkeypatch.setattr(manager.Gio, "bus_get_sync", lambda *_args: object())
    monkeypatch.setattr(manager.Gio.DBusProxy, "new_sync", lambda *_args: proxy)

    assert (
        ManagerUtils.get_portal_host_path(
            "/run/user/1000/doc/document-id/My Bottles/drive_c/game.exe"
        )
        == "/media/Games/My Bottles/drive_c/game.exe"
    )


def test_get_portal_host_path_rejects_mismatched_export_name(monkeypatch):
    proxy = PortalProxyStub(
        b"/run/user/1000/doc\x00",
        {"document-id": b"/media/Games/My Bottles\x00"},
    )
    monkeypatch.setattr(manager.Gio, "bus_get_sync", lambda *_args: object())
    monkeypatch.setattr(manager.Gio.DBusProxy, "new_sync", lambda *_args: proxy)

    assert (
        ManagerUtils.get_portal_host_path("/run/user/1000/doc/document-id/Other Folder")
        is None
    )


def test_get_portal_host_path_rejects_parent_traversal(monkeypatch):
    proxy = PortalProxyStub(
        b"/run/user/1000/doc\x00",
        {"document-id": b"/media/Games/My Bottles\x00"},
    )
    monkeypatch.setattr(manager.Gio, "bus_get_sync", lambda *_args: object())
    monkeypatch.setattr(manager.Gio.DBusProxy, "new_sync", lambda *_args: proxy)

    assert (
        ManagerUtils.get_portal_host_path(
            "/run/user/1000/doc/document-id/My Bottles/../../Other"
        )
        is None
    )


def test_resolve_portal_path_keeps_unavailable_portal_path(monkeypatch):
    portal_path = "/run/user/1000/doc/document-id/My Bottles"
    monkeypatch.setattr(
        ManagerUtils,
        "get_portal_host_path",
        lambda _path: "/media/Games/My Bottles",
    )
    monkeypatch.setattr(manager.os.path, "exists", lambda _path: False)

    assert ManagerUtils.resolve_portal_path(portal_path) == portal_path


def test_resolve_portal_path_returns_accessible_host_path(monkeypatch):
    portal_path = "/run/user/1000/doc/document-id/My Bottles"
    host_path = "/media/Games/My Bottles"
    monkeypatch.setattr(
        ManagerUtils,
        "get_portal_host_path",
        lambda _path: host_path,
    )
    monkeypatch.setattr(manager.os.path, "exists", lambda path: path == host_path)

    assert ManagerUtils.resolve_portal_path(portal_path) == host_path


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


class FallbackLauncherPortal:
    def __init__(
        self,
        prepare_result=None,
        prepare_error=None,
        install_error=None,
    ):
        self.prepare_result = prepare_result
        self.prepare_error = prepare_error
        self.install_error = install_error
        self.callback = None
        self.installed = False

    def dynamic_launcher_prepare_install(self, *args):
        self.callback = args[-1]

    def dynamic_launcher_prepare_install_finish(self, _result):
        if self.prepare_error:
            raise manager.GLib.Error(self.prepare_error)
        return self.prepare_result

    def dynamic_launcher_install(self, *_args):
        if self.install_error:
            raise manager.GLib.Error(self.install_error)
        self.installed = True


def request_desktop_entry(monkeypatch, tmp_path, portal):
    icon = tmp_path / "icon.svg"
    icon.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    results = []

    monkeypatch.setattr(manager, "portal", portal)
    ManagerUtils.create_desktop_entry(
        BottleConfig(Name="Test Bottle"),
        {
            "name": "Test Program",
            "executable": "test.exe",
            "path": "/test.exe",
        },
        custom_icon=str(icon),
        callback=results.append,
    )
    portal.callback(None, object())
    return results


def test_desktop_entry_reports_portal_success(monkeypatch, tmp_path):
    portal = FallbackLauncherPortal(prepare_result={"token": "test-token"})

    results = request_desktop_entry(monkeypatch, tmp_path, portal)

    assert portal.installed is True
    assert results[0].status is True
    assert results[0].data == {"method": "portal"}


def test_desktop_entry_reports_manual_fallback_paths(monkeypatch, tmp_path):
    portal = FallbackLauncherPortal(prepare_error="portal unavailable")
    applications = tmp_path / "applications"
    monkeypatch.setattr(
        manager.os.path,
        "expanduser",
        lambda path: (
            str(applications) if path == "~/.local/share/applications" else path
        ),
    )
    monkeypatch.setattr(manager.GLib, "get_user_special_dir", lambda *_args: None)

    results = request_desktop_entry(monkeypatch, tmp_path, portal)

    expected = applications / "bottles-TestBottle-TestProgram.desktop"
    assert expected.is_file()
    assert results[0].status is True
    assert results[0].data == {"method": "manual", "paths": [str(expected)]}


def test_desktop_entry_falls_back_when_portal_install_fails(monkeypatch, tmp_path):
    portal = FallbackLauncherPortal(
        prepare_result={"token": "test-token"},
        install_error="install failed",
    )
    applications = tmp_path / "applications"
    monkeypatch.setattr(
        manager.os.path,
        "expanduser",
        lambda path: (
            str(applications) if path == "~/.local/share/applications" else path
        ),
    )
    monkeypatch.setattr(manager.GLib, "get_user_special_dir", lambda *_args: None)

    results = request_desktop_entry(monkeypatch, tmp_path, portal)

    assert portal.installed is False
    assert results[0].status is True
    assert results[0].data["method"] == "manual"


def test_desktop_entry_reports_manual_fallback_failure(monkeypatch, tmp_path):
    portal = FallbackLauncherPortal(prepare_error="portal unavailable")

    def deny_directory_creation(*_args, **_kwargs):
        raise PermissionError("permission denied")

    monkeypatch.setattr(manager.os, "makedirs", deny_directory_creation)
    monkeypatch.setattr(manager.GLib, "get_user_special_dir", lambda *_args: None)

    results = request_desktop_entry(monkeypatch, tmp_path, portal)

    assert results[0].status is False
    assert results[0].data == {"method": "manual", "paths": []}
    assert "permission denied" in results[0].message
