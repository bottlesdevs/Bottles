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
from bottles.frontend.views import bottle_details
from bottles.frontend.views.bottle_details import BottleView
from bottles.frontend.widgets import program as program_module
from bottles.frontend.widgets.library import LibraryEntry
from bottles.frontend.widgets.program import ProgramEntry


class Button:
    def __init__(self):
        self.visible = True

    def set_visible(self, visible):
        self.visible = visible


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
    assert add_button.visible is False
    assert steam_add_button.visible is False


def test_regular_program_library_entry_is_unchanged(monkeypatch):
    captured = {}

    class LibraryManager:
        def add_to_library(self, data, config):
            captured["data"] = data
            captured["config"] = config

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
