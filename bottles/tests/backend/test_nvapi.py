from bottles.backend.dlls import dll as dll_module
from bottles.backend.dlls import nvapi as nvapi_module
from bottles.backend.dlls.nvapi import NVAPIComponent
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result


def test_nvapi_can_update_and_remove_after_driver_disappears(monkeypatch, tmp_path):
    component_path = tmp_path / "component"
    for arch, name in (("x32", "nvapi.dll"), ("x64", "nvapi64.dll")):
        source = component_path / arch / name
        source.parent.mkdir(parents=True)
        source.write_bytes(b"new NVAPI")
    prefix = tmp_path / "prefix"
    windows = prefix / "drive_c/windows"
    for system, name in (("syswow64", "nvapi.dll"), ("system32", "nvapi64.dll")):
        destination = windows / system / name
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"Wine builtin")
    driver = tmp_path / "driver/lib64"
    driver.mkdir(parents=True)
    for name in ("nvngx.dll", "_nvngx.dll"):
        (driver / name).write_bytes(b"NVIDIA driver")
    config = BottleConfig(Path=str(prefix), Custom_Path=True, Arch="win64")
    monkeypatch.setattr(NVAPIComponent, "get_base_path", lambda *_args: str(component_path))
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: Result(True))
    monkeypatch.setattr(nvapi_module, "get_nvidia_dll_path", lambda: str(driver))
    original = NVAPIComponent("old")
    assert original.install(config)

    monkeypatch.setattr(nvapi_module, "get_nvidia_dll_path", lambda: None)
    updated = NVAPIComponent("new")

    assert updated.check()
    assert updated.install(config)
    assert (windows / "system32/nvapi64.dll").read_bytes() == b"new NVAPI"
    assert updated.uninstall(config)
    assert (windows / "system32/nvapi64.dll").read_bytes() == b"Wine builtin"
    assert (windows / "syswow64/nvapi.dll").read_bytes() == b"Wine builtin"
    assert not (windows / "system32/nvngx.dll").exists()
    assert not (windows / "system32/_nvngx.dll").exists()
    assert str(driver) in original.dlls
    assert None not in NVAPIComponent.dlls
    assert NVAPIComponent.dlls["x64"] == ["nvapi64.dll"]
