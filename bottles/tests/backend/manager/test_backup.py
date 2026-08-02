import os
import tarfile
from concurrent.futures import CancelledError
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from bottles.backend.managers.backup import BackupManager
from bottles.backend.state import SignalManager, Task, TaskManager


@pytest.fixture(autouse=True)
def preserve_working_directory():
    working_directory = os.getcwd()
    yield
    os.chdir(working_directory)


@pytest.fixture(autouse=True)
def isolated_tasks():
    tasks = TaskManager._TASKS
    signals = SignalManager._SIGNALS
    TaskManager._TASKS = {}
    SignalManager._SIGNALS = {}
    yield
    TaskManager._TASKS = tasks
    SignalManager._SIGNALS = signals


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


def test_full_backup_is_atomic_when_cancelled_during_file_copy(tmp_path, monkeypatch):
    source = tmp_path / "bottle"
    source.mkdir()
    payload = source / "payload.bin"
    payload.write_bytes(b"x" * 128 * 1024)
    destination = tmp_path / "backup.tar.gz"
    destination.write_bytes(b"existing backup")
    cancel_event = Event()
    original_open = tarfile.bltn_open

    class CancelAfterRead:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.stream.close()

        def read(self, size=-1):
            data = self.stream.read(size)
            cancel_event.set()
            return data

    def open_file(name, mode):
        stream = original_open(name, mode)
        if Path(name) == payload and mode == "rb":
            return CancelAfterRead(stream)
        return stream

    monkeypatch.setattr(tarfile, "bltn_open", open_file)

    result = BackupManager._create_tarfile(
        str(source),
        str(destination),
        task=Task(cancellable=True),
        cancel_event=cancel_event,
    )

    assert not result
    assert destination.read_bytes() == b"existing backup"
    assert not list(tmp_path.glob(".backup.tar.gz.*.tmp"))


def test_full_backup_replaces_destination_only_after_success(tmp_path):
    source = tmp_path / "bottle"
    source.mkdir()
    (source / "drive_c").mkdir()
    (source / "drive_c" / "program.exe").write_bytes(b"program")
    (source / "dosdevices").mkdir()
    (source / "dosdevices" / "c:").write_text("ignored")
    destination = tmp_path / "backup.tar.gz"
    destination.write_bytes(b"old")

    assert BackupManager._create_tarfile(
        str(source),
        str(destination),
        exclude_filter=BackupManager.exclude_filter,
        task=Task(cancellable=True),
        cancel_event=Event(),
    )

    with tarfile.open(destination, "r:gz") as archive:
        names = archive.getnames()
        assert "bottle/drive_c/program.exe" in names
        assert not any("dosdevices" in name for name in names)
    assert not list(tmp_path.glob(".backup.tar.gz.*.tmp"))


def test_full_backup_scan_honors_cancellation(tmp_path):
    source = tmp_path / "bottle"
    source.mkdir()
    (source / "payload").write_bytes(b"payload")
    cancel_event = Event()
    cancel_event.set()

    with pytest.raises(CancelledError):
        BackupManager._calculate_dir_size(str(source), cancel_event=cancel_event)


def test_full_backup_preserves_destination_after_write_error(tmp_path, monkeypatch):
    source = tmp_path / "bottle"
    source.mkdir()
    (source / "payload").write_bytes(b"payload")
    destination = tmp_path / "backup.tar.gz"
    destination.write_bytes(b"existing backup")

    monkeypatch.setattr(
        "bottles.backend.managers.backup._BackupTarFile.add",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("failure")),
    )

    assert not BackupManager._create_tarfile(
        str(source), str(destination), cancel_event=Event()
    )
    assert destination.read_bytes() == b"existing backup"
    assert not list(tmp_path.glob(".backup.tar.gz.*.tmp"))


@pytest.mark.parametrize("through_symlink", (False, True))
def test_full_backup_rejects_destination_inside_source(tmp_path, through_symlink):
    source = tmp_path / "bottle"
    source.mkdir()
    (source / "payload").write_bytes(b"payload")
    destination_dir = source
    if through_symlink:
        destination_dir = tmp_path / "bottle-link"
        destination_dir.symlink_to(source, target_is_directory=True)
    destination = destination_dir / "backup.tar.gz"

    assert not BackupManager._create_tarfile(str(source), str(destination))
    assert not destination.exists()
    assert not list(source.glob(".backup.tar.gz.*.tmp"))


def test_export_backup_reports_cancellation_and_removes_task(tmp_path, monkeypatch):
    config = SimpleNamespace(Name="Test")

    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(tmp_path / "bottle"),
    )

    def cancel_backup(*_args, task, cancel_event, **_kwargs):
        assert task.cancellable
        assert TaskManager.cancel(task.task_id)
        assert cancel_event is task.cancel_event
        return False

    monkeypatch.setattr(BackupManager, "_create_tarfile", cancel_backup)

    result = BackupManager.export_backup(config, "full", str(tmp_path / "backup"))

    assert not result.status
    assert result.message == "cancelled"
    assert TaskManager._TASKS == {}
