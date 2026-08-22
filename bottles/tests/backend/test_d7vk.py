import pytest

from bottles.backend.dlls import dll as dll_module
from bottles.backend.dlls.d7vk import D7VKComponent
from bottles.backend.managers import manager as manager_module
from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.utils.vulkan import VulkanUtils


def test_d7vk_preserves_wine_ddraw_for_win64(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    component_dll = component_path / "x32/ddraw.dll"
    component_dll.parent.mkdir(parents=True)
    component_dll.write_bytes(b"d7vk")

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/syswow64"
    system_path.mkdir(parents=True)
    wine_ddraw = system_path / "ddraw.dll"
    wine_ddraw.write_bytes(b"wine")

    bundles = []
    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )
    monkeypatch.setattr(
        dll_module.Reg,
        "import_bundle",
        lambda _self, bundle: bundles.append(bundle),
    )

    config = BottleConfig(Path=str(bottle_path), Custom_Path=True, Arch="win64")
    component = D7VKComponent("d7vk-v2.0")
    component.install(config)

    assert wine_ddraw.read_bytes() == b"d7vk"
    assert (system_path / "ddraw_.dll").read_bytes() == b"wine"
    assert (system_path / "ddraw.dll.bottles-d7vk.bck").read_bytes() == b"wine"
    assert (system_path / "ddraw.dll.bottles-d7vk.json").is_file()
    assert bundles[-1]["HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides"] == [
        {"value": "ddraw", "data": "native,builtin"}
    ]

    component.uninstall(config)

    assert wine_ddraw.read_bytes() == b"wine"
    assert not (system_path / "ddraw_.dll").exists()
    assert not (system_path / "ddraw.dll.bottles-d7vk.bck").exists()
    assert not (system_path / "ddraw.dll.bottles-d7vk.json").exists()
    assert bundles[-1]["HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides"] == [
        {"value": "ddraw", "data": "-"}
    ]


def test_d7vk_targets_system32_for_win32(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    component_dll = component_path / "x32/ddraw.dll"
    component_dll.parent.mkdir(parents=True)
    component_dll.write_bytes(b"d7vk")

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/system32"
    system_path.mkdir(parents=True)
    (system_path / "ddraw.dll").write_bytes(b"wine")

    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: None)

    config = BottleConfig(Path=str(bottle_path), Custom_Path=True, Arch="win32")
    D7VKComponent("d7vk-v2.0").install(config)

    assert (system_path / "ddraw.dll").read_bytes() == b"d7vk"
    assert (system_path / "ddraw_.dll").read_bytes() == b"wine"


def test_incomplete_d7vk_component_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(VulkanUtils, "check_support", lambda: True)
    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(tmp_path / "missing")),
    )

    manager = object.__new__(Manager)
    manager.d7vk_available = []
    config = BottleConfig(Path=str(tmp_path / "bottle"), Custom_Path=True)

    result = Manager.install_dll_component(manager, config, "d7vk", version="d7vk-v2.0")

    assert result.ok is False
    assert result.message == "The selected D7VK installation is incomplete."


def test_d7vk_rejects_empty_x32_directory(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    (component_path / "x32").mkdir(parents=True)
    monkeypatch.setattr(VulkanUtils, "check_support", lambda: True)
    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )

    manager = object.__new__(Manager)
    config = BottleConfig(Path=str(tmp_path / "bottle"), Custom_Path=True)

    result = Manager.install_dll_component(manager, config, "d7vk", version="d7vk-v2.0")

    assert result.ok is False
    assert result.message == "The selected D7VK installation is incomplete."


def test_d7vk_rejects_zero_byte_dll(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    component_dll = component_path / "x32/ddraw.dll"
    component_dll.parent.mkdir(parents=True)
    component_dll.touch()
    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )

    assert not D7VKComponent("d7vk-v2.0").checked_dlls


