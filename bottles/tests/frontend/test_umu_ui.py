# ruff: noqa: E402

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from gi.repository import Adw, Gio, Gtk

from bottles.backend.umu import UmuDatabaseEntry

resource_path = Path(
    os.environ.get("BOTTLES_TEST_RESOURCE", "/app/share/bottles/bottles.gresource")
)
if not resource_path.exists():
    pytest.skip(
        "UMU frontend tests require the Bottles resource bundle",
        allow_module_level=True,
    )
Gio.resources_register(Gio.Resource.load(str(resource_path)))

from bottles.frontend.views.list import BottleView
from bottles.frontend.widgets.umu import UmuPrefixRow
from bottles.frontend.windows import umu as umu_module
from bottles.frontend.windows.umu import UmuDependencyDialog, UmuSearchDialog
from bottles.frontend.windows.window import BottlesWindow


def _descendants(widget):
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _descendants(child)
        child = child.get_next_sibling()


def test_empty_umu_row_only_offers_install():
    calls = []

    def unexpected_probe():
        pytest.fail("the UMU launcher must not be probed while building the list")

    view = SimpleNamespace(
        window=SimpleNamespace(
            manager=SimpleNamespace(get_umu_installation=unexpected_probe),
            show_umu_search=lambda *args: calls.append(args),
        )
    )

    row = BottleView._BottleView__build_umu_empty_row(view)
    buttons = [widget for widget in _descendants(row) if isinstance(widget, Gtk.Button)]

    assert row.get_subtitle() == "Install a Windows game to create one."
    assert len(buttons) == 1
    assert isinstance(buttons[0].get_child(), Adw.ButtonContent)
    assert buttons[0].get_child().get_label() == "Install Game"
    buttons[0].emit("clicked")
    assert calls == [(buttons[0],)]


def test_detected_prefix_row_passes_full_entry_to_setup():
    entry = {
        "source": "umu",
        "source_id": "/home/user/Games/umu/game",
        "name": "game",
        "path": "/home/user/Games/umu/game",
        "state": "detected",
        "detected": True,
    }
    calls = []
    row = UmuPrefixRow(entry, calls.append)

    row._UmuPrefixRow__show_settings()

    assert calls == [entry]
    assert row.label_state.get_label() == "Setup Required"
    assert row.label_state.get_tooltip_text() == (
        "Select the game identity and executable to complete setup."
    )
    assert row.get_subtitle() == (
        "Select the game identity and executable to complete setup."
    )
    labels = [
        widget.get_label()
        for widget in _descendants(row)
        if isinstance(widget, Gtk.Label)
    ]
    icons = [
        widget.get_icon_name()
        for widget in _descendants(row)
        if isinstance(widget, Gtk.Image)
    ]
    assert "UMU" not in labels
    assert "Detected" not in labels
    assert "go-next-symbolic" not in icons


def test_detected_prefix_opens_database_search():
    calls = []
    window = SimpleNamespace(
        show_umu_search=lambda **kwargs: calls.append(kwargs),
    )

    BottlesWindow.show_umu_detected_prefix(
        window,
        {"path": "/home/user/Games/umu/game"},
    )

    assert calls == [{"detected_prefix": "/home/user/Games/umu/game"}]


def test_database_selection_preserves_identity_and_detected_prefix(monkeypatch):
    calls = []
    entry = UmuDatabaseEntry(
        title="Baldur's Gate 3",
        store="gog",
        codename="1456460669",
        umu_id="umu-1086940",
    )

    class Dialog:
        def __init__(self, window, **kwargs):
            calls.append((window, kwargs))

        def present(self, parent):
            calls.append(("present", parent))

    monkeypatch.setattr(umu_module, "UmuAddGameDialog", Dialog)
    window = object()
    search = SimpleNamespace(
        window=window,
        detected_prefix="/home/user/Games/umu/game",
        close=lambda: calls.append("closed"),
    )

    UmuSearchDialog._UmuSearchDialog__select(search, None, entry)

    assert calls == [
        "closed",
        (
            window,
            {
                "mode": "detected",
                "detected_prefix": "/home/user/Games/umu/game",
                "database_entry": entry,
            },
        ),
        ("present", window),
    ]


