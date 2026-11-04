from types import SimpleNamespace
from unittest.mock import Mock

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk

from bottles.backend.managers.playtime import ProcessSessionTracker, _compute_program_id
from bottles.frontend.utils.playtime import PlaytimeService

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.frontend.windows.playtimegraph import PlaytimeGraphDialog


def test_reset_invalidates_the_shared_program_cache(tmp_path):
    tracker = ProcessSessionTracker(db_path=str(tmp_path / "playtime.sqlite"))
    try:
        path = str(tmp_path / "drive_c/game.exe")
        session = tracker.start_session(
            bottle_id="test", bottle_name="test", bottle_path=str(tmp_path),
            program_name="Game", program_path=path,
        )
        tracker.mark_exit(session)
        manager = SimpleNamespace(playtime_tracker=tracker)
        service = manager.playtime_service = PlaytimeService(manager)
        record = service.get_program_playtime("test", str(tmp_path), "Game", path)
        assert record is not None
        program_id = _compute_program_id("test", str(tmp_path), path)
        parent = SimpleNamespace(manager=manager, update_playtime=Mock())
        dialog = SimpleNamespace(
            bottle_id="test", program_id=program_id, program_name="Game", parent=parent,
            current_week_offset=-1, _PlaytimeGraphDialog__load_data=Mock(),
        )

        PlaytimeGraphDialog._PlaytimeGraphDialog__on_reset_confirmed(dialog, None, "reset")

        assert service.cache.get("test", program_id) is None
        assert service.get_program_playtime("test", str(tmp_path), "Game", path) is None
        parent.update_playtime.assert_called_once_with(service)
        assert dialog.current_week_offset == 0
    finally:
        tracker.shutdown()


def test_reset_dialog_cancel_preserves_stats_and_confirm_clears_them(tmp_path):
    tracker = ProcessSessionTracker(db_path=str(tmp_path / "playtime.sqlite"))
    Adw.init()
    window = Gtk.Window()
    dialog = None
    try:
        path = str(tmp_path / "drive_c/game.exe")
        session = tracker.start_session(
            bottle_id="test", bottle_name="test", bottle_path=str(tmp_path),
            program_name="Game", program_path=path,
        )
        tracker.mark_exit(session)
        program_id = _compute_program_id("test", str(tmp_path), path)
        manager = SimpleNamespace(playtime_tracker=tracker)
        window.manager = manager
        parent = SimpleNamespace(window=window, manager=manager, update_playtime=Mock())
        dialog = PlaytimeGraphDialog(parent, "Game", program_id, "test")

        dialog.btn_reset.emit("clicked")
        confirmation = next(w for w in Gtk.Window.get_toplevels() if isinstance(w, Adw.MessageDialog))
        confirmation.response("cancel")
        assert tracker.get_totals("test", program_id) is not None
        parent.update_playtime.assert_not_called()

        dialog.btn_reset.emit("clicked")
        confirmation = next(w for w in Gtk.Window.get_toplevels() if isinstance(w, Adw.MessageDialog))
        confirmation.response("reset")
        assert tracker.get_totals("test", program_id) is None
        parent.update_playtime.assert_called_once()
    finally:
        if dialog is not None:
            dialog.destroy()
        window.destroy()
        tracker.shutdown()
