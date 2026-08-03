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
