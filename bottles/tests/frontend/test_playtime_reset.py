from types import SimpleNamespace
from unittest.mock import Mock

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gio

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
