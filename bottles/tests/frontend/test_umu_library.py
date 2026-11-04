import os
from types import SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

Gio.resources_register(Gio.Resource.load(os.environ.get(
    "BOTTLES_TEST_RESOURCE", "/app/share/bottles/bottles.gresource",
)))
from bottles.frontend.widgets import library


@pytest.mark.parametrize("error", [False, True])
def test_umu_launch_shows_download_status_until_launch_finishes(monkeypatch, error):
    callbacks = {}
    executor = Mock()
    executor.status_for.return_value = "downloading"
    entry = SimpleNamespace(
        game=SimpleNamespace(state="ready", name="Game"),
        manager=SimpleNamespace(get_umu_executor=lambda: executor),
        window=SimpleNamespace(show_toast=Mock()),
        label_source=Gtk.Label(label="UMU"),
        btn_remove=Mock(), btn_stop=Mock(), btn_run=Mock(),
        _LibraryEntry__reset_buttons=Mock(),
    )
    def timeout_add(_interval, callback):
        callbacks["poll"] = callback
        return 42
    def run_async(run, callback):
        callbacks["complete"] = callback
    monkeypatch.setattr(library.GLib, "timeout_add", timeout_add)
    remove = Mock()
    monkeypatch.setattr(library.GLib, "source_remove", remove)
    monkeypatch.setattr(library, "RunAsync", run_async)

    library.LibraryEntry._LibraryEntry__run_umu(entry)

    assert callbacks["poll"]() == library.GLib.SOURCE_CONTINUE
    assert entry.label_source.get_text() == "Downloading..."
    assert callbacks["poll"]() == library.GLib.SOURCE_CONTINUE
    assert entry.label_source.get_text() == "Downloading..."
    executor.status_for.return_value = "preparing"
    callbacks["poll"]()
    assert entry.label_source.get_text() == "Preparing..."
    if not error:
        executor.status_for.return_value = "running"
        assert callbacks["poll"]() == library.GLib.SOURCE_REMOVE
        assert entry.label_source.get_text() == "UMU"

    callbacks["complete"](0, error)

    assert entry.label_source.get_text() == "UMU"
    entry._LibraryEntry__reset_buttons.assert_called_once_with(True)
    if error:
        remove.assert_called_once_with(42)
        assert entry.window.show_toast.call_args.args == ("The game could not be started.",)
    else:
        remove.assert_not_called()
