import tarfile
from types import SimpleNamespace

from bottles.backend.globals import Paths
from bottles.backend.managers import component as component_module
from bottles.backend.managers.component import ComponentManager


def test_component_manager_preserves_catalog_x86_64_runner_name(
    tmp_path, monkeypatch
):
    temp_path = tmp_path / "temp"
    runners_path = tmp_path / "runners"
    source_path = tmp_path / "source"
    component_name = "proton-cachyos-11.0-20260703-slr-x86_64"
    temp_path.mkdir()
    runners_path.mkdir()
    source_path.mkdir()
    (source_path / "proton").write_text("runner")
    archive_path = temp_path / f"{component_name}.tar.xz"

    with tarfile.open(archive_path, "w:xz") as archive:
        archive.add(source_path, arcname=component_name)

    monkeypatch.setattr(Paths, "temp", str(temp_path))
    monkeypatch.setattr(Paths, "runners", str(runners_path))

    assert ComponentManager.extract(component_name, "runner:proton", archive_path.name)
    assert (runners_path / component_name / "proton").read_text() == "runner"


def test_component_manager_strips_archive_only_x86_64_suffix(tmp_path, monkeypatch):
    temp_path = tmp_path / "temp"
    runners_path = tmp_path / "runners"
    source_path = tmp_path / "source"
    component_name = "legacy-runner-1.0"
    archive_root = f"{component_name}_x86_64"
    temp_path.mkdir()
    runners_path.mkdir()
    source_path.mkdir()
    (source_path / "wine").write_text("runner")
    archive_path = temp_path / f"{archive_root}.tar.xz"

    with tarfile.open(archive_path, "w:xz") as archive:
        archive.add(source_path, arcname=archive_root)

    monkeypatch.setattr(Paths, "temp", str(temp_path))
    monkeypatch.setattr(Paths, "runners", str(runners_path))

    assert ComponentManager.extract(component_name, "runner", archive_path.name)
    assert (runners_path / component_name / "wine").read_text() == "runner"
    assert not (runners_path / archive_root).exists()


def test_component_manager_strips_archive_only_aarch64_suffix(
    tmp_path, monkeypatch
):
    temp_path = tmp_path / "temp"
    runners_path = tmp_path / "runners"
    source_path = tmp_path / "source"
    component_name = "soda-11.0-7"
    archive_root = f"{component_name}-aarch64"
    temp_path.mkdir()
    runners_path.mkdir()
    source_path.mkdir()
    (source_path / "wine").write_text("runner")
    archive_path = temp_path / f"{archive_root}.tar.xz"

    with tarfile.open(archive_path, "w:xz") as archive:
        archive.add(source_path, arcname=archive_root)

    monkeypatch.setattr(Paths, "temp", str(temp_path))
    monkeypatch.setattr(Paths, "runners", str(runners_path))

    assert ComponentManager.extract(component_name, "runner", archive_path.name)
    assert (runners_path / component_name / "wine").read_text() == "runner"
    assert not (runners_path / archive_root).exists()


def test_component_cache_selects_host_architecture(tmp_path, monkeypatch):
    monkeypatch.setattr(Paths, "temp", str(tmp_path))
    (tmp_path / "soda-aarch64.tar.xz").write_bytes(b"runner")
    manifest = {
        "File": [
            {
                "architecture": "x86_64",
                "file_name": "soda-x86_64.tar.xz",
            },
            {
                "architecture": "aarch64",
                "file_name": "soda-aarch64.tar.xz",
            },
        ]
    }
    component_manager = object.__new__(ComponentManager)
    component_manager._ComponentManager__repo = SimpleNamespace(
        get=lambda name, plain=False: manifest
    )
    monkeypatch.setattr(
        component_module, "get_host_architecture", lambda: "aarch64"
    )

    assert component_manager.is_component_cached("soda-11.0-7") is True

    monkeypatch.setattr(
        component_module, "get_host_architecture", lambda: "x86_64"
    )

    assert component_manager.is_component_cached("soda-11.0-7") is False


def test_component_cache_rejects_other_platform(tmp_path, monkeypatch):
    monkeypatch.setattr(Paths, "temp", str(tmp_path))
    (tmp_path / "soda-aarch64.tar.xz").write_bytes(b"runner")
    manifest = {
        "File": [
            {
                "architecture": "aarch64",
                "platform": "linux",
                "file_name": "soda-aarch64.tar.xz",
            }
        ]
    }
    component_manager = object.__new__(ComponentManager)
    component_manager._ComponentManager__repo = SimpleNamespace(
        get=lambda name, plain=False: manifest
    )
    monkeypatch.setattr(
        component_module, "get_host_architecture", lambda: "aarch64"
    )
    monkeypatch.setattr(component_module.sys, "platform", "darwin")

    assert component_manager.is_component_cached("soda-11.0-7") is False

    monkeypatch.setattr(component_module.sys, "platform", "linux")

    assert component_manager.is_component_cached("soda-11.0-7") is True


def test_external_runner_cannot_be_uninstalled(tmp_path):
    runner = tmp_path / "GE-Proton10-4"
    runner.mkdir()
    manager = SimpleNamespace(
        external_runners={runner.name},
        local_bottles={},
    )
    component_manager = object.__new__(ComponentManager)
    component_manager._ComponentManager__manager = manager

    result = component_manager.uninstall("runner:proton", runner.name)

    assert not result.ok
    assert result.data == {
        "message": "External runners cannot be removed from Bottles."
    }
    assert runner.is_dir()
