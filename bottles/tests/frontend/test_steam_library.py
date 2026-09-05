# ruff: noqa: E402
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

blueprint_compiler = shutil.which("blueprint-compiler")
resource_bundle = Path("/app/share/bottles/bottles.gresource")
if blueprint_compiler is None or not resource_bundle.is_file():
    pytest.skip("Bottles Flatpak test resources are required", allow_module_level=True)

resource_dir = tempfile.TemporaryDirectory(prefix="bottles-steam-library-")
source_root = Path(__file__).resolve().parents[3]
subprocess.run(
    [
        blueprint_compiler,
        "compile",
        str(source_root / "bottles/frontend/ui/program-entry.blp"),
        "--output",
        str(Path(resource_dir.name) / "program-entry.ui"),
    ],
    check=True,
)
os.environ["G_RESOURCE_OVERLAYS"] = f"/com/usebottles/bottles={resource_dir.name}"

from gi.repository import Gio

Gio.resources_register(Gio.Resource.load(str(resource_bundle)))

from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.frontend.views import bottle_details
from bottles.frontend.views.bottle_details import BottleView
from bottles.frontend.widgets import library as library_module
from bottles.frontend.widgets import program as program_module
from bottles.frontend.widgets.library import LibraryEntry
from bottles.frontend.widgets.program import ProgramEntry


def test_cover_picker_opens_in_pictures(monkeypatch):
    class Filter:
        def set_name(self, _name):
            pass

        def add_pattern(self, _pattern):
            pass

    class Store(list):
        @staticmethod
        def new(_type):
            return Store()

    class Dialog:
        def set_title(self, _title):
            pass

        def set_filters(self, _filters):
            pass

        def set_default_filter(self, _filter):
            pass

        def set_initial_folder(self, folder):
            self.initial_folder = folder

        def open(self, _window, callback):
            self.callback = callback

    dialog = Dialog()
    monkeypatch.setattr(
        library_module,
        "Gtk",
        SimpleNamespace(
            FileDialog=SimpleNamespace(new=lambda: dialog),
            FileFilter=Filter,
        ),
    )
    monkeypatch.setattr(
        library_module,
        "Gio",
        SimpleNamespace(
            File=SimpleNamespace(new_for_path=lambda path: path),
            ListStore=Store,
        ),
    )
    monkeypatch.setattr(
        library_module,
        "GLib",
        SimpleNamespace(
            UserDirectory=SimpleNamespace(DIRECTORY_PICTURES=4),
            get_user_special_dir=lambda _directory: "/home/user/Pictures",
        ),
    )

    entry = SimpleNamespace(window=object())
    LibraryEntry._LibraryEntry__choose_cover(entry)

    assert dialog.initial_folder == "/home/user/Pictures"


class Button:
    def __init__(self):
        self.visible = True
        self.sensitive = True
        self.text = None

    def set_visible(self, visible):
        self.visible = visible

    def set_sensitive(self, sensitive):
        self.sensitive = sensitive

    def set_property(self, name, value):
        setattr(self, name, value)


def desktop_program_entry():
    toasts = []
    return (
        SimpleNamespace(
            window=SimpleNamespace(show_toast=toasts.append),
            config=object(),
            _ProgramEntry__set_desktop_entry_state=lambda _exists: None,
            program={
                "name": "Test Program",
                "executable": "test.exe",
                "path": "/test.exe",
            },
        ),
        toasts,
    )


def test_add_entry_reports_portal_success(monkeypatch):
    entry, toasts = desktop_program_entry()

    def create_desktop_entry(**kwargs):
        kwargs["callback"](Result(True, {"method": "portal"}))

    monkeypatch.setattr(
        program_module.ManagerUtils,
        "create_desktop_entry",
        create_desktop_entry,
    )

    ProgramEntry.add_entry(entry, None)

    assert toasts == ['Desktop Entry created for "Test Program"']


def test_desktop_entry_state_updates_action():
    labels = []
    sensitivities = []
    entry = SimpleNamespace(
        btn_add_entry=SimpleNamespace(
            set_property=lambda name, value: labels.append((name, value)),
            set_sensitive=sensitivities.append,
        ),
    )

    ProgramEntry._ProgramEntry__set_desktop_entry_state(entry, True)
    ProgramEntry._ProgramEntry__set_desktop_entry_state(entry, False)

    assert labels == [
        ("text", "Remove Desktop Entry"),
        ("text", "Add Desktop Entry"),
    ]
    assert sensitivities == [True, True]
    assert entry._ProgramEntry__desktop_entry_exists is False


