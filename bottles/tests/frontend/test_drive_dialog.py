import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from gi.repository import Gio

from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result

resource_path = Path(
    os.environ.get("BOTTLES_TEST_RESOURCE", "/app/share/bottles/bottles.gresource")
)
if not resource_path.exists():
    pytest.skip(
        "Drive tests require the Bottles Flatpak runtime",
        allow_module_level=True,
    )
Gio.resources_register(Gio.Resource.load(str(resource_path)))


def test_device_drive_shows_eject_action(tmp_path):
    from bottles.frontend.windows.drives import DriveEntry

    dosdevices = tmp_path / "dosdevices"
    dosdevices.mkdir()
    (dosdevices / "d:").symlink_to(tmp_path)
    (dosdevices / "d::").symlink_to("/dev/sr0")
    config = BottleConfig(Path=str(tmp_path), Custom_Path=str(tmp_path))
    parent = SimpleNamespace(
        config=config,
        window=SimpleNamespace(manager=Mock()),
    )

    entry = DriveEntry(parent, ["D", str(tmp_path)])

    assert entry.btn_eject.get_visible() is True


def test_drive_entry_runs_wine_eject(monkeypatch):
    from bottles.frontend.windows import drives as drives_module
    from bottles.frontend.windows.drives import DriveEntry

    config = BottleConfig()
    calls = []

    class FakeEject:
        def __init__(self, received_config):
            assert received_config is config

        def cdrom(self, drive):
            calls.append(drive)
            return Result(True)

    def run_async(task_func, callback, **kwargs):
        callback(task_func(**kwargs), None)

    monkeypatch.setattr(drives_module, "Eject", FakeEject)
    monkeypatch.setattr(drives_module, "RunAsync", run_async)
    entry = SimpleNamespace(
        config=config,
        drive=["D", "/run/media/disc"],
        btn_eject=Mock(),
        parent=SimpleNamespace(window=SimpleNamespace(show_toast=Mock())),
    )

    DriveEntry._DriveEntry__eject(entry)

    assert calls == ["D:"]
    assert entry.btn_eject.set_sensitive.call_args_list == [call(False), call(True)]
    entry.parent.window.show_toast.assert_called_once()
