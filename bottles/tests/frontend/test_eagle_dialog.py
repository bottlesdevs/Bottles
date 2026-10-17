# ruff: noqa: E402

import gc
import weakref
from types import SimpleNamespace
from unittest.mock import Mock

from gi.repository import Gio

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.frontend.views import bottle_details


def test_eagle_chooser_stays_alive_until_response(monkeypatch, tmp_path):
    dialogs = []
    gtk = bottle_details.Gtk

    def create_dialog(**kwargs):
        dialog = gtk.FileChooserNative.new(**kwargs)
        dialogs.append(weakref.ref(dialog))
        return dialog

    monkeypatch.setattr(
        bottle_details,
        "Gtk",
        SimpleNamespace(
            FileChooserNative=SimpleNamespace(new=create_dialog),
            FileChooserAction=gtk.FileChooserAction,
            ResponseType=gtk.ResponseType,
        ),
    )
    monkeypatch.setattr(
        bottle_details.ManagerUtils, "get_bottle_path", lambda _config: str(tmp_path)
    )
    view = SimpleNamespace(
        config=object(), window=gtk.Window(), analyze_with_eagle=Mock()
    )
    try:
        bottle_details.BottleView.run_eagle(view, None)
        gc.collect()
        dialog = dialogs[0]()
        assert dialog is not None
        dialog.emit("response", gtk.ResponseType.CANCEL)
        view.analyze_with_eagle.assert_not_called()
        dialog.destroy()
    finally:
        view.window.destroy()
