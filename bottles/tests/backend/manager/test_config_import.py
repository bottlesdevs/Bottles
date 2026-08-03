from bottles.backend.managers import manager as manager_module
from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig, BottleParams


def test_config_import_restores_runtime_settings(monkeypatch, tmp_path):
    applied_settings = []
    windows_versions = []
    wineboot_inits = []

    class Settings:
        @staticmethod
        def get_boolean(key):
            assert key == "disable-home-drive"
            return False

        @staticmethod
        def get_string(key):
            assert key == "audio-driver"
            return "default"

    class WineBoot:
        def __init__(self, _config):
            pass

        def init(self):
            wineboot_inits.append(True)

        def update(self):
            pass

    class WineServer:
        def __init__(self, _config):
            pass

        @staticmethod
        def is_alive():
            return False

    class Reg:
        def __init__(self, _config):
            pass

        def add(self, **_kwargs):
            pass

    class RegKeys:
        def __init__(self, _config):
            pass

        @staticmethod
        def lg_set_windows(version):
            windows_versions.append(version)

        def apply_cmd_settings(self):
            pass

        def apply_font_smoothing(self):
            pass

        @staticmethod
        def toggle_virtual_desktop(state, resolution):
            applied_settings.append(("virtual_desktop", state, resolution))

        @staticmethod
        def toggle_wayland_driver(state):
            applied_settings.append(("wayland", state))

        @staticmethod
        def set_renderer(value):
            applied_settings.append(("renderer", value))

        @staticmethod
        def set_dpi(value):
            applied_settings.append(("dpi", value))

        @staticmethod
        def set_grab_fullscreen(state):
            applied_settings.append(("fullscreen_capture", state))

        @staticmethod
        def set_take_focus(state):
            applied_settings.append(("take_focus", state))

        @staticmethod
        def set_decorated(state):
            applied_settings.append(("decorated", state))

        @staticmethod
        def set_mouse_warp(state):
            applied_settings.append(("mouse_warp", state))

    manager = object.__new__(Manager)
    manager.settings = Settings()
    manager.runners_available = ["soda-11.0"]
    manager.dxvk_available = ["dxvk-2.7"]
    manager.vkd3d_available = ["vkd3d-3.0"]
    manager.nvapi_available = ["nvapi-1.0"]
    manager.latencyflex_available = ["latencyflex-1.0"]
    manager.supported_dependencies = {}
    manager.update_bottles = lambda **_kwargs: None
    source = BottleConfig(
        Name="Imported",
        Runner="soda-11.0",
        DXVK="dxvk-2.7",
        VKD3D="vkd3d-3.0",
        NVAPI="nvapi-1.0",
        LatencyFleX="latencyflex-1.0",
        Environment="Gaming",
        Windows="win7",
        Language="ja_JP",
        Environment_Variables={"GAME_MODE": "1"},
        Parameters=BottleParams(
            virtual_desktop=True,
            virtual_desktop_res="1024x768",
            wayland=True,
            renderer="vulkan",
            custom_dpi=144,
            fullscreen_capture=True,
            take_focus=True,
            decorated=False,
            mouse_warp=False,
            sync="esync",
        ),
    )

    (tmp_path / "Imported").mkdir()
    monkeypatch.setattr(manager_module.Paths, "bottles", str(tmp_path))
    monkeypatch.setattr(manager_module.random, "randint", lambda *_args: 123)
    monkeypatch.setattr(manager_module.FileUtils, "chattr_f", lambda _path: None)
    monkeypatch.setattr(
        manager_module.FileUtils, "wait_for_files", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(
        manager_module.TemplateManager,
        "get_env_template",
        lambda _environment: (_ for _ in ()).throw(
            AssertionError("configuration imports must not use an environment template")
        ),
    )
    monkeypatch.setattr(manager_module.TemplateManager, "new", lambda *_args: None)
    monkeypatch.setattr(
        manager_module.WineUtils, "ensure_user_profile_alias", lambda _: True
    )
    monkeypatch.setattr(
        manager_module.WineUtils, "unlink_user_profile_links", lambda _: True
    )
    monkeypatch.setattr(manager_module, "WineBoot", WineBoot)
    monkeypatch.setattr(manager_module, "WineServer", WineServer)
    monkeypatch.setattr(manager_module, "Reg", Reg)
    monkeypatch.setattr(manager_module, "RegKeys", RegKeys)

    result = Manager.create_bottle_from_config(manager, source)

    restored = BottleConfig.load(str(tmp_path / "Imported__123" / "bottle.yml")).data
    assert result is True
    assert restored.Name == "Imported__123"
    assert restored.Path == "Imported__123"
    assert restored.Runner == "soda-11.0"
    assert restored.Windows == "win7"
    assert restored.Language == "ja_JP"
    assert restored.Environment_Variables == {"GAME_MODE": "1"}
    assert restored.Parameters.decorated is False
    assert restored.Parameters.sync == "esync"
    assert applied_settings == [
        ("virtual_desktop", True, "1024x768"),
        ("wayland", True),
        ("renderer", "vulkan"),
        ("dpi", 144),
        ("fullscreen_capture", True),
        ("take_focus", True),
        ("decorated", False),
        ("mouse_warp", 0),
    ]
    assert windows_versions == ["win7"]
    assert wineboot_inits == [True]
