import os

from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.drives import Drives


def test_device_backed_drive_is_ejectable(tmp_path):
    dosdevices = tmp_path / "dosdevices"
    dosdevices.mkdir()
    (dosdevices / "d:").symlink_to(tmp_path)
    (dosdevices / "d::").symlink_to("/dev/sr0")
    config = BottleConfig(Path=str(tmp_path), Custom_Path=str(tmp_path))
    drives = Drives(config)

    assert drives.is_ejectable("D") is True
    assert drives.is_ejectable("E:") is False


def test_set_drive_path_replaces_broken_symlink(tmp_path):
    bottle_path = tmp_path / "bottle"
    dosdevices_path = bottle_path / "dosdevices"
    dosdevices_path.mkdir(parents=True)
    drive_path = dosdevices_path / "h:"
    drive_path.symlink_to("/missing/portal/path", target_is_directory=True)

    config = BottleConfig(
        Name="Test",
        Path=str(bottle_path),
        Custom_Path=True,
    )

    Drives(config).set_drive_path("H", "/home/test/Games")

    assert drive_path.is_symlink()
    assert os.readlink(drive_path) == "/home/test/Games"