def test_database_selection_opens_install_wizard(monkeypatch):
    calls = []
    entry = UmuDatabaseEntry(
        title="PKHeX",
        store="none",
        codename="pkhex",
        umu_id="umu-pkhex",
    )

    class Dialog:
        def __init__(self, window, database_entry):
            calls.append((window, database_entry))

        def present(self, parent):
            calls.append(("present", parent))

    monkeypatch.setattr(umu_module, "UmuInstallDialog", Dialog)
    window = object()
    search = SimpleNamespace(
        window=window,
        detected_prefix=None,
        close=lambda: calls.append("closed"),
    )

    UmuSearchDialog._UmuSearchDialog__select(search, None, entry)

    assert calls == ["closed", (window, entry), ("present", window)]


def test_custom_installer_opens_install_wizard(monkeypatch):
    calls = []

    class Dialog:
        def __init__(self, window):
            calls.append(window)

        def present(self, parent):
            calls.append(("present", parent))

    monkeypatch.setattr(umu_module, "UmuInstallDialog", Dialog)
    window = object()
    search = SimpleNamespace(
        window=window,
        close=lambda: calls.append("closed"),
    )

    UmuSearchDialog._UmuSearchDialog__custom(search, None, "install")

    assert calls == ["closed", window, ("present", window)]


def test_add_game_prefix_button_opens_folder_selection(monkeypatch):
    calls = []

    class Catalog:
        @staticmethod
        def list_choices(**_kwargs):
            return []

    window = SimpleNamespace(
        manager=SimpleNamespace(
            umu_repository=object(),
            umu_proton_catalog=Catalog(),
        ),
        settings=SimpleNamespace(get_string=lambda _key: "GE-Proton"),
    )
    monkeypatch.setattr(
        umu_module.UmuAddGameDialog,
        "_UmuAddGameDialog__choose_prefix",
        lambda *_args: calls.append("prefix"),
    )

    dialog = umu_module.UmuAddGameDialog(window, mode="import")
    dialog.btn_prefix.emit("clicked")

    assert calls == ["prefix"]


def test_umu_dependency_dialog_installs_without_a_second_step(monkeypatch):
    calls = []
    game = SimpleNamespace(id="game-id", extra={})
    updated_game = SimpleNamespace(id="game-id", extra={"dependency_tool": "bottles"})

    class Check:
        def __init__(self, active):
            self.active = active

        def get_active(self):
            return self.active

    class InstallDialog:
        def __init__(self, parent, title):
            calls.append(("dialog", parent, title))
            self.add_step = calls.append
            self.update_progress = calls.append

        def present(self):
            calls.append("presented")

        def finish(self, success, message):
            calls.append(("finished", success, message))

    class Repository:
        def load(self, game_id):
            assert game_id == game.id
            return game

        def update(self, current, **changes):
            calls.append(("updated", current, changes))
            return updated_game

    class Manager:
        umu_repository = Repository()

        def install_umu_dependencies(self, current, names, **callbacks):
            calls.append(("installed", current, names, sorted(callbacks)))
            return SimpleNamespace(status=True, data=updated_game, message="")

    window = SimpleNamespace(
        manager=Manager(),
        show_toast=lambda message: calls.append(("toast", message)),
    )
    dialog = SimpleNamespace(
        rows=[
            SimpleNamespace(_umu_name="dotnet", _umu_check=Check(True)),
            SimpleNamespace(_umu_name="vcredist", _umu_check=Check(False)),
        ],
        window=window,
        game=game,
        callback=lambda current: calls.append(("callback", current)),
        close=lambda: calls.append("closed"),
    )

    monkeypatch.setattr(umu_module, "DependencyInstallDialog", InstallDialog)
    monkeypatch.setattr(
        umu_module,
        "RunAsync",
        lambda task_func, callback: callback(task_func()),
    )

    UmuDependencyDialog._UmuDependencyDialog__install(dialog)

    assert (
        "installed",
        updated_game,
        ("dotnet",),
        ["progress_cb", "progress_progress_cb"],
    ) in calls
    assert ("callback", updated_game) in calls
    assert ("finished", True, "1 dependency installed.") in calls
