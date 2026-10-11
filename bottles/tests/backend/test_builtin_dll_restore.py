from unittest.mock import Mock

import pytest

from bottles.backend.dlls import dll as dll_module
from bottles.backend.dlls.dxvk import DXVKComponent
from bottles.backend.dlls.vkd3d import VKD3DComponent
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils


@pytest.mark.parametrize("steam", [False, True])
@pytest.mark.parametrize("component", [DXVKComponent, VKD3DComponent])
@pytest.mark.parametrize("layout", ["lib", "lib64", "files/lib", "dist/lib64"])
@pytest.mark.parametrize(
    "bottle_arch, windows_arch, system",
    [
        ("win64", "x86_64", "system32"),
        ("win64", "i386", "syswow64"),
        ("win32", "i386", "system32"),
    ],
)
def test_uninstall_restores_matching_builtin_without_backup(
    monkeypatch, tmp_path, component, layout, bottle_arch, windows_arch, system, steam
):
    runner = tmp_path / "runner"
    runner.mkdir()
    if "/" in layout:
        (runner / "toolmanifest.vdf").write_text(
            '"manifest"\n{\n    "compatmanager_layer_name" "proton"\n}\n'
        )
    name = next(iter(component.dlls.values()))[0]
    builtin = runner / layout / "wine" / f"{windows_arch}-windows" / name
    builtin.parent.mkdir(parents=True)
    builtin.write_bytes(b"matching-wine-builtin")
    wrong_arch = "i386" if windows_arch == "x86_64" else "x86_64"
    wrong = runner / layout / "wine" / f"{wrong_arch}-windows" / name
    wrong.parent.mkdir(parents=True)
    wrong.write_bytes(b"wrong-architecture")
    prefix = tmp_path / "bottle"
    target = prefix / "drive_c/windows" / system / name
    target.parent.mkdir(parents=True)
    if bottle_arch == "win64":
        (
            prefix
            / "drive_c/windows"
            / ("syswow64" if system == "system32" else "system32")
        ).mkdir()
    target.write_bytes(b"native-component")
    config = BottleConfig(
        Path=str(prefix),
        Custom_Path=True,
        Arch=bottle_arch,
        Environment="Steam" if steam else "",
        RunnerPath=str(runner),
        CompatData=str(prefix) if steam else "",
    )
    monkeypatch.setattr(ManagerUtils, "get_runner_path", lambda _runner: str(runner))
    monkeypatch.setattr(
        component,
        "get_base_path",
        staticmethod(lambda _version: str(tmp_path / "cache-missing")),
    )
    registry = Mock(return_value=Result(True))
    monkeypatch.setattr(dll_module.Reg, "import_bundle", registry)

    assert component("component-old").uninstall(config)

    assert target.read_bytes() == b"matching-wine-builtin"
    assert builtin.read_bytes() == b"matching-wine-builtin"
    assert not target.with_name(name + ".bck").exists()
    assert all(
        item["data"] == "-"
        for item in registry.call_args.args[0][
            "HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides"
        ]
    )


def test_native_backup_takes_priority_over_runner_builtin(monkeypatch, tmp_path):
    prefix = tmp_path / "bottle"
    target = prefix / "drive_c/windows/system32/dxgi.dll"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"dxvk")
    target.with_name("dxgi.dll.bck").write_bytes(b"custom-native")
    config = BottleConfig(Path=str(prefix), Custom_Path=True, Arch="win64")
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: Result(True))
    monkeypatch.setattr(
        ManagerUtils, "get_runner_path", lambda *_args: pytest.fail("backup must win")
    )
    component = DXVKComponent("old")
    component.dlls = {"x64": ["dxgi.dll"]}

    assert component.uninstall(config)

    assert target.read_bytes() == b"custom-native"


def test_restore_error_preserves_native_dll_and_reports_failure(monkeypatch, tmp_path):
    runner = tmp_path / "runner"
    builtin = runner / "lib/wine/x86_64-windows/dxgi.dll"
    builtin.parent.mkdir(parents=True)
    builtin.write_bytes(b"builtin")
    prefix = tmp_path / "bottle"
    target = prefix / "drive_c/windows/system32/dxgi.dll"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"native-component")
    config = BottleConfig(Path=str(prefix), Custom_Path=True, Arch="win64")
    monkeypatch.setattr(ManagerUtils, "get_runner_path", lambda *_args: str(runner))
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: Result(True))
    monkeypatch.setattr(
        dll_module.shutil, "copyfile", Mock(side_effect=OSError("copy failed"))
    )
    component = DXVKComponent("old")
    component.dlls = {"x64": ["dxgi.dll"]}

    assert not component.uninstall(config)

    assert target.read_bytes() == b"native-component"
    assert list(target.parent.iterdir()) == [target]


@pytest.mark.parametrize(
    "arch, directory",
    [
        ("i386", "lib/i386-linux-gnu"),
        ("x86_64", "lib/x86_64-linux-gnu"),
    ],
)
def test_system_runner_restores_multilib_builtin(
    monkeypatch, tmp_path, arch, directory
):
    system_root = tmp_path / "system"
    builtin = system_root / directory / "wine" / f"{arch}-windows/dxgi.dll"
    builtin.parent.mkdir(parents=True)
    builtin.write_bytes(b"system-wine")
    prefix = tmp_path / "bottle"
    target = prefix / "drive_c/windows/system32/dxgi.dll"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"dxvk")
    (prefix / "drive_c/windows/syswow64").mkdir()
    config = BottleConfig(
        Path=str(prefix),
        Custom_Path=True,
        Runner="sys-wine",
        Arch="win32" if arch == "i386" else "win64",
    )
    monkeypatch.setattr(
        dll_module.shutil, "which", lambda *_args: str(system_root / "bin/wine")
    )
    monkeypatch.setattr(dll_module.Reg, "import_bundle", lambda *_args: Result(True))
    component = DXVKComponent("old")

    assert component.uninstall(config)

    assert target.read_bytes() == b"system-wine"