def test_d7vk_preserves_preexisting_manual_files(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    component_dll = component_path / "x32/ddraw.dll"
    component_dll.parent.mkdir(parents=True)
    component_dll.write_bytes(b"managed")

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/syswow64"
    system_path.mkdir(parents=True)
    target = system_path / "ddraw.dll"
    wine_path = system_path / "ddraw_.dll"
    target.write_bytes(b"manual")
    wine_path.write_bytes(b"wine")

    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: None)

    config = BottleConfig(Path=str(bottle_path), Custom_Path=True, Arch="win64")
    component = D7VKComponent("d7vk-v2.0")
    component.install(config)

    assert target.read_bytes() == b"managed"
    assert wine_path.read_bytes() == b"wine"

    component.uninstall(config)

    assert target.read_bytes() == b"manual"
    assert wine_path.read_bytes() == b"wine"
    assert not (system_path / "ddraw.dll.bottles-d7vk.bck").exists()
    assert not (system_path / "ddraw_.dll.bottles-d7vk.bck").exists()
    assert not (system_path / "ddraw.dll.bottles-d7vk.json").exists()


def test_d7vk_rejects_preexisting_target_backup(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    component_dll = component_path / "x32/ddraw.dll"
    component_dll.parent.mkdir(parents=True)
    component_dll.write_bytes(b"managed")

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/syswow64"
    system_path.mkdir(parents=True)
    target = system_path / "ddraw.dll"
    backup = system_path / "ddraw.dll.bottles-d7vk.bck"
    target.write_bytes(b"wine")
    backup.write_bytes(b"preexisting")

    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: None)

    config = BottleConfig(Path=str(bottle_path), Custom_Path=True, Arch="win64")
    assert not D7VKComponent("d7vk-v2.0").install(config)
    assert target.read_bytes() == b"wine"
    assert backup.read_bytes() == b"preexisting"
    assert not (system_path / "ddraw.dll.bottles-d7vk.json").exists()


def test_d7vk_rejects_preexisting_wine_backup(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    component_dll = component_path / "x32/ddraw.dll"
    component_dll.parent.mkdir(parents=True)
    component_dll.write_bytes(b"managed")

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/syswow64"
    system_path.mkdir(parents=True)
    target = system_path / "ddraw.dll"
    wine_path = system_path / "ddraw_.dll"
    wine_backup = system_path / "ddraw_.dll.bottles-d7vk.bck"
    target.write_bytes(b"wine")
    wine_path.write_bytes(b"manual-alias")
    wine_backup.write_bytes(b"preexisting")

    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: None)

    config = BottleConfig(Path=str(bottle_path), Custom_Path=True, Arch="win64")
    assert not D7VKComponent("d7vk-v2.0").install(config)
    assert target.read_bytes() == b"wine"
    assert wine_path.read_bytes() == b"manual-alias"
    assert wine_backup.read_bytes() == b"preexisting"
    assert not (system_path / "ddraw.dll.bottles-d7vk.bck").exists()
    assert not (system_path / "ddraw.dll.bottles-d7vk.json").exists()


def test_d7vk_update_keeps_original_files(monkeypatch, tmp_path):
    components_path = tmp_path / "components"
    for version, content in (("d7vk-v1.0", b"old"), ("d7vk-v2.0", b"new")):
        dll = components_path / version / "x32/ddraw.dll"
        dll.parent.mkdir(parents=True)
        dll.write_bytes(content)

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/syswow64"
    system_path.mkdir(parents=True)
    target = system_path / "ddraw.dll"
    wine_path = system_path / "ddraw_.dll"
    target.write_bytes(b"wine")
    wine_path.write_bytes(b"manual-alias")

    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda version: str(components_path / version)),
    )
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: None)

    config = BottleConfig(Path=str(bottle_path), Custom_Path=True, Arch="win64")
    assert D7VKComponent("d7vk-v1.0").install(config)
    assert D7VKComponent("d7vk-v2.0").install(config)
    assert target.read_bytes() == b"new"

    assert D7VKComponent("d7vk-v2.0").uninstall(config)
    assert target.read_bytes() == b"wine"
    assert wine_path.read_bytes() == b"manual-alias"