def test_remove_entry_result_updates_action():
    entry, toasts = desktop_program_entry()
    states = []
    entry._ProgramEntry__set_desktop_entry_state = states.append

    ProgramEntry._ProgramEntry__desktop_entry_removed(entry, True, None)

    assert states == [False]
    assert toasts == ['Desktop Entry removed for "Test Program"']


def test_manage_entry_uses_detected_state():
    calls = []
    entry = SimpleNamespace(
        _ProgramEntry__desktop_entry_exists=True,
        add_entry=lambda _widget: calls.append("add"),
        remove_entry=lambda _widget: calls.append("remove"),
    )

    ProgramEntry.manage_entry(entry, None)

    assert calls == ["remove"]


def test_program_widget_switches_desktop_entry_action(monkeypatch):
    toasts = []

    class LibraryManager:
        def get_library(self):
            return {}

    monkeypatch.setattr(program_module, "LibraryManager", LibraryManager)
    monkeypatch.setattr(
        program_module,
        "RunAsync",
        lambda task_func, callback, **kwargs: callback(task_func(**kwargs), None),
    )
    monkeypatch.setattr(
        program_module.ManagerUtils,
        "extract_icon",
        lambda **_kwargs: "com.usebottles.bottles-program",
    )
    monkeypatch.setattr(
        program_module.ManagerUtils,
        "has_desktop_entry",
        lambda _config, _program: True,
    )
    monkeypatch.setattr(
        program_module.ManagerUtils,
        "remove_desktop_entry",
        lambda _config, _program: True,
    )
    window = SimpleNamespace(
        page_details=SimpleNamespace(view_bottle=object()),
        manager=SimpleNamespace(
            steam_manager=SimpleNamespace(is_steam_supported=False),
        ),
        show_toast=toasts.append,
    )
    entry = ProgramEntry(
        window,
        BottleConfig(Name="Games", Path="Games"),
        {
            "name": "Test Program",
            "id": "test-program",
            "path": "C:\\Games\\test.exe",
            "executable": "test.exe",
        },
        check_boot=False,
    )

    ProgramEntry._ProgramEntry__refresh_desktop_entry_state(
        entry,
        SimpleNamespace(get_visible=lambda: True),
    )
    assert entry.btn_add_entry.get_property("text") == "Remove Desktop Entry"
    entry.btn_add_entry.emit("clicked")
    assert entry.btn_add_entry.get_property("text") == "Add Desktop Entry"
    assert toasts == ['Desktop Entry removed for "Test Program"']


def test_add_entry_warns_after_manual_fallback(monkeypatch):
    entry, toasts = desktop_program_entry()
    warnings = []

    def create_desktop_entry(**kwargs):
        kwargs["callback"](
            Result(True, {"method": "manual", "paths": ["/test.desktop"]})
        )

    monkeypatch.setattr(
        program_module.ManagerUtils,
        "create_desktop_entry",
        create_desktop_entry,
    )
    monkeypatch.setattr(
        ProgramEntry,
        "_ProgramEntry__show_desktop_entry_fallback",
        lambda _self, result: warnings.append(result),
    )

    ProgramEntry.add_entry(entry, None)

    assert toasts == []
    assert warnings[0].data["method"] == "manual"


def test_add_entry_warns_after_manual_fallback_failure(monkeypatch):
    entry, toasts = desktop_program_entry()
    warnings = []

    def create_desktop_entry(**kwargs):
        kwargs["callback"](Result(False, {"method": "manual", "paths": []}))

    monkeypatch.setattr(
        program_module.ManagerUtils,
        "create_desktop_entry",
        create_desktop_entry,
    )
    monkeypatch.setattr(
        ProgramEntry,
        "_ProgramEntry__show_desktop_entry_fallback",
        lambda _self, result: warnings.append(result),
    )

    ProgramEntry.add_entry(entry, None)

    assert toasts == []
    assert warnings[0].status is False


