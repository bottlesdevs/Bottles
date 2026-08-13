from pathlib import Path

from bottles.backend.cabextract import CabExtract
from bottles.backend.managers.dependency import DependencyManager
from bottles.backend.models.config import BottleConfig


def test_get_from_cab_keeps_case_normalized_rename(monkeypatch, tmp_path: Path):
    dependency_manager = object.__new__(DependencyManager)
    destination = tmp_path / "system32"
    destination.mkdir()

    monkeypatch.setattr(
        DependencyManager,
        "_DependencyManager__get_real_dest",
        staticmethod(lambda _config, _dest: str(destination)),
    )

    def extract(_self, path, files, destination):
        assert path.endswith("d3dcompiler_42.cab")
        assert files == ["D3DCompiler_42.dll"]
        (Path(destination) / "d3dcompiler_42.dll").write_bytes(b"native")
        return True

    monkeypatch.setattr(CabExtract, "run", extract)

    result = dependency_manager._DependencyManager__step_get_from_cab(
        BottleConfig(),
        {
            "source": "d3dcompiler_42.cab",
            "file_name": "D3DCompiler_42.dll",
            "dest": "win64/",
            "rename": "d3dcompiler_42.dll",
        },
    )

    assert result
    assert (destination / "d3dcompiler_42.dll").read_bytes() == b"native"
