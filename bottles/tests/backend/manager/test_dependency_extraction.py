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


def test_font_install_replaces_prefix_link_without_changing_runner(tmp_path):
    prefix = tmp_path / "prefix"
    fonts = prefix / "drive_c/windows/Fonts"
    fonts.mkdir(parents=True)
    runner_font = tmp_path / "runner-font.ttf"
    runner_font.write_bytes(b"runner")
    runner_font.chmod(0o444)
    fonts.joinpath("cour.ttf").symlink_to(runner_font)
    source = tmp_path / "source"
    source.mkdir()
    source.joinpath("cour.ttf").write_bytes(b"replacement")

    result = DependencyManager._DependencyManager__step_install_fonts(
        BottleConfig(Path=str(prefix), Custom_Path=True),
        {"url": str(source), "fonts": ["cour.ttf"]},
    )

    assert result
    assert runner_font.read_bytes() == b"runner"
    assert not fonts.joinpath("cour.ttf").is_symlink()
    assert fonts.joinpath("cour.ttf").read_bytes() == b"replacement"


def test_failed_font_copy_keeps_existing_destination(tmp_path):
    prefix = tmp_path / "prefix"
    fonts = prefix / "drive_c/windows/Fonts"
    fonts.mkdir(parents=True)
    fonts.joinpath("cour.ttf").write_bytes(b"original")

    result = DependencyManager._DependencyManager__step_install_fonts(
        BottleConfig(Path=str(prefix), Custom_Path=True),
        {"url": str(tmp_path / "missing"), "fonts": ["cour.ttf"]},
    )

    assert not result
    assert fonts.joinpath("cour.ttf").read_bytes() == b"original"
    assert list(fonts.iterdir()) == [fonts / "cour.ttf"]
