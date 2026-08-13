import tarfile
from types import SimpleNamespace

from bottles.backend.globals import Paths
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
