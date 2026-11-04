import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gio

Gio.resources_register(Gio.Resource.load(os.environ.get(
    "BOTTLES_TEST_RESOURCE", "/app/share/bottles/bottles.gresource",
)))
from bottles.frontend.windows import umu


@pytest.fixture
def selection(monkeypatch):
    selected = SimpleNamespace(path="")
    class Dialog:
        def __init__(self, **kwargs):
            pass
        def open(self, window, callback):
            callback(self, None)
        def select_folder(self, window, callback):
            callback(self, None)
        def open_finish(self, result):
            return Gio.File.new_for_path(selected.path)
        select_folder_finish = open_finish
    monkeypatch.setattr(umu.Gtk, "FileDialog", Dialog)
    return selected


def _view(prefix, executable=None):
    return SimpleNamespace(
        prefix=str(prefix), executable=executable, prefix_managed=False,
        game=SimpleNamespace(extra={"source_mode": "imported"}),
        window=SimpleNamespace(show_toast=Mock()),
        combo_mode=SimpleNamespace(get_selected=lambda: 1),
        entry_name=SimpleNamespace(get_text=lambda: "Game"),
        row_executable=Mock(), row_prefix=Mock(),
        _UmuAddGameDialog__validate=Mock(),
        _UmuGameDialog__validate_settings=Mock(),
    )


@pytest.mark.parametrize("dialog", [umu.UmuAddGameDialog, umu.UmuGameDialog])
def test_umu_accepts_an_executable_outside_the_prefix(tmp_path, selection, dialog):
    prefix = tmp_path / "Prefix"
    prefix.mkdir()
    executable = tmp_path / "Game Files" / "Game.EXE"
    executable.parent.mkdir()
    executable.write_bytes(b"MZfixture")
    selection.path = str(executable)
    view = _view(prefix)

    getattr(dialog, f"_{dialog.__name__}__choose_executable")(view)

    assert view.executable == str(executable)
    view.window.show_toast.assert_not_called()


@pytest.mark.parametrize("dialog", [umu.UmuAddGameDialog, umu.UmuGameDialog])
def test_umu_prefix_change_keeps_the_selected_executable(tmp_path, selection, dialog):
    executable = tmp_path / "Game Files" / "Game.exe"
    chosen = tmp_path / "New Prefix"
    chosen.mkdir()
    view = _view(tmp_path / "Old Prefix", str(executable))
    selection.path = str(chosen)

    getattr(dialog, f"_{dialog.__name__}__choose_prefix")(view)

    assert view.executable == str(executable)
    assert view.prefix == str(chosen)
    view.window.show_toast.assert_not_called()


@pytest.mark.parametrize("dialog", [umu.UmuAddGameDialog, umu.UmuGameDialog])
def test_umu_still_rejects_an_invalid_windows_executable(tmp_path, selection, dialog):
    executable = tmp_path / "invalid.exe"
    executable.write_bytes(b"not a Windows executable")
    selection.path = str(executable)
    view = _view(tmp_path / "Prefix")

    getattr(dialog, f"_{dialog.__name__}__choose_executable")(view)

    assert view.executable is None
    view.window.show_toast.assert_called_once()