def test_flatpak_fallback_guidance_requires_restart():
    title, description, command = (
        ProgramEntry._ProgramEntry__desktop_entry_fallback_content(
            Result(False, {"method": "manual", "paths": []}),
            "com.usebottles.bottles.Devel",
        )
    )

    assert title == "Desktop Entry Could Not Be Created"
    assert "Close Bottles" in description
    assert "reopen Bottles" in description
    assert command.endswith("com.usebottles.bottles.Devel")


def test_native_fallback_guidance_does_not_show_flatpak_command():
    _title, description, command = (
        ProgramEntry._ProgramEntry__desktop_entry_fallback_content(
            Result(False, {"method": "manual", "paths": []}),
            None,
        )
    )

    assert "writable" in description
    assert command is None


def steam_config():
    return BottleConfig(
        Name="Example Game",
        Path="/steamapps/compatdata/123/pfx",
        Environment="Steam",
        CompatData="123",
    )


def test_steam_program_uses_stable_library_id(monkeypatch):
    calls = []
    visibility = []
    view = SimpleNamespace(
        config=steam_config(),
        manager=SimpleNamespace(get_programs=lambda _config, **_kwargs: []),
        empty_list=lambda: None,
        row_no_programs=SimpleNamespace(
            set_visible=lambda visible: visibility.append(visible)
        ),
        show_hidden=False,
    )

    monkeypatch.setattr(
        bottle_details.GLib,
        "idle_add",
        lambda _callback, *args: calls.append(args),
    )
    monkeypatch.setattr(
        bottle_details,
        "WineServer",
        lambda _config: SimpleNamespace(is_alive=lambda: False),
    )

    BottleView.update_programs(view)

    assert (
        {
            "name": "Example Game",
            "id": "steam:123",
            "steam": True,
        },
        None,
        True,
    ) in calls
    assert visibility == [False]


def test_steam_program_can_be_added_to_library(monkeypatch):
    captured = {}

    class LibraryManager:
        def add_to_library(self, data, config):
            captured["data"] = data
            captured["config"] = config
            return "entry-id"

    def run_async(task, callback):
        callback(task(), False)

    config = steam_config()
    add_button = Button()
    steam_add_button = Button()
    entry = SimpleNamespace(
        window=SimpleNamespace(
            update_library=lambda: captured.setdefault("updated", True),
            show_toast=lambda _message: None,
        ),
        config=config,
        program={
            "name": "Example Game",
            "id": "steam:123",
            "steam": True,
        },
        is_steam=True,
        btn_add_library=add_button,
        btn_add_steam_library=steam_add_button,
        save_program=lambda: pytest.fail("Steam games must not be stored as programs"),
    )
    entry._ProgramEntry__set_library_state = lambda exists: (
        ProgramEntry._ProgramEntry__set_library_state(entry, exists)
    )

    monkeypatch.setattr(program_module, "LibraryManager", LibraryManager)
    monkeypatch.setattr(program_module, "RunAsync", run_async)
    monkeypatch.setattr(
        program_module.ManagerUtils,
        "extract_icon",
        lambda *_args: pytest.fail("Steam games do not use Wine executable icons"),
    )

    ProgramEntry.add_to_library(entry, None)

    assert captured["data"] == {
        "bottle": {"name": "123", "path": config.Path},
        "name": "Example Game",
        "id": "steam:123",
        "steam": True,
    }
    assert captured["config"] is config
    assert captured["updated"] is True
    assert add_button.visible is True
    assert add_button.text == "Remove from Library"
    assert steam_add_button.visible is False


def test_regular_program_library_entry_is_unchanged(monkeypatch):
    captured = {}

    class LibraryManager:
        def add_to_library(self, data, config):
            captured["data"] = data
            captured["config"] = config
            return "entry-id"

    def run_async(task, callback):
        callback(task(), False)

    config = BottleConfig(Name="Games", Path="Games")
    entry = SimpleNamespace(
        window=SimpleNamespace(
            update_library=lambda: captured.setdefault("updated", True),
            show_toast=lambda _message: None,
        ),
        config=config,
        program={
            "name": "Example Game",
            "id": "program-id",
            "path": "C:\\Games\\example.exe",
        },
        is_steam=False,
        btn_add_library=Button(),
        btn_add_steam_library=Button(),
        save_program=lambda: captured.setdefault("saved", True),
    )
    entry._ProgramEntry__set_library_state = lambda exists: (
        ProgramEntry._ProgramEntry__set_library_state(entry, exists)
    )

    monkeypatch.setattr(program_module, "LibraryManager", LibraryManager)
    monkeypatch.setattr(program_module, "RunAsync", run_async)
    monkeypatch.setattr(
        program_module.ManagerUtils,
        "extract_icon",
        lambda *_args: "example-icon",
    )

    ProgramEntry.add_to_library(entry, None)

    assert captured["data"] == {
        "bottle": {"name": "Games", "path": "Games"},
        "name": "Example Game",
        "id": "program-id",
        "icon": "example-icon",
    }
    assert captured["config"] is config
    assert captured["saved"] is True
    assert captured["updated"] is True
    assert entry.btn_add_library.text == "Remove from Library"


