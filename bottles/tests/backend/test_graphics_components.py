from unittest.mock import Mock

import pytest

from bottles.backend.managers.manager import Manager
from bottles.backend.managers.registry_rule import RegistryRuleManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result


@pytest.fixture
def graphics_manager(monkeypatch, tmp_path):
    manager = object.__new__(Manager)
    manager.dxvk_available = ["dxvk-new"]
    manager.vkd3d_available = ["vkd3d-new"]
    manager.local_bottles = {}
    manager.steam_manager = Mock()
    manager.install_dll_component = Mock(return_value=Result(True))
    monkeypatch.setattr(RegistryRuleManager, "apply_rules", Mock())
    config = BottleConfig(
        Name="graphics",
        Path=str(tmp_path),
        Custom_Path=True,
        DXVK="dxvk-old",
        VKD3D="vkd3d-old",
    )
    config.Parameters.dxvk = True
    config.Parameters.vkd3d = False
    config.dump(str(tmp_path / "bottle.yml"))
    return manager, config, tmp_path / "bottle.yml"


@pytest.mark.parametrize("component", ["dxvk", "vkd3d"])
def test_failed_removal_preserves_enabled_config(graphics_manager, component):
    manager, config, path = graphics_manager
    setattr(config.Parameters, component, True)
    original = path.read_bytes()
    manager.install_dll_component.side_effect = [
        Result(False, message="remove failed"),
        Result(True),
    ]

    result = manager.set_graphics_component(config, component, False)

    assert not result.ok
    assert result.message == "remove failed"
    assert getattr(config.Parameters, component)
    assert path.read_bytes() == original
    assert manager.install_dll_component.call_args.kwargs["version"] == getattr(
        config, component.upper()
    )


def test_version_switch_failure_restores_old_version(graphics_manager):
    manager, config, path = graphics_manager
    original = path.read_bytes()
    manager.install_dll_component.side_effect = [
        Result(False, message="install failed"),
        Result(True),
    ]

    result = manager.set_graphics_component(config, "dxvk", True, "dxvk-new")

    assert not result.ok
    assert config.DXVK == "dxvk-old"
    assert config.Parameters.dxvk
    assert path.read_bytes() == original
    assert manager.install_dll_component.call_args.kwargs["version"] == "dxvk-old"


def test_save_failure_restores_components(graphics_manager, monkeypatch):
    manager, config, path = graphics_manager
    original = path.read_bytes()
    monkeypatch.setattr(
        BottleConfig, "dump", lambda *_args: Result(False, message="save failed")
    )

    result = manager.set_graphics_component(config, "dxvk", False)

    assert not result.ok
    assert result.message == "save failed"
    assert config.Parameters.dxvk
    assert path.read_bytes() == original
    assert manager.install_dll_component.call_args.kwargs["version"] == "dxvk-old"


def test_disabling_dxvk_disables_vkd3d_first(graphics_manager):
    manager, config, path = graphics_manager
    config.Parameters.vkd3d = True
    original = path.read_bytes()
    calls = []

    def remove(_config, component, **kwargs):
        assert config.Parameters.dxvk and config.Parameters.vkd3d
        assert path.read_bytes() == original
        calls.append(component)
        assert kwargs["remove"]
        return Result(True)

    manager.install_dll_component.side_effect = remove
    result = manager.set_graphics_component(config, "dxvk", False)

    assert result.ok
    assert calls == ["vkd3d", "dxvk"]
    assert not config.Parameters.dxvk
    assert not config.Parameters.vkd3d
    assert path.read_bytes() != original


def test_vkd3d_dependency_failure_does_not_install_vkd3d(graphics_manager):
    manager, config, path = graphics_manager
    config.Parameters.dxvk = False
    original = path.read_bytes()
    manager.install_dll_component.side_effect = [
        Result(False, message="dxvk failed"),
        Result(True),
    ]

    result = manager.set_graphics_component(config, "vkd3d", True, "vkd3d-new")

    assert not result.ok
    assert not config.Parameters.dxvk and not config.Parameters.vkd3d
    assert path.read_bytes() == original
    assert all(
        call.args[1] == "dxvk" for call in manager.install_dll_component.call_args_list
    )


