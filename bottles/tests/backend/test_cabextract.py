from pathlib import Path

from bottles.backend import cabextract as cabextract_module
from bottles.backend.cabextract import CabExtract


def test_extract_expands_cab_wildcards(monkeypatch, tmp_path: Path) -> None:
    archive_dir = tmp_path / "archives"
    archive_dir.mkdir()
    archives = [archive_dir / "first.cab", archive_dir / "second.cab"]
    for archive in archives:
        archive.touch()

    commands = []
    def extract(command, check):
        assert check is True
        commands.append(command)
        (Path(command[command.index("-d") + 1]) / "xaudio2_0.dll").touch()

    monkeypatch.setattr(cabextract_module.subprocess, "run", extract)
    extractor = CabExtract()
    extractor.cabextract_bin = "cabextract"

    assert extractor.run(
        str(archive_dir / "*.cab"),
        files=["xaudio*.dll"],
        destination=str(tmp_path / "output"),
    )
    assert [Path(command[-1]) for command in commands] == archives


def test_extract_rejects_unmatched_cab_wildcard(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cabextract_module.subprocess,
        "run",
        lambda *_args, **_kwargs: None,
    )
    extractor = CabExtract()
    extractor.cabextract_bin = "cabextract"

    assert not extractor.run(
        str(tmp_path / "*.cab"), destination=str(tmp_path / "output")
    )


def test_extract_rejects_unmatched_file_filter(monkeypatch, tmp_path: Path) -> None:
    archive = tmp_path / "archive.cab"
    archive.touch()
    monkeypatch.setattr(
        cabextract_module.subprocess,
        "run",
        lambda *_args, **_kwargs: None,
    )
    extractor = CabExtract()
    extractor.cabextract_bin = "cabextract"

    assert not extractor.run(
        str(archive),
        files=["missing*.dll"],
        destination=str(tmp_path / "output"),
    )


def test_extract_does_not_accept_preexisting_filtered_file(
    monkeypatch, tmp_path: Path
) -> None:
    archive = tmp_path / "archive.cab"
    archive.touch()
    destination = tmp_path / "output"
    destination.mkdir()
    (destination / "xaudio2_0.dll").touch()
    monkeypatch.setattr(
        cabextract_module.subprocess,
        "run",
        lambda *_args, **_kwargs: None,
    )
    extractor = CabExtract()
    extractor.cabextract_bin = "cabextract"

    assert not extractor.run(
        str(archive), files=["xaudio*.dll"], destination=str(destination)
    )


def test_extract_replaces_broken_matching_symlink(
    monkeypatch, tmp_path: Path
) -> None:
    archive = tmp_path / "archive.cab"
    archive.touch()
    destination = tmp_path / "output"
    destination.mkdir()
    missing_target = tmp_path / "missing.dll"
    output = destination / "xaudio2_0.dll"
    output.symlink_to(missing_target)

    def extract(command, check):
        assert check is True
        assert not output.is_symlink()
        output.write_bytes(b"native")

    monkeypatch.setattr(cabextract_module.subprocess, "run", extract)
    extractor = CabExtract()
    extractor.cabextract_bin = "cabextract"

    assert extractor.run(
        str(archive), files=["xaudio*.dll"], destination=str(destination)
    )
    assert output.read_bytes() == b"native"
    assert not missing_target.exists()


def test_extract_replaces_case_insensitive_duplicate(
    monkeypatch, tmp_path: Path
) -> None:
    archive = tmp_path / "archive.cab"
    archive.touch()
    destination = tmp_path / "output"
    destination.mkdir()
    builtin = destination / "xaudio2_0.dll"
    native = destination / "XAudio2_0.dll"
    builtin.write_bytes(b"builtin")

    def extract(command, check):
        assert check is True
        native.write_bytes(b"native")

    monkeypatch.setattr(cabextract_module.subprocess, "run", extract)
    extractor = CabExtract()
    extractor.cabextract_bin = "cabextract"

    assert extractor.run(
        str(archive), files=["xaudio*.dll"], destination=str(destination)
    )
    assert builtin.read_bytes() == b"native"
    assert not native.exists()


def test_extract_accepts_literal_path_with_glob_characters(
    monkeypatch, tmp_path: Path
) -> None:
    archive = tmp_path / "archive[1].cab"
    archive.touch()
    commands = []
    monkeypatch.setattr(
        cabextract_module.subprocess,
        "run",
        lambda command, check: commands.append((command, check)),
    )
    extractor = CabExtract()
    extractor.cabextract_bin = "cabextract"

    assert extractor.run(str(archive), destination=str(tmp_path / "output"))
    assert commands[0][0][-1] == str(archive)
    assert commands[0][1] is True


def test_extract_reports_subprocess_failure(monkeypatch, tmp_path: Path) -> None:
    archive = tmp_path / "archive.cab"
    archive.touch()

    def fail(_command, check):
        assert check is True
        raise cabextract_module.subprocess.CalledProcessError(1, "cabextract")

    monkeypatch.setattr(cabextract_module.subprocess, "run", fail)
    extractor = CabExtract()
    extractor.cabextract_bin = "cabextract"

    assert not extractor.run(str(archive), destination=str(tmp_path / "output"))