def test_library_waits_for_program_icon_extraction(monkeypatch, tmp_path):
    captured = {}
    icon_path = tmp_path / "Example Game.png"

    class LibraryManager:
        def add_to_library(self, data, _config):
            captured["data"] = data
            return "entry-id"

    class IconJob:
        @staticmethod
        def join():
            icon_path.write_text("icon", encoding="utf-8")

    def run_async(task, callback):
        callback(task(), False)

    entry = SimpleNamespace(
        window=SimpleNamespace(
            update_library=lambda: None,
            show_toast=lambda _message: None,
        ),
        config=BottleConfig(Name="Games", Path="Games"),
        program={
            "name": "Example Game",
            "id": "program-id",
            "path": "C:\\Games\\example.exe",
        },
        is_steam=False,
        btn_add_library=Button(),
        btn_add_steam_library=Button(),
        save_program=lambda: None,
        _ProgramEntry__program_icon_job=IconJob(),
        _ProgramEntry__program_icon_path=str(icon_path),
    )
    entry._ProgramEntry__set_library_state = lambda exists: (
        ProgramEntry._ProgramEntry__set_library_state(entry, exists)
    )

    monkeypatch.setattr(program_module, "LibraryManager", LibraryManager)
    monkeypatch.setattr(program_module, "RunAsync", run_async)
    monkeypatch.setattr(
        program_module.ManagerUtils,
        "extract_icon",
        lambda *_args: pytest.fail("The completed icon job must be reused"),
    )

    ProgramEntry.add_to_library(entry, None)

    assert captured["data"]["icon"] == str(icon_path)


def test_program_library_action_removes_entry(monkeypatch):
    captured = {}

    class LibraryManager:
        def remove_from_library(self, entry_uuid, config):
            captured["uuid"] = entry_uuid
            captured["config"] = config

    def run_async(task, callback):
        callback(task(), False)

    config = BottleConfig(Name="Games", Path="Games")
    button = Button()
    entry = SimpleNamespace(
        window=SimpleNamespace(
            update_library=lambda: captured.setdefault("updated", True),
            show_toast=lambda message: captured.setdefault("toast", message),
        ),
        config=config,
        program={"name": "Example Game"},
        btn_add_library=button,
        _ProgramEntry__library_entry_uuid="entry-id",
        _ProgramEntry__set_library_state=lambda exists: (
            ProgramEntry._ProgramEntry__set_library_state(entry, exists)
        ),
    )

    monkeypatch.setattr(program_module, "LibraryManager", LibraryManager)
    monkeypatch.setattr(program_module, "RunAsync", run_async)

    ProgramEntry.manage_library(entry, None)

    assert captured["uuid"] == "entry-id"
    assert captured["config"] is config
    assert captured["updated"] is True
    assert captured["toast"] == '"Example Game" removed from your library'
    assert entry._ProgramEntry__library_entry_uuid is None
    assert button.text == "Add to Library"
    assert button.sensitive is True


def test_uninstall_program_refreshes_cached_programs(monkeypatch):
    calls = []
    config = BottleConfig(Name="Games", Path="Games")
    entry = SimpleNamespace(
        config=config,
        program={"name": "Example Game"},
        view_bottle=SimpleNamespace(
            update_programs=lambda **kwargs: calls.append(kwargs)
        ),
        update_programs=lambda: calls.append({}),
    )

    monkeypatch.setattr(
        program_module,
        "Uninstaller",
        lambda _config: SimpleNamespace(from_name=lambda _name: None),
    )
    monkeypatch.setattr(
        program_module,
        "RunAsync",
        lambda task_func, callback, **_kwargs: callback(None, False),
    )
    monkeypatch.setattr(
        program_module.ManagerUtils,
        "remove_desktop_entry",
        lambda _config, _program: None,
    )

    ProgramEntry.uninstall_program(entry, None)

    assert calls == [{"config": config, "force_update": True}]


