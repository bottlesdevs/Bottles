import os

import pytest

from bottles.backend.managers import manager as manager_module
from bottles.backend.managers.manager import Manager


@pytest.mark.parametrize("expose_home_drive", (True, False))
def test_create_bottle_applies_home_drive_after_wineboot(
    monkeypatch, tmp_path, expose_home_drive
):
    class Settings:
        @staticmethod
        def get_boolean(key):
            assert key == "disable-home-drive"
            return not expose_home_drive

        @staticmethod
        def get_string(key):
            assert key == "audio-driver"
            return "default"

    class WineBoot:
        def __init__(self, config):
            self.config = config

        def _create_home_drive(self):
            bottle_path = tmp_path / self.config.Path
            dosdevices = bottle_path / "dosdevices"
            dosdevices.mkdir(exist_ok=True)
            home_drive = dosdevices / "z:"
            if not os.path.lexists(home_drive):
                home_drive.symlink_to(tmp_path, target_is_directory=True)

        def init(self):
            self._create_home_drive()

        def update(self):
            self._create_home_drive()

    class RegKeys:
        def __init__(self, _config):
            pass

        def apply_cmd_settings(self):
            pass

        def apply_font_smoothing(self):
            pass

    class Reg:
        def __init__(self, _config):
            pass

        def add(self, **_kwargs):
            pass

    manager = object.__new__(Manager)
    manager.settings = Settings()
    manager.runners_available = ["soda-11.0"]
    manager.dxvk_available = ["dxvk-2.7"]
    manager.vkd3d_available = ["vkd3d-3.0"]
    manager.nvapi_available = ["nvapi-1.0"]
    manager.latencyflex_available = ["latencyflex-1.0"]

    monkeypatch.setattr(manager_module.Paths, "bottles", str(tmp_path))
    monkeypatch.setattr(manager_module.FileUtils, "chattr_f", lambda _path: None)
    monkeypatch.setattr(
        manager_module.FileUtils,
        "wait_for_files",
        lambda _paths, **_kwargs: True,
    )
    monkeypatch.setattr(
        manager_module.TemplateManager,
        "get_env_template",
        lambda _environment: None,
    )
    monkeypatch.setattr(
        manager_module.TemplateManager, "new", lambda _environment, _config: None
    )
    monkeypatch.setattr(manager_module, "Reg", Reg)
    monkeypatch.setattr(manager_module, "RegKeys", RegKeys)
    monkeypatch.setattr(manager_module, "WineBoot", WineBoot)
    monkeypatch.setattr(manager_module, "WineServer", lambda _config: object())

    result = Manager.create_bottle(
        manager,
        name="Default Drives",
        environment="custom",
        runner="soda-11.0",
        dxvk="dxvk-2.7",
        vkd3d="vkd3d-3.0",
        nvapi="nvapi-1.0",
        latencyflex="latencyflex-1.0",
    )

    home_drive = tmp_path / "Default-Drives" / "dosdevices" / "z:"
    assert result.ok
    assert os.path.lexists(home_drive) is expose_home_drive
