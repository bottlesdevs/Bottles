# ruff: noqa: E402

from types import SimpleNamespace
from unittest.mock import Mock

from gi.repository import Adw, Gio, GLib, Gtk
from bottles.backend.models.config import BottleConfig

bottles_resource = Gio.Resource.load("/app/share/bottles/bottles.gresource")
bottles_resource._register()

from bottles.frontend.windows import drives


def test_missing_c_drive_is_not_available(monkeypatch):
    dialog = SimpleNamespace(
        config=object(),
        _DrivesDialog__alphabet="ABC",
        str_list_letters=Mock(),
        btn_save=Mock(),
        list_drives=Mock(),
    )
    monkeypatch.setattr(
        drives,
        "Drives",
        lambda _config: SimpleNamespace(get_all=lambda: {}),
    )

    drives.DrivesDialog._DrivesDialog__populate_combo_and_drives(dialog)

    assert [
        call.args[0] for call in dialog.str_list_letters.append.call_args_list
    ] == ["A", "B"]


def test_removed_drive_letter_can_be_added_without_reopening(monkeypatch, tmp_path):
    Adw.init()
    devices = tmp_path / "dosdevices"
    devices.mkdir()
    (devices / "p:").symlink_to(tmp_path)
    rows = []
    entry_type = drives.DriveEntry

    def create_entry(*args, **kwargs):
        entry = entry_type(*args, **kwargs)
        rows.append(entry)
        return entry

    def drain():
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

    monkeypatch.setattr(drives, "DriveEntry", create_entry)
    window = Gtk.Window()
    window.manager = Mock()
    dialog = drives.DrivesDialog(
        window, BottleConfig(Path=str(tmp_path), Custom_Path=True)
    )
    try:
        drain()
        rows[0].btn_remove.emit("clicked")
        letters = [
            dialog.str_list_letters.get_string(i)
            for i in range(dialog.str_list_letters.get_n_items())
        ]
        assert "P" in letters
        assert not (devices / "p:").exists()

        dialog.combo_letter.set_selected(letters.index("P"))
        dialog.btn_save.emit("clicked")
        drain()

        assert rows[1].get_title() == "P"
        assert "P" not in [
            dialog.str_list_letters.get_string(i)
            for i in range(dialog.str_list_letters.get_n_items())
        ]
    finally:
        dialog.destroy()
        window.destroy()