def test_steam_program_widget_exposes_library_action(monkeypatch):
    captured = {}

    class LibraryManager:
        def get_library(self):
            return {}

        def add_to_library(self, data, config):
            captured["data"] = data
            captured["config"] = config
            return "entry-id"

    def run_async(task, callback):
        callback(task(), False)

    monkeypatch.setattr(program_module, "LibraryManager", LibraryManager)
    monkeypatch.setattr(program_module, "RunAsync", run_async)
    window = SimpleNamespace(
        page_details=SimpleNamespace(view_bottle=object()),
        manager=SimpleNamespace(
            steam_manager=SimpleNamespace(is_steam_supported=True),
        ),
        update_library=lambda: captured.setdefault("updated", True),
        show_toast=lambda _message: None,
    )

    entry = ProgramEntry(
        window,
        steam_config(),
        {
            "name": "Example Game",
            "id": "steam:123",
            "steam": True,
        },
        is_steam=True,
    )

    assert entry.btn_add_steam_library.get_visible() is True
    assert entry.btn_add_steam_library.get_icon_name() == "library-symbolic"
    assert entry.btn_add_steam_library.get_tooltip_text() == "Add to Library"
    assert entry.btn_menu.get_visible() is False
    assert entry.btn_launch_steam.get_visible() is True

    entry.btn_add_steam_library.emit("clicked")

    assert captured["data"]["id"] == "steam:123"
    assert captured["data"]["steam"] is True
    assert captured["config"] is entry.config
    assert captured["updated"] is True


def test_program_widget_uses_library_icon(monkeypatch, tmp_path):
    icon_path = tmp_path / "program.svg"
    icon_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">'
        '<rect width="32" height="32" fill="#3584e4"/></svg>',
        encoding="utf-8",
    )

    class LibraryManager:
        @staticmethod
        def get_library():
            return {
                "entry-id": {
                    "id": "program-id",
                    "icon": str(icon_path),
                }
            }

    monkeypatch.setattr(program_module, "LibraryManager", LibraryManager)
    window = SimpleNamespace(
        page_details=SimpleNamespace(view_bottle=object()),
        manager=SimpleNamespace(
            steam_manager=SimpleNamespace(is_steam_supported=False),
        ),
    )

    entry = ProgramEntry(
        window,
        BottleConfig(Name="Games", Path="Games"),
        {
            "name": "Example Game",
            "id": "program-id",
            "path": "C:\\Example Game\\game.exe",
            "icon": "com.usebottles.bottles-program",
        },
        check_boot=False,
    )

    assert entry.img_program.get_icon_name() is None
    assert entry.img_program.get_paintable() is not None
    assert entry.btn_add_library.get_property("text") == "Remove from Library"
    assert entry.btn_add_library.get_visible() is True


def test_program_widget_extracts_its_own_icon(monkeypatch, tmp_path):
    icon_path = tmp_path / "icons" / "Example Game.png"
    icon_path.parent.mkdir()
    captured = {}

    class LibraryManager:
        @staticmethod
        def get_library():
            return {}

    def extract_icon(**kwargs):
        captured.update(kwargs)
        icon_path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">'
            '<rect width="32" height="32" fill="#3584e4"/></svg>',
            encoding="utf-8",
        )
        return str(icon_path)

    def run_async(task_func, callback, **kwargs):
        callback(task_func(**kwargs), None)

    config = BottleConfig(Name="Games", Path="Games")
    monkeypatch.setattr(program_module, "LibraryManager", LibraryManager)
    monkeypatch.setattr(program_module, "RunAsync", run_async)
    monkeypatch.setattr(program_module.ManagerUtils, "extract_icon", extract_icon)
    monkeypatch.setattr(
        program_module.ManagerUtils, "get_bottle_path", lambda _config: str(tmp_path)
    )
    window = SimpleNamespace(
        page_details=SimpleNamespace(view_bottle=object()),
        manager=SimpleNamespace(
            steam_manager=SimpleNamespace(is_steam_supported=False),
        ),
    )

    entry = ProgramEntry(
        window,
        config,
        {
            "name": "Example Game",
            "id": "program-id",
            "path": "C:\\Example Game\\game.exe",
            "icon": "com.usebottles.bottles-program",
        },
        check_boot=False,
    )

    assert captured["program_path"] == "C:\\Example Game\\game.exe"
    assert entry.program["icon"] == str(icon_path)
    assert entry.img_program.get_icon_name() is None
    assert entry.img_program.get_paintable() is not None


