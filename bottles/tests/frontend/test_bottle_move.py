# ruff: noqa: E402

import time
from types import SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
from gi.repository import Adw, Gio, GLib, Gtk

Adw.init()
Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.backend.globals import Paths
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils import yaml
from bottles.frontend.views import bottle_details


def wait_for(predicate):
    deadline = time.monotonic() + 5
    context = GLib.MainContext.default()
    while not predicate() and time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)
    return predicate()


@pytest.mark.parametrize("response", ["move", "cancel", "failure"])
def test_move_requires_confirmation_and_restores_the_window(tmp_path, monkeypatch, response):
    root = tmp_path / "Bottles"
    source = root / "Source"
    (source / "drive_c").mkdir(parents=True)
    (source / "drive_c/document.txt").write_text("Document")
    config = BottleConfig(Name="Source", Path="Source", Custom_Path=False)
    config.dump(str(source / "bottle.yml"))
    destination = tmp_path / "External"
    destination.mkdir()
    monkeypatch.setattr(Paths, "bottles", str(root))
    monkeypatch.setattr(bottle_details.WineServer, "is_alive", lambda self: response == "failure")
    window = Adw.Window()
    window.show_toast = Mock()
    updated = Mock()
    view = SimpleNamespace(window=window, config=config, manager=SimpleNamespace(update_bottles=updated), set_config=Mock())

    class Picker:
        def set_title(self, title):
            pass

        def select_folder(self, parent, callback):
            self.callback = callback

        def select_folder_finish(self, result):
            return Gio.File.new_for_path(str(destination))

    picker = Picker()
    monkeypatch.setattr(Gtk.FileDialog, "new", lambda: picker)
    bottle_details.BottleView._BottleView__move(view, None)
    picker.callback(picker, None)
    confirmation = next(w for w in Gtk.Window.list_toplevels() if isinstance(w, Adw.MessageDialog))
    assert (source / "drive_c/document.txt").exists()
    assert not list(destination.iterdir())
    confirmation.response("cancel" if response == "cancel" else "move")
    if response == "cancel":
        assert (source / "drive_c/document.txt").exists()
        updated.assert_not_called()
    else:
        assert wait_for(lambda: window.show_toast.called)
        assert window.get_sensitive()
        if response == "failure":
            updated.assert_not_called()
            assert (source / "drive_c/document.txt").exists()
        else:
            updated.assert_called_once()
            view.set_config.assert_called_once_with(config)
            assert (destination / "Source/drive_c/document.txt").read_text() == "Document"
            assert yaml.load((source / "placeholder.yml").read_text())["Path"] == str(destination / "Source")
    window.destroy()
