# ruff: noqa: E402

from types import SimpleNamespace
from unittest.mock import Mock

from gi.repository import Gio

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