def test_library_entry_resolves_steam_game_without_wine_program():
    config = steam_config()
    data = {
        "bottle": {"name": "123", "path": config.Path},
        "name": "Example Game",
        "id": "steam:123",
        "steam": True,
    }
    entry = SimpleNamespace(
        entry=data,
        manager=SimpleNamespace(local_bottles={"123": config}),
        _LibraryEntry__remove_from_library=lambda: pytest.fail(
            "The Steam prefix is available"
        ),
    )

    entry.config = LibraryEntry._LibraryEntry__get_config(entry)
    program = LibraryEntry._LibraryEntry__get_program(entry)

    assert entry.config is config
    assert program is data


def test_library_stop_terminates_the_bottle(monkeypatch):
    calls = []
    button = SimpleNamespace(
        set_sensitive=lambda value: calls.append(("button", value))
    )
    entry = SimpleNamespace(
        is_umu=False,
        config=object(),
        program={"name": "Example Game", "executable": "game.exe"},
        window=SimpleNamespace(
            show_toast=lambda message: calls.append(("toast", message))
        ),
        btn_stop=button,
        _LibraryEntry__reset_buttons=lambda status: calls.append(("reset", status)),
    )

    class WineBoot:
        def __init__(self, config):
            assert config is entry.config

        @staticmethod
        def kill(force_if_stalled=False):
            calls.append(("kill", force_if_stalled))

    def run_async(task_func, callback, **kwargs):
        result = task_func(**kwargs)
        callback(result)

    monkeypatch.setattr(library_module, "WineBoot", WineBoot)
    monkeypatch.setattr(library_module, "RunAsync", run_async)

    LibraryEntry.stop_process(entry, None)

    assert ("button", False) in calls
    assert ("kill", True) in calls
    assert ("reset", True) in calls


def test_steam_library_widget_launches_through_steam():
    launched = []
    config = steam_config()
    data = {
        "bottle": {"name": "123", "path": config.Path},
        "name": "Example Game",
        "id": "steam:123",
        "steam": True,
    }
    manager = SimpleNamespace(
        local_bottles={"123": config},
        steam_manager=SimpleNamespace(launch_app=lambda appid: launched.append(appid)),
    )
    library = SimpleNamespace(
        window=SimpleNamespace(manager=manager),
        remove_entry=lambda _entry: None,
    )

    entry = LibraryEntry(library, "entry-uuid", data)

    assert entry.label_name.get_text() == "Example Game"
    assert entry.label_bottle.get_text() == "Steam"
    assert entry.btn_run.get_visible() is False
    assert entry.btn_launch_steam.get_visible() is True

    entry.btn_launch_steam.emit("clicked")

    assert launched == ["123"]


def test_umu_actions_keep_library_details_visible():
    revealed = []
    entry = SimpleNamespace(
        _LibraryEntry__pointer_inside=True,
        _LibraryEntry__umu_actions_popover=SimpleNamespace(
            get_visible=lambda: False
        ),
        revealer_details=SimpleNamespace(set_reveal_child=revealed.append),
    )
    entry._LibraryEntry__sync_details_revealer = lambda: (
        LibraryEntry._LibraryEntry__sync_details_revealer(entry)
    )

    LibraryEntry._LibraryEntry__on_motion_leave(entry)
    assert revealed[-1] is False

    entry._LibraryEntry__umu_actions_popover = SimpleNamespace(
        get_visible=lambda: True
    )
    LibraryEntry._LibraryEntry__on_umu_actions_visible(entry)
    LibraryEntry._LibraryEntry__on_motion_leave(entry)
    assert revealed[-1] is True

    entry._LibraryEntry__umu_actions_popover = SimpleNamespace(
        get_visible=lambda: False
    )
    LibraryEntry._LibraryEntry__on_umu_actions_visible(entry)
    assert revealed[-1] is False