def test_d7vk_recovers_interrupted_uninstall(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    component_dll = component_path / "x32/ddraw.dll"
    component_dll.parent.mkdir(parents=True)
    component_dll.write_bytes(b"managed")

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/syswow64"
    system_path.mkdir(parents=True)
    target = system_path / "ddraw.dll"
    wine_path = system_path / "ddraw_.dll"
    target.write_bytes(b"wine")
    wine_path.write_bytes(b"manual-alias")

    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: Result(True))

    config = BottleConfig(Path=str(bottle_path), Custom_Path=True, Arch="win64")
    component = D7VKComponent("d7vk-v2.0")
    assert component.install(config)

    complete_uninstall = D7VKComponent.complete_uninstall

    def interrupt_cleanup(*_args):
        raise OSError("interrupted cleanup")

    monkeypatch.setattr(D7VKComponent, "complete_uninstall", interrupt_cleanup)
    assert not component.uninstall(config)
    assert target.read_bytes() == b"wine"
    assert wine_path.read_bytes() == b"manual-alias"
    state = D7VKComponent._load_state(str(target))
    assert state and state["phase"] == "restored"
    assert not (system_path / "ddraw.dll.bottles-d7vk.bck").exists()

    monkeypatch.setattr(D7VKComponent, "complete_uninstall", complete_uninstall)
    assert component.uninstall(config)
    assert target.read_bytes() == b"wine"
    assert wine_path.read_bytes() == b"manual-alias"
    assert not D7VKComponent.has_managed_install(config)
    assert not (system_path / "ddraw_.dll.bottles-d7vk.bck").exists()


def test_set_d7vk_does_not_change_config_after_install_failure(monkeypatch):
    manager = object.__new__(Manager)
    manager.d7vk_available = ["d7vk-v2.0"]
    config = BottleConfig(D7VK="d7vk-v1.0")
    config.Parameters.d7vk = True

    monkeypatch.setattr(
        manager,
        "install_dll_component",
        lambda *_args, **_kwargs: Result(False, message="failed"),
    )
    monkeypatch.setattr(
        manager,
        "update_config",
        lambda *_args, **_kwargs: pytest.fail("configuration changed"),
    )

    result = Manager.set_d7vk(manager, config, True, "d7vk-v2.0")

    assert result.ok is False
    assert config.D7VK == "d7vk-v1.0"
    assert config.Parameters.d7vk is True


def test_set_d7vk_rolls_back_after_registry_failure(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    component_dll = component_path / "x32/ddraw.dll"
    component_dll.parent.mkdir(parents=True)
    component_dll.write_bytes(b"managed")

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/syswow64"
    system_path.mkdir(parents=True)
    target = system_path / "ddraw.dll"
    target.write_bytes(b"wine")

    registry_results = iter([Result(False, message="registry failed"), Result(True)])
    monkeypatch.setattr(VulkanUtils, "check_support", lambda: True)
    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )
    monkeypatch.setattr(
        dll_module.Reg,
        "import_bundle",
        lambda *_args: next(registry_results),
    )

    manager = object.__new__(Manager)
    manager.d7vk_available = ["d7vk-v2.0"]
    manager.local_bottles = {}
    config = BottleConfig(
        Name="Test", Path=str(bottle_path), Custom_Path=True, Arch="win64"
    )

    result = Manager.set_d7vk(manager, config, True, "d7vk-v2.0")

    assert not result.ok
    assert target.read_bytes() == b"wine"
    assert not (system_path / "ddraw_.dll").exists()
    assert not D7VKComponent.has_managed_install(config)
    assert config.D7VK == ""
    assert config.Parameters.d7vk is False