def test_enabling_vkd3d_persists_dependency_once(graphics_manager, monkeypatch):
    manager, config, _path = graphics_manager
    config.Parameters.dxvk = False
    saved = []
    dump = BottleConfig.dump

    def save(candidate, path):
        saved.append(candidate.to_dict())
        return dump(candidate, path)

    monkeypatch.setattr(BottleConfig, "dump", save)
    result = manager.set_graphics_component(config, "vkd3d", True, "vkd3d-new")

    assert result.ok
    assert config.Parameters.dxvk and config.Parameters.vkd3d
    assert config.VKD3D == "vkd3d-new"
    assert len(saved) == 1
    assert saved[0]["Parameters"]["dxvk"] and saved[0]["Parameters"]["vkd3d"]


def test_rollback_failure_is_reported(graphics_manager):
    manager, config, _path = graphics_manager
    manager.install_dll_component.return_value = Result(False)

    result = manager.set_graphics_component(config, "dxvk", False)

    assert not result.ok
    assert result.message == "Failed to restore graphics components."
    assert config.Parameters.dxvk


def test_failed_update_restores_dlls_and_original_backups(
    graphics_manager, monkeypatch
):
    from bottles.backend.dlls import dll as dll_module
    from bottles.backend.dlls.dxvk import DXVKComponent
    from bottles.backend.utils.vulkan import VulkanUtils

    manager, config, path = graphics_manager
    component_root = path.parent / "components"
    system = path.parent / "drive_c/windows/system32"
    system.mkdir(parents=True)
    for version in ("dxvk-old", "dxvk-new"):
        for arch, names in DXVKComponent.dlls.items():
            directory = component_root / version / arch
            directory.mkdir(parents=True)
            for name in names:
                (directory / name).write_bytes(version.encode())
    (path.parent / "drive_c/windows/syswow64").mkdir()
    for name in DXVKComponent.dlls["x64"]:
        (system / name).write_bytes(b"custom-native")

    monkeypatch.setattr(
        DXVKComponent,
        "get_base_path",
        staticmethod(lambda version: str(component_root / version)),
    )
    monkeypatch.setattr(VulkanUtils, "check_support", lambda: True)
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: Result(True))
    manager.install_dll_component = lambda *args, **kwargs: (
        Manager.install_dll_component(manager, *args, **kwargs)
    )
    assert manager.install_dll_component(config, "dxvk").ok
    bundles = []

    def registry(_reg, bundle):
        bundles.append(bundle)
        return Result(len(bundles) != 1)

    monkeypatch.setattr(dll_module.Reg, "import_bundle", registry)
    original = path.read_bytes()
    result = manager.set_graphics_component(config, "dxvk", True, "dxvk-new")

    assert not result.ok
    assert config.DXVK == "dxvk-old"
    assert path.read_bytes() == original
    for name in DXVKComponent.dlls["x64"]:
        assert (system / name).read_bytes() == b"dxvk-old"
        assert (system / f"{name}.bck").read_bytes() == b"custom-native"
    assert len(bundles) == 2


def test_component_save_preserves_other_preferences_changed_while_pending(
    graphics_manager,
):
    manager, config, path = graphics_manager

    def install(*_args, **_kwargs):
        config.Parameters.gamemode = True
        return Result(True)

    manager.install_dll_component.side_effect = install
    result = manager.set_graphics_component(config, "dxvk", True, "dxvk-new")

    assert result.ok
    assert config.Parameters.gamemode
    assert BottleConfig.load(str(path)).data.Parameters.gamemode


@pytest.mark.parametrize("component", ["dxvk", "vkd3d"])
def test_missing_component_cache_is_not_reported_as_installed(
    monkeypatch, tmp_path, component
):
    from bottles.backend.dlls.dxvk import DXVKComponent
    from bottles.backend.dlls.vkd3d import VKD3DComponent
    from bottles.backend.utils.vulkan import VulkanUtils

    manager = object.__new__(Manager)
    manager.dxvk_available = []
    manager.vkd3d_available = []
    config = BottleConfig(DXVK="missing", VKD3D="missing")
    cls = DXVKComponent if component == "dxvk" else VKD3DComponent
    monkeypatch.setattr(
        cls, "get_base_path", staticmethod(lambda *_args: str(tmp_path / "missing"))
    )
    monkeypatch.setattr(VulkanUtils, "check_support", lambda: True)

    result = manager.install_dll_component(config, component)

    assert not result.ok
    assert (
        result.message
        == f"The selected {component.upper()} installation is incomplete."
    )
