# ruff: noqa: E402

import time
from types import SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

Adw.init()
Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.frontend.windows.display import DisplayDialog, RegKeys


@pytest.mark.parametrize(("mode", "success"), [(0, True), (1, True), (2, True), (1, False)])
def test_display_saves_dpi_scaling_only_after_the_registry_update(monkeypatch, mode, success):
    config = BottleConfig()
    window = Adw.Window()
    window.show_toast = Mock()

    def save(**kwargs):
        assert kwargs["key"] == "dpi_scaling"
        setattr(config.Parameters, kwargs["key"], kwargs["value"])
        return Result(True, {"config": config})

    window.manager = SimpleNamespace(update_config=Mock(side_effect=save))
    queue = SimpleNamespace(add_task=Mock(), end_task=Mock())
    spinner = Gtk.Spinner()
    button = Gtk.Button()
    dialog = DisplayDialog(window, config, None, queue, button, spinner)
    registry = Mock(return_value=Result(success, message="Registry failed"))
    monkeypatch.setattr(RegKeys, "set_dpi_scaling", registry)
    dialog.combo_dpi_scaling.set_selected(mode)
    dialog.btn_save.emit("clicked")
    context = GLib.MainContext.default()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if mode == 0 or queue.end_task.called:
            break
        time.sleep(0.01)
    if mode == 0:
        registry.assert_not_called()
        window.manager.update_config.assert_not_called()
    else:
        expected = "application" if mode == 1 else "system"
        registry.assert_called_once_with(mode=expected)
        queue.end_task.assert_called_once()
        assert button.get_sensitive()
        assert not spinner.get_spinning()
        if success:
            assert config.Parameters.dpi_scaling == expected
            window.manager.update_config.assert_called_once()
        else:
            assert config.Parameters.dpi_scaling == "default"
            window.manager.update_config.assert_not_called()
            assert window.show_toast.call_args.args == ("Some display settings could not be updated.",)
    dialog.destroy()
    window.destroy()
