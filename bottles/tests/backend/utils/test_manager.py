"""Unit tests for ManagerUtils."""

import shlex
from types import SimpleNamespace

import pytest
from gi.repository import GLib

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils import manager
from bottles.backend.utils.manager import ManagerUtils


def test_open_filemanager_encodes_custom_path(monkeypatch):
    results = []
    monkeypatch.setattr(
        manager.SignalManager,
        "send",
        lambda _signal, result: results.append(result.data),
    )

    ManagerUtils.open_filemanager(
        path_type="custom", custom_path="/media/Games/Bottles Test"
    )

    assert results == ["file:///media/Games/Bottles%20Test"]


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

    @staticmethod
    def dynamic_launcher_get_desktop_entry(_desktop_id):
        raise GLib.Error(
            "missing",
            GLib.file_error_quark(),
            int(GLib.FileError.NOENT),
        )


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
                "--file-forwarding",
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
    field_arguments = ["@@u", "%u", "@@"] if flatpak_id else ["%u"]
    assert shlex.split(exec_line) == expected_prefix + [
        "run",
        "-p",
        "Alice's Game",
        "-b",
        "Hero's bottle",
        "--",
    ] + field_arguments


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


@pytest.mark.parametrize(
    ("path", "expected"),
    (
        ("/run/user/1000/doc/document-id/Document.txt", True),
        ("/run/user/1001/doc/document-id/Document.txt", False),
        ("/run/user/1000/doc/document-id/../pulse/native", False),
        ("/run/user/1000/documents/document-id/Document.txt", False),
        ("/run/user/1000/doc/document-id", False),
    ),
)
def test_portal_document_path_validation(monkeypatch, path, expected):
    monkeypatch.setattr(manager.os, "getuid", lambda: 1000)
    monkeypatch.setattr(manager.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(manager.os.path, "islink", lambda _path: False)
    monkeypatch.setattr(manager.os.path, "realpath", lambda value: value)

    assert ManagerUtils.is_portal_document_path(path) is expected


def test_portal_document_path_rejects_symlink(monkeypatch):
    path = "/run/user/1000/doc/document-id/Document.txt"
    monkeypatch.setattr(manager.os, "getuid", lambda: 1000)
    monkeypatch.setattr(manager.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(manager.os.path, "islink", lambda _path: True)

    assert ManagerUtils.is_portal_document_path(path) is False


def test_portal_document_path_rejects_symlinked_parent(monkeypatch):
    path = "/run/user/1000/doc/document-id/Document.txt"
    monkeypatch.setattr(manager.os, "getuid", lambda: 1000)
    monkeypatch.setattr(manager.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(manager.os.path, "islink", lambda _path: False)
    monkeypatch.setattr(
        manager.os.path,
        "realpath",
        lambda _path: "/run/user/1000/pulse/native",
    )

    assert ManagerUtils.is_portal_document_path(path) is False


def test_portal_document_path_rejects_non_regular_file(monkeypatch):
    path = "/run/user/1000/doc/document-id/Document.txt"
    monkeypatch.setattr(manager.os, "getuid", lambda: 1000)
    monkeypatch.setattr(manager.os.path, "isfile", lambda _path: False)

    assert ManagerUtils.is_portal_document_path(path) is False


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

    @staticmethod
    def dynamic_launcher_get_desktop_entry(_desktop_id):
        raise GLib.Error(
            "missing",
            GLib.file_error_quark(),
            int(GLib.FileError.NOENT),
        )


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


def test_get_autostart_programs_filters_disabled_and_removed_entries():
    configs = [
        SimpleNamespace(
            Name="Services",
            External_Programs={
                "enabled": {"id": "enabled", "autostart": True},
                "disabled": {"id": "disabled", "autostart": False},
                "removed": {"id": "removed", "autostart": True, "removed": True},
                "invalid": {"autostart": True},
            },
        ),
        SimpleNamespace(
            Name="Tools",
            External_Programs={
                "tool": {"id": "tool", "autostart": True},
            },
        ),
    ]

    entries = ManagerUtils.get_autostart_programs(configs)

    assert [(config.Name, program["id"]) for config, program in entries] == [
        ("Services", "enabled"),
        ("Tools", "tool"),
    ]


def test_set_autostart_entry_for_native_install(tmp_path, monkeypatch):
    monkeypatch.setattr(GLib, "get_user_config_dir", lambda: str(tmp_path))
    monkeypatch.setattr(manager, "APP_ID", "com.usebottles.bottles")

    assert ManagerUtils.set_autostart_entry(True)

    entry = tmp_path / "autostart" / "com.usebottles.bottles.autostart.desktop"
    assert entry.read_text() == (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Bottles\n"
        "Comment=Launch selected Bottles programs\n"
        "Exec=bottles-cli autostart\n"
        "Terminal=false\n"
        "NoDisplay=true\n"
    )

    assert ManagerUtils.set_autostart_entry(False)
    assert not entry.exists()


def test_resolve_file_associations_normalizes_and_deduplicates_extensions():
    extensions, mime_types, invalid = ManagerUtils.resolve_file_associations(
        "DOCX, .txt, .DOCX"
    )

    assert extensions == [".docx", ".txt"]
    assert mime_types == [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    ]
    assert invalid == []


def test_resolve_file_associations_rejects_unknown_and_unsafe_extensions():
    extensions, mime_types, invalid = ManagerUtils.resolve_file_associations(
        ".txt, ../escape, .bottles-unknown-file-type"
    )

    assert extensions == [".txt"]
    assert mime_types == ["text/plain"]
    assert invalid == ["../escape", ".bottles-unknown-file-type"]


def test_resolve_file_associations_accepts_known_uncertain_mime_type():
    extensions, mime_types, invalid = ManagerUtils.resolve_file_associations(".json")

    assert extensions == [".json"]
    assert mime_types == ["application/json"]
    assert invalid == []


def test_desktop_entry_uses_local_file_field_code_for_associations():
    config = BottleConfig(Name="Documents")
    program = {
        "name": "Document Editor",
        "executable": "editor.exe",
        "file_extensions": [".txt", ".pdf"],
    }

    exec_cmd = ManagerUtils.get_desktop_entry_exec(config, program)
    content = ManagerUtils.build_desktop_entry(config, program, exec_cmd)

    assert exec_cmd == ('bottles-cli run -p "Document Editor" -b "Documents" -- %f')
    assert "MimeType=text/plain;application/pdf;" in content


def test_program_steam_app_id_is_empty_without_configured_value():
    config = BottleConfig(Name="Games", Path="Games", Runner="soda-11.0-3")
    program = {"id": "game-id", "name": "Game", "path": "C:\\Games\\game.exe"}

    assert ManagerUtils.get_program_steam_app_id(config, program) == ""


def test_program_steam_app_id_preserves_custom_value():
    config = BottleConfig(Name="Games")
    program = {"environment": {"SteamAppId": "123456"}}

    assert ManagerUtils.get_program_steam_app_id(config, program) == "123456"


def test_program_steam_app_id_honors_bottle_environment():
    config = BottleConfig(
        Name="Games",
        Environment_Variables={"SteamAppId": "654321"},
    )

    assert ManagerUtils.get_program_steam_app_id(config, {}) == "654321"


def test_program_steam_app_id_prefers_program_environment():
    config = BottleConfig(
        Name="Games",
        Environment_Variables={"SteamAppId": "654321"},
    )
    program = {"environment": {"SteamAppId": "123456"}}

    assert ManagerUtils.get_program_steam_app_id(config, program) == "123456"


def test_program_steam_app_id_rejects_invalid_custom_value():
    config = BottleConfig(Name="Games")
    program = {"id": "game-id", "environment": {"SteamAppId": "invalid value"}}

    assert ManagerUtils.get_program_steam_app_id(config, program) == ""


def test_desktop_entry_matches_configured_steam_window_class():
    config = BottleConfig(Name="Games", Runner="soda-11.0-3")
    program = {
        "id": "game-id",
        "name": "Game",
        "executable": "game.exe",
        "environment": {"SteamAppId": "123456"},
    }

    content = ManagerUtils.build_desktop_entry(
        config,
        program,
        'bottles-cli run -p "Game" -b "Games"',
    )

    assert "StartupWMClass=steam_app_123456" in content


def test_desktop_entry_keeps_executable_window_class_for_proton():
    config = BottleConfig(Name="Games", Runner="dwproton-9-1")
    program = {
        "id": "game-id",
        "name": "Game",
        "executable": "Game.exe",
    }

    content = ManagerUtils.build_desktop_entry(
        config,
        program,
        'bottles-cli run -p "Game" -b "Games"',
    )

    assert "StartupWMClass=game.exe" in content


def test_desktop_entry_keeps_executable_window_class_for_wine():
    config = BottleConfig(Name="Applications", Runner="sys-wine")
    program = {
        "name": "Editor",
        "executable": "Editor.exe",
    }

    content = ManagerUtils.build_desktop_entry(
        config,
        program,
        'bottles-cli run -p "Editor" -b "Applications"',
    )

    assert "StartupWMClass=editor.exe" in content


def test_desktop_entry_keeps_uri_field_code_without_associations():
    config = BottleConfig(Name="Games")
    program = {"name": "Game", "executable": "game.exe"}

    exec_cmd = ManagerUtils.get_desktop_entry_exec(config, program)
    content = ManagerUtils.build_desktop_entry(config, program, exec_cmd)

    assert exec_cmd == 'bottles-cli run -p "Game" -b "Games" -- %u'
    assert "MimeType=" not in content


def test_desktop_entry_exec_escapes_reserved_characters():
    config = BottleConfig(Name='Bottle $ "One"')
    program = {
        "name": "Editor % Docs",
        "executable": "editor.exe",
        "file_extensions": [".txt"],
    }

    exec_cmd = ManagerUtils.get_desktop_entry_exec(config, program)
    assert exec_cmd == (
        'bottles-cli run -p "Editor %% Docs" -b "Bottle \\$ \\"One\\"" -- %f'
    )

    content = ManagerUtils.build_desktop_entry(config, program, exec_cmd)
    desktop_entry = GLib.KeyFile()
    desktop_entry.load_from_data(content, len(content), GLib.KeyFileFlags.NONE)
    parsed_exec = desktop_entry.get_string("Desktop Entry", "Exec")

    assert parsed_exec == exec_cmd
    assert GLib.shell_parse_argv(parsed_exec)[1] == [
        "bottles-cli",
        "run",
        "-p",
        "Editor %% Docs",
        "-b",
        'Bottle $ "One"',
        "--",
        "%f",
    ]


@pytest.mark.parametrize(
    "value",
    ["Dollar$Name", 'Quote"Name', "Tick`Name", r"Back\Slash"],
)
def test_desktop_entry_exec_round_trips_reserved_characters(value):
    config = BottleConfig(Name=value)
    program = {"name": "Editor", "executable": "editor.exe"}
    exec_cmd = ManagerUtils.get_desktop_entry_exec(config, program)
    content = ManagerUtils.build_desktop_entry(config, program, exec_cmd)
    desktop_entry = GLib.KeyFile()
    desktop_entry.load_from_data(content, len(content), GLib.KeyFileFlags.NONE)
    parsed_exec = desktop_entry.get_string("Desktop Entry", "Exec")

    assert parsed_exec == exec_cmd
    assert GLib.shell_parse_argv(parsed_exec)[1][5] == value


def test_desktop_entry_rejects_control_characters():
    config = BottleConfig(Name="Documents")
    program = {
        "name": "Editor\nExec=/bin/false",
        "executable": "editor.exe",
    }

    with pytest.raises(ValueError, match="control characters"):
        ManagerUtils.build_desktop_entry(
            config,
            program,
            'bottles-cli run -p "Editor" -b "Documents" -- %u',
        )


def test_desktop_entry_exec_uses_flatpak_file_forwarding_for_host(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles.Devel")
    config = BottleConfig(Name="Documents")
    program = {
        "name": "Document Editor",
        "executable": "editor.exe",
        "file_extensions": [".txt"],
    }

    assert ManagerUtils.get_desktop_entry_exec(config, program, for_host=True) == (
        "flatpak run --command=bottles-cli --file-forwarding "
        '"com.usebottles.bottles.Devel" run -p "Document Editor" '
        '-b "Documents" -- @@ %f @@'
    )


def test_umu_desktop_entry_exec_uses_game_id(monkeypatch):
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    config = {"Name": "UMU-test"}
    program = {
        "name": "Test Game",
        "executable": "game.exe",
        "umu_game": "e33f87f0-648e-44d2-bb73-78c9f60f77cf",
    }

    assert ManagerUtils.get_desktop_entry_exec(config, program, for_host=True) == (
        'bottles-cli umu run --game "e33f87f0-648e-44d2-bb73-78c9f60f77cf"'
    )


def test_umu_desktop_entry_exec_uses_flatpak_cli(monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    config = {"Name": "UMU-test"}
    program = {
        "name": "Test Game",
        "executable": "game.exe",
        "umu_game": "e33f87f0-648e-44d2-bb73-78c9f60f77cf",
    }

    assert ManagerUtils.get_desktop_entry_exec(config, program, for_host=True) == (
        "flatpak run --command=bottles-cli "
        '"com.usebottles.bottles" umu run --game '
        '"e33f87f0-648e-44d2-bb73-78c9f60f77cf"'
    )


def test_has_desktop_entry_detects_dynamic_launcher(monkeypatch):
    config = BottleConfig(Name="Documents")
    program = {"name": "Document Editor", "executable": "editor.exe"}
    desktop_entry_id = ManagerUtils.get_desktop_entry_id(config, program)

    class Portal:
        @staticmethod
        def dynamic_launcher_get_desktop_entry(requested_id):
            assert requested_id == desktop_entry_id
            return "[Desktop Entry]\nType=Application\n"

    monkeypatch.setattr(manager, "portal", Portal())

    assert ManagerUtils.has_desktop_entry(config, program) is True


def test_has_desktop_entry_preserves_unknown_portal_state(monkeypatch):
    monkeypatch.setattr(
        ManagerUtils, "get_portal_desktop_entry_state", lambda *_args: None
    )
    monkeypatch.setattr(
        ManagerUtils,
        "get_manual_desktop_entry_paths",
        lambda *_args: ("/applications", ["/applications/missing.desktop"]),
    )

    assert (
        ManagerUtils.has_desktop_entry(
            BottleConfig(Name="Unknown"),
            {"name": "Editor", "executable": "editor.exe"},
        )
        is None
    )


def test_missing_portal_entry_error_is_recognized():
    error = GLib.Error(
        "missing",
        GLib.file_error_quark(),
        int(GLib.FileError.NOENT),
    )

    assert ManagerUtils.is_missing_portal_entry_error(error) is True


def test_update_desktop_database_preserves_existing_default(monkeypatch):
    commands = []
    preserved = []
    app_info = SimpleNamespace(
        set_as_default_for_type=lambda mime_type: preserved.append(mime_type) or True
    )
    monkeypatch.setattr(manager.shutil, "which", lambda _name: "/usr/bin/updater")
    monkeypatch.setattr(
        manager.subprocess,
        "run",
        lambda command, **_kwargs: (
            commands.append(command) or SimpleNamespace(returncode=0, stderr="")
        ),
    )

    ManagerUtils.update_desktop_database(
        "/home/user/.local/share/applications",
        {"text/plain": app_info},
    )

    assert commands == [["/usr/bin/updater", "/home/user/.local/share/applications"]]
    assert preserved == ["text/plain"]


def test_create_desktop_entry_installs_associations_through_portal(
    monkeypatch, tmp_path
):
    installed = {}
    callback_called = []

    class Portal:
        @staticmethod
        def dynamic_launcher_prepare_install(*args):
            args[-1](None, object())

        @staticmethod
        def dynamic_launcher_prepare_install_finish(_result):
            return {"token": "test-token"}

        @staticmethod
        def dynamic_launcher_install(token, desktop_id, content):
            installed.update(token=token, desktop_id=desktop_id, content=content)

    icon = tmp_path / "icon.svg"
    icon.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles.Devel")
    monkeypatch.setattr(manager, "portal", Portal())
    monkeypatch.setattr(manager, "APP_ID", "com.usebottles.bottles")
    monkeypatch.setattr(
        ManagerUtils, "get_portal_desktop_entry_state", lambda *_args: False
    )
    config = BottleConfig(Name="Documents")
    program = {
        "name": "Document Editor",
        "executable": "editor.exe",
        "file_extensions": [".txt"],
    }

    ManagerUtils.create_desktop_entry(
        config,
        program,
        custom_icon=str(icon),
        on_created=lambda: callback_called.append(True),
    )

    assert installed["token"] == "test-token"
    assert installed["desktop_id"] == ManagerUtils.get_desktop_entry_id(config, program)
    assert (
        "Exec=flatpak run --command=bottles-cli --file-forwarding "
        '"com.usebottles.bottles.Devel" run -p "Document Editor" '
        '-b "Documents" -- @@ %f @@'
        in installed["content"]
    )
    assert "MimeType=text/plain;" in installed["content"]
    assert callback_called == [True]


def test_create_desktop_entry_does_not_fallback_when_portal_is_cancelled(
    monkeypatch, tmp_path
):
    callbacks = []

    class Portal:
        @staticmethod
        def dynamic_launcher_prepare_install(*args):
            args[-1](None, object())

        @staticmethod
        def dynamic_launcher_prepare_install_finish(_result):
            return None

        @staticmethod
        def dynamic_launcher_install(*_args):
            raise AssertionError("cancelled request must not install")

    icon = tmp_path / "icon.svg"
    icon.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    monkeypatch.setattr(manager, "portal", Portal())
    monkeypatch.setattr(
        ManagerUtils, "get_portal_desktop_entry_state", lambda *_args: False
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    ManagerUtils.create_desktop_entry(
        BottleConfig(Name="Cancelled"),
        {"name": "Editor", "executable": "editor.exe", "file_extensions": [".txt"]},
        custom_icon=str(icon),
        on_created=lambda: callbacks.append("created"),
        on_failed=lambda: callbacks.append("failed"),
        on_cancelled=lambda: callbacks.append("cancelled"),
    )

    assert callbacks == ["cancelled"]
    assert not (tmp_path / ".local/share/applications").exists()


def test_create_desktop_entry_uses_manual_fallback_for_new_launcher(
    monkeypatch, tmp_path
):
    callbacks = []

    class Portal:
        @staticmethod
        def dynamic_launcher_prepare_install(*args):
            args[-1](None, object())

        @staticmethod
        def dynamic_launcher_prepare_install_finish(_result):
            raise GLib.Error("portal unavailable")

    config = BottleConfig(Name="Fallback")
    program = {"name": "Editor", "executable": "editor.exe"}
    icon = tmp_path / "icon.svg"
    icon.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    monkeypatch.setattr(manager, "portal", Portal())
    monkeypatch.setattr(
        ManagerUtils, "get_portal_desktop_entry_state", lambda *_args: False
    )
    monkeypatch.setattr(manager.GLib, "get_user_special_dir", lambda *_args: None)
    monkeypatch.setattr(ManagerUtils, "update_desktop_database", lambda *_args: None)
    monkeypatch.setenv("HOME", str(tmp_path))

    ManagerUtils.create_desktop_entry(
        config,
        program,
        custom_icon=str(icon),
        on_created=lambda: callbacks.append("created"),
        on_failed=lambda: callbacks.append("failed"),
    )

    entry = (
        tmp_path
        / ".local/share/applications"
        / ManagerUtils.get_desktop_entry_filename(config, program)
    )
    assert callbacks == ["created"]
    assert entry.exists()


def test_create_desktop_entry_removes_manual_fallback_after_portal_install(
    monkeypatch, tmp_path
):
    class Portal:
        @staticmethod
        def dynamic_launcher_prepare_install(*args):
            args[-1](None, object())

        @staticmethod
        def dynamic_launcher_prepare_install_finish(_result):
            return {"token": "test-token"}

        @staticmethod
        def dynamic_launcher_install(*_args):
            return None

    config = BottleConfig(Name="Transition")
    program = {"name": "Editor", "executable": "editor.exe"}
    icon = tmp_path / "icon.svg"
    icon.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    applications = tmp_path / ".local/share/applications"
    applications.mkdir(parents=True)
    manual_entry = applications / ManagerUtils.get_desktop_entry_filename(
        config, program
    )
    manual_entry.write_text("[Desktop Entry]\n")

    monkeypatch.setattr(manager, "portal", Portal())
    monkeypatch.setattr(
        ManagerUtils, "get_portal_desktop_entry_state", lambda *_args: False
    )
    monkeypatch.setattr(manager.GLib, "get_user_special_dir", lambda *_args: None)
    monkeypatch.setattr(ManagerUtils, "update_desktop_database", lambda *_args: None)
    monkeypatch.setenv("HOME", str(tmp_path))

    ManagerUtils.create_desktop_entry(
        config,
        program,
        custom_icon=str(icon),
    )

    assert not manual_entry.exists()


def test_create_desktop_entry_does_not_duplicate_existing_portal_on_error(
    monkeypatch, tmp_path
):
    callbacks = []

    class Portal:
        @staticmethod
        def dynamic_launcher_prepare_install(*args):
            args[-1](None, object())

        @staticmethod
        def dynamic_launcher_prepare_install_finish(_result):
            return {"token": "test-token"}

        @staticmethod
        def dynamic_launcher_install(*_args):
            raise GLib.Error("install failed")

    icon = tmp_path / "icon.svg"
    icon.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    monkeypatch.setattr(manager, "portal", Portal())
    monkeypatch.setattr(
        ManagerUtils, "get_portal_desktop_entry_state", lambda *_args: True
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    ManagerUtils.create_desktop_entry(
        BottleConfig(Name="Existing"),
        {"name": "Editor", "executable": "editor.exe"},
        custom_icon=str(icon),
        on_created=lambda: callbacks.append("created"),
        on_failed=lambda: callbacks.append("failed"),
    )

    assert callbacks == ["failed"]
    assert not (tmp_path / ".local/share/applications").exists()


def test_unknown_portal_state_removes_manual_launcher(monkeypatch, tmp_path):
    config = BottleConfig(Name="Unknown")
    program = {"name": "Editor", "executable": "editor.exe"}
    applications = tmp_path / ".local/share/applications"
    applications.mkdir(parents=True)
    manual_entry = applications / ManagerUtils.get_desktop_entry_filename(
        config, program
    )
    manual_entry.write_text("[Desktop Entry]\n")

    monkeypatch.setattr(
        ManagerUtils, "get_portal_desktop_entry_state", lambda *_args: None
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    assert ManagerUtils.remove_desktop_entry(config, program) is True
    assert not manual_entry.exists()


def test_unknown_portal_state_without_manual_launcher_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(
        ManagerUtils, "get_portal_desktop_entry_state", lambda *_args: None
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    assert ManagerUtils.remove_desktop_entry(
        BottleConfig(Name="Unknown"),
        {"name": "Editor", "executable": "editor.exe"},
    ) is False