def test_set_d7vk_rolls_back_after_persistence_failure(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    component_dll = component_path / "x32/ddraw.dll"
    component_dll.parent.mkdir(parents=True)
    component_dll.write_bytes(b"managed")

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/syswow64"
    system_path.mkdir(parents=True)
    target = system_path / "ddraw.dll"
    target.write_bytes(b"wine")

    monkeypatch.setattr(VulkanUtils, "check_support", lambda: True)
    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: None)
    monkeypatch.setattr(
        BottleConfig,
        "dump",
        lambda *_args, **_kwargs: Result(False, message="disk full"),
    )

    manager = object.__new__(Manager)
    manager.d7vk_available = ["d7vk-v2.0"]
    manager.local_bottles = {}
    config = BottleConfig(
        Name="Test", Path=str(bottle_path), Custom_Path=True, Arch="win64"
    )

    result = Manager.set_d7vk(manager, config, True, "d7vk-v2.0")

    assert not result.ok
    assert result.message == "disk full"
    assert target.read_bytes() == b"wine"
    assert not (system_path / "ddraw_.dll").exists()
    assert not D7VKComponent.has_managed_install(config)
    assert config.D7VK == ""
    assert config.Parameters.d7vk is False


def test_unset_d7vk_rolls_back_after_persistence_failure(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    component_dll = component_path / "x32/ddraw.dll"
    component_dll.parent.mkdir(parents=True)
    component_dll.write_bytes(b"managed")

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/syswow64"
    system_path.mkdir(parents=True)
    target = system_path / "ddraw.dll"
    target.write_bytes(b"wine")

    monkeypatch.setattr(VulkanUtils, "check_support", lambda: True)
    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: None)

    config = BottleConfig(
        Name="Test",
        Path=str(bottle_path),
        Custom_Path=True,
        Arch="win64",
        D7VK="d7vk-v2.0",
    )
    config.Parameters.d7vk = True
    assert D7VKComponent("d7vk-v2.0").install(config)

    monkeypatch.setattr(
        BottleConfig,
        "dump",
        lambda *_args, **_kwargs: Result(False, message="disk full"),
    )
    manager = object.__new__(Manager)
    manager.d7vk_available = ["d7vk-v2.0"]
    manager.local_bottles = {}

    result = Manager.set_d7vk(manager, config, False)

    assert not result.ok
    assert result.message == "disk full"
    assert target.read_bytes() == b"managed"
    assert D7VKComponent.has_managed_install(config)
    assert config.D7VK == "d7vk-v2.0"
    assert config.Parameters.d7vk is True


def test_set_d7vk_persists_one_candidate_config(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    component_dll = component_path / "x32/ddraw.dll"
    component_dll.parent.mkdir(parents=True)
    component_dll.write_bytes(b"managed")

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/syswow64"
    system_path.mkdir(parents=True)
    (system_path / "ddraw.dll").write_bytes(b"wine")

    dumped = []
    monkeypatch.setattr(VulkanUtils, "check_support", lambda: True)
    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: None)
    monkeypatch.setattr(
        BottleConfig,
        "dump",
        lambda self, *_args, **_kwargs: dumped.append(self.to_dict()) or Result(True),
    )
    monkeypatch.setattr(
        manager_module.RegistryRuleManager,
        "apply_rules",
        lambda *_args, **_kwargs: None,
    )

    manager = object.__new__(Manager)
    manager.d7vk_available = ["d7vk-v2.0"]
    config = BottleConfig(
        Name="Test", Path=str(bottle_path), Custom_Path=True, Arch="win64"
    )
    manager.local_bottles = {config.Name: config}

    result = Manager.set_d7vk(manager, config, True, "d7vk-v2.0")

    assert result.ok
    assert len(dumped) == 1
    assert dumped[0]["D7VK"] == "d7vk-v2.0"
    assert dumped[0]["Parameters"]["d7vk"] is True
    assert result.data["config"] is manager.local_bottles[config.Name]
    assert result.data["config"] is config
    assert config.D7VK == "d7vk-v2.0"
    assert config.Parameters.d7vk is True


def test_reconcile_d7vk_reverts_an_interrupted_enable(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    component_dll = component_path / "x32/ddraw.dll"
    component_dll.parent.mkdir(parents=True)
    component_dll.write_bytes(b"managed")

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/syswow64"
    system_path.mkdir(parents=True)
    target = system_path / "ddraw.dll"
    target.write_bytes(b"wine")

    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda _version: str(component_path)),
    )
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: None)

    config = BottleConfig(
        Name="Test", Path=str(bottle_path), Custom_Path=True, Arch="win64"
    )
    assert D7VKComponent("d7vk-v2.0").install(config)

    manager = object.__new__(Manager)
    assert Manager.reconcile_d7vk(manager, config)
    assert target.read_bytes() == b"wine"
    assert not D7VKComponent.has_managed_install(config)


