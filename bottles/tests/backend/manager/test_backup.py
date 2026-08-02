import os
import tarfile
from pathlib import Path

import pytest

from bottles.backend.managers.backup import BackupManager


@pytest.fixture(autouse=True)
def preserve_working_directory():
    working_directory = os.getcwd()
    yield
    os.chdir(working_directory)


def test_full_backup_skips_file_removed_during_copy(tmp_path, monkeypatch):
    source = tmp_path / "bottle"
    source.mkdir()
    stable = source / "stable.dat"
    stable.write_bytes(b"stable")
    volatile = source / "volatile.tmp"
    volatile.write_bytes(b"volatile")
    destination = tmp_path / "backup.tar.gz"
    original_open = tarfile.bltn_open

    def open_file(name, mode):
        if Path(name).resolve() == volatile and mode == "rb":
            volatile.unlink(missing_ok=True)
        return original_open(name, mode)

    monkeypatch.setattr(tarfile, "bltn_open", open_file)

    assert BackupManager._create_tarfile(str(source), str(destination))

    with tarfile.open(destination, "r:gz") as archive:
        assert "bottle/stable.dat" in archive.getnames()
        assert "bottle/volatile.tmp" not in archive.getnames()


def test_full_backup_preserves_destination_after_failure(tmp_path, monkeypatch):
    source = tmp_path / "bottle"
    source.mkdir()
    (source / "payload").write_bytes(b"payload")
    destination = tmp_path / "backup.tar.gz"
    destination.write_bytes(b"existing backup")

    def fail_write(*_args, **_kwargs):
        raise FileNotFoundError("removed during backup")

    monkeypatch.setattr(tarfile.TarFile, "addfile", fail_write)

    assert not BackupManager._create_tarfile(str(source), str(destination))
    assert destination.read_bytes() == b"existing backup"
    assert not list(tmp_path.glob(".backup.tar.gz.*.tmp"))


def test_full_backup_does_not_change_working_directory(tmp_path):
    source = tmp_path / "bottle"
    source.mkdir()
    (source / "payload").write_bytes(b"payload")
    destination = tmp_path / "backup.tar.gz"
    working_directory = os.getcwd()

    try:
        assert BackupManager._create_tarfile(str(source), str(destination))
        resulting_directory = os.getcwd()
    finally:
        os.chdir(working_directory)

    assert resulting_directory == working_directory


def test_full_backup_rejects_destination_inside_source(tmp_path):
    source = tmp_path / "bottle"
    source.mkdir()
    (source / "payload").write_bytes(b"payload")
    destination = source / "backup.tar.gz"

    assert not BackupManager._create_tarfile(str(source), str(destination))
    assert not destination.exists()


def test_full_backup_fails_when_source_is_missing(tmp_path):
    source = tmp_path / "missing"
    destination = tmp_path / "backup.tar.gz"

    assert not BackupManager._create_tarfile(str(source), str(destination))
    assert not destination.exists()
    assert not list(tmp_path.glob(".backup.tar.gz.*.tmp"))


def test_full_backup_keeps_existing_filter_behavior(tmp_path):
    source = tmp_path / "bottle"
    source.mkdir()
    drive_c = source / "drive_c"
    drive_c.mkdir()
    (drive_c / "program.exe").write_bytes(b"program")
    dosdevices = source / "dosdevices"
    dosdevices.mkdir()
    (dosdevices / "c:").symlink_to("../drive_c")
    destination = tmp_path / "backup.tar.gz"

    assert BackupManager._create_tarfile(
        str(source),
        str(destination),
        exclude_filter=BackupManager.exclude_filter,
    )

    with tarfile.open(destination, "r:gz") as archive:
        names = archive.getnames()
        assert "bottle/drive_c/program.exe" in names
        assert not any("dosdevices" in name for name in names)