def test_reconcile_d7vk_reverts_an_interrupted_update(monkeypatch, tmp_path):
    components_path = tmp_path / "components"
    for version, content in (("d7vk-v1.0", b"old"), ("d7vk-v2.0", b"new")):
        dll = components_path / version / "x32/ddraw.dll"
        dll.parent.mkdir(parents=True)
        dll.write_bytes(content)

    bottle_path = tmp_path / "bottle"
    system_path = bottle_path / "drive_c/windows/syswow64"
    system_path.mkdir(parents=True)
    target = system_path / "ddraw.dll"
    target.write_bytes(b"wine")

    monkeypatch.setattr(
        D7VKComponent,
        "get_base_path",
        staticmethod(lambda version: str(components_path / version)),
    )
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: None)

    config = BottleConfig(
        Name="Test",
        Path=str(bottle_path),
        Custom_Path=True,
        Arch="win64",
        D7VK="d7vk-v1.0",
    )
    config.Parameters.d7vk = True
    assert D7VKComponent("d7vk-v1.0").install(config)
    assert D7VKComponent("d7vk-v2.0").install(config)
    assert target.read_bytes() == b"new"

    manager = object.__new__(Manager)
    assert Manager.reconcile_d7vk(manager, config)
    assert target.read_bytes() == b"old"
    assert D7VKComponent("d7vk-v1.0").is_installed(config)


def test_create_bottle_from_config_reports_creation_failure():
    manager = object.__new__(Manager)
    manager.runners_available = ["runner"]
    manager.d7vk_available = ["d7vk-v2.0"]
    manager.dxvk_available = []
    manager.vkd3d_available = []
    manager.nvapi_available = []
    manager.latencyflex_available = []
    manager.create_bottle = lambda **_kwargs: Result(False, message="failed")

    config = BottleConfig(Name="Imported", Path="Imported", Runner="runner")
    config.D7VK = "d7vk-v2.0"
    config.Parameters.d7vk = True

    assert not Manager.create_bottle_from_config(manager, config)


def test_create_bottle_from_config_requests_enabled_d7vk():
    manager = object.__new__(Manager)
    manager.runners_available = ["runner"]
    manager.d7vk_available = ["d7vk-v2.0"]
    manager.dxvk_available = []
    manager.vkd3d_available = []
    manager.nvapi_available = []
    manager.latencyflex_available = []
    captured = {}

    def create_bottle(**kwargs):
        captured.update(kwargs)
        return Result(True, data={"config": kwargs["configuration"]})

    manager.create_bottle = create_bottle
    manager.update_bottles = lambda **_kwargs: None

    config = BottleConfig(Name="Imported", Path="Imported", Runner="runner")
    config.D7VK = "d7vk-v2.0"
    config.Parameters.d7vk = True

    assert Manager.create_bottle_from_config(manager, config)
    assert captured["d7vk"] == "d7vk-v2.0"
    assert captured["configuration"].Parameters.d7vk is True


def test_create_bottle_from_config_does_not_request_disabled_d7vk():
    manager = object.__new__(Manager)
    manager.runners_available = ["runner"]
    manager.d7vk_available = ["d7vk-v2.0"]
    manager.dxvk_available = []
    manager.vkd3d_available = []
    manager.nvapi_available = []
    manager.latencyflex_available = []
    captured = {}

    def create_bottle(**kwargs):
        captured.update(kwargs)
        return Result(True, data={"config": kwargs["configuration"]})

    manager.create_bottle = create_bottle
    manager.update_bottles = lambda **_kwargs: None
    config = BottleConfig(Name="Imported", Path="Imported", Runner="runner")
    config.D7VK = "d7vk-v2.0"

    assert Manager.create_bottle_from_config(manager, config)
    assert captured["d7vk"] is False
    assert captured["configuration"].Parameters.d7vk is False
