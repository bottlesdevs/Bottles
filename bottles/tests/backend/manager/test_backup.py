import os
import shutil
import tarfile
from concurrent.futures import CancelledError
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from bottles.backend.globals import Paths
from bottles.backend.managers.backup import BackupManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.state import SignalManager, Task, TaskManager
from bottles.backend.utils import yaml


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


def test_duplicate_bottle_preserves_hidden_files(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    drive_c = source / "drive_c"
    hidden_directory = drive_c / ".hidden-directory"
    hidden_directory.mkdir(parents=True)
    (drive_c / ".hidden-file").write_bytes(b"hidden")
    (hidden_directory / "payload.dat").write_bytes(b"payload")
    with (source / "bottle.yml").open("w") as config_file:
        yaml.dump({"Name": "Source", "Path": "Source"}, config_file)

    result = BackupManager._duplicate_bottle_directory(
        BottleConfig(Name="Source", Path="Source"),
        str(source),
        str(destination),
        "Destination",
    )

    assert result.status
    assert (destination / "drive_c/.hidden-file").read_bytes() == b"hidden"
    assert (
        destination / "drive_c/.hidden-directory/payload.dat"
    ).read_bytes() == b"payload"


def test_duplicate_bottle_replaces_spaces_in_destination_path(tmp_path, monkeypatch):
    monkeypatch.setattr(Paths, "bottles", str(tmp_path))
    source = tmp_path / "Source"
    (source / "drive_c").mkdir(parents=True)
    with (source / "bottle.yml").open("w") as config_file:
        yaml.dump({"Name": "Source", "Path": "Source"}, config_file)

    result = BackupManager.duplicate_bottle(
        BottleConfig(Name="Source", Path="Source"), "Destination Bottle"
    )

    assert result.status
    assert (tmp_path / "Destination-Bottle").is_dir()
    assert not (tmp_path / "Destination Bottle").exists()
    with (tmp_path / "Destination-Bottle/bottle.yml").open() as config_file:
        duplicate_config = yaml.load(config_file)
    assert duplicate_config["Name"] == "Destination Bottle"


def test_duplicate_bottle_appends_next_available_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr(Paths, "bottles", str(tmp_path))
    source = tmp_path / "Source"
    (source / "drive_c").mkdir(parents=True)
    with (source / "bottle.yml").open("w") as config_file:
        yaml.dump({"Name": "Source", "Path": "Source"}, config_file)

    for destination_name in ("Destination-Bottle", "Destination-Bottle__1"):
        destination = tmp_path / destination_name
        destination.mkdir()
        (destination / "marker").write_text("existing")

    result = BackupManager.duplicate_bottle(
        BottleConfig(Name="Source", Path="Source"), "Destination Bottle"
    )

    assert result.status
    assert (tmp_path / "Destination-Bottle/marker").read_text() == "existing"
    assert (tmp_path / "Destination-Bottle__1/marker").read_text() == "existing"
    with (tmp_path / "Destination-Bottle__2/bottle.yml").open() as config_file:
        duplicate_config = yaml.load(config_file)
    assert duplicate_config["Name"] == "Destination Bottle__2"


def test_duplicate_bottle_rejects_empty_name(tmp_path, monkeypatch):
    monkeypatch.setattr(Paths, "bottles", str(tmp_path))

    result = BackupManager.duplicate_bottle(
        BottleConfig(Name="Source", Path="Source"), "   "
    )

    assert not result.status
    assert not list(tmp_path.iterdir())


def test_duplicate_bottle_does_not_overwrite_existing_destination(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    (source / "drive_c").mkdir(parents=True)
    destination.mkdir()
    marker = destination / "marker"
    marker.write_text("existing")

    result = BackupManager._duplicate_bottle_directory(
        BottleConfig(Name="Source", Path="Source"),
        str(source),
        str(destination),
        "Destination",
    )

    assert not result.status
    assert marker.read_text() == "existing"


def test_duplicate_bottle_removes_partial_destination_after_failure(
    tmp_path, monkeypatch
):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    (source / "drive_c").mkdir(parents=True)

    def fail_copytree(*_args, **_kwargs):
        raise shutil.Error("copy failed")

    monkeypatch.setattr(shutil, "copytree", fail_copytree)

    result = BackupManager._duplicate_bottle_directory(
        BottleConfig(Name="Source", Path="Source"),
        str(source),
        str(destination),
        "Destination",
    )

    assert not result.status
    assert not destination.exists()


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


def test_program_backup_copies_selected_paths_and_writes_manifest(
    tmp_path, monkeypatch
):
    bottle = tmp_path / "bottle"
    saves = bottle / "drive_c" / "users" / "player" / "Saved Games"
    saves.mkdir(parents=True)
    (saves / "slot.sav").write_bytes(b"save-data")
    destination = tmp_path / "backups"
    destination.mkdir()
    config = BottleConfig(Name="Test Bottle", Path="TestBottle")
    program = {
        "id": "game-id",
        "name": "Test Game",
        "automatic_backup": {
            "enabled": True,
            "destination": str(destination),
            "paths": ["%BOTTLE_PATH%/drive_c/users/player/Saved Games"],
            "keep": 5,
        },
    }
    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )

    result = BackupManager.create_program_backup(config, program)

    assert result.status
    backup = Path(result.data["path"])
    assert (
        backup / "drive_c/users/player/Saved Games/slot.sav"
    ).read_bytes() == b"save-data"
    with (backup / "backup.yml").open() as manifest_file:
        manifest = yaml.load(manifest_file)
    assert manifest["bottle"] == "Test Bottle"
    assert manifest["program"] == "Test Game"
    assert manifest["paths"] == [
        {
            "source": "%BOTTLE_PATH%/drive_c/users/player/Saved Games",
            "backup": "drive_c/users/player/Saved Games",
        }
    ]


def test_program_backup_keeps_only_requested_generations(tmp_path, monkeypatch):
    bottle = tmp_path / "bottle"
    bottle.mkdir()
    save = bottle / "save.dat"
    save.write_bytes(b"save-data")
    destination = tmp_path / "backups"
    destination.mkdir()
    config = BottleConfig(Name="Bottle", Path="Bottle")
    program = {
        "id": "game-id",
        "name": "Game",
        "automatic_backup": {
            "enabled": True,
            "destination": str(destination),
            "paths": ["%BOTTLE_PATH%/save.dat"],
            "keep": 2,
        },
    }
    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )
    root = Path(BackupManager.get_program_backup_root(config, program))
    root.mkdir(parents=True)
    (root / "20260101-000000-000001").mkdir()
    (root / "20260102-000000-000001").mkdir()
    monkeypatch.setattr(
        BackupManager,
        "_program_backup_timestamp",
        staticmethod(lambda: "20260103-000000-000001"),
    )

    result = BackupManager.create_program_backup(config, program)

    assert result.status
    generations = sorted(path.name for path in root.iterdir())
    assert generations == [
        "20260102-000000-000001",
        "20260103-000000-000001",
    ]


def test_program_backup_is_atomic_after_copy_failure(tmp_path, monkeypatch):
    bottle = tmp_path / "bottle"
    bottle.mkdir()
    save = bottle / "save.dat"
    save.write_bytes(b"save-data")
    destination = tmp_path / "backups"
    destination.mkdir()
    config = BottleConfig(Name="Bottle", Path="Bottle")
    program = {
        "id": "game-id",
        "name": "Game",
        "automatic_backup": {
            "enabled": True,
            "destination": str(destination),
            "paths": ["%BOTTLE_PATH%/save.dat"],
            "keep": 5,
        },
    }
    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )
    root = Path(BackupManager.get_program_backup_root(config, program))
    root.mkdir(parents=True)
    previous = root / "20260101-000000-000001"
    previous.mkdir()
    monkeypatch.setattr(
        "bottles.backend.managers.backup.shutil.copy2",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("copy failed")),
    )

    result = BackupManager.create_program_backup(config, program)

    assert not result.status
    assert previous.is_dir()
    assert [path for path in root.iterdir() if path.name.startswith(".")] == []


def test_program_backup_preserves_symlinks(tmp_path, monkeypatch):
    bottle = tmp_path / "bottle"
    saves = bottle / "saves"
    saves.mkdir(parents=True)
    secret = tmp_path / "secret"
    secret.write_text("do not copy")
    (saves / "external").symlink_to(secret)
    destination = tmp_path / "backups"
    destination.mkdir()
    config = BottleConfig(Name="Bottle", Path="Bottle")
    program = {
        "id": "game-id",
        "name": "Game",
        "automatic_backup": {
            "enabled": True,
            "destination": str(destination),
            "paths": ["%BOTTLE_PATH%/saves"],
            "keep": 5,
        },
    }
    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )

    result = BackupManager.create_program_backup(config, program)

    assert result.status
    copied_link = Path(result.data["path"]) / "saves/external"
    assert copied_link.is_symlink()
    assert os.readlink(copied_link) == str(secret)


def test_program_backup_rejects_source_through_external_symlink(tmp_path, monkeypatch):
    bottle = tmp_path / "bottle"
    bottle.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.dat").write_bytes(b"private")
    (bottle / "external").symlink_to(outside, target_is_directory=True)
    destination = tmp_path / "backups"
    destination.mkdir()
    config = BottleConfig(Name="Bottle", Path="Bottle")
    program = {
        "name": "Game",
        "automatic_backup": {
            "enabled": True,
            "destination": str(destination),
            "paths": ["%BOTTLE_PATH%/external/private.dat"],
        },
    }
    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )

    result = BackupManager.create_program_backup(config, program)

    assert not result.status
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize(
    "paths",
    [
        ["%BOTTLE_PATH%/saves/slot.sav", "%BOTTLE_PATH%/saves"],
        ["%BOTTLE_PATH%/saves", "%BOTTLE_PATH%/saves/slot.sav"],
    ],
)
def test_program_backup_collapses_nested_paths(tmp_path, monkeypatch, paths):
    bottle = tmp_path / "bottle"
    saves = bottle / "saves"
    saves.mkdir(parents=True)
    (saves / "slot.sav").write_bytes(b"save-data")
    destination = tmp_path / "backups"
    destination.mkdir()
    config = BottleConfig(Name="Bottle", Path="Bottle")
    program = {
        "name": "Game",
        "automatic_backup": {
            "enabled": True,
            "destination": str(destination),
            "paths": paths,
        },
    }
    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )

    result = BackupManager.create_program_backup(config, program)

    assert result.status
    backup = Path(result.data["path"])
    assert (backup / "saves/slot.sav").read_bytes() == b"save-data"
    with (backup / "backup.yml").open() as manifest_file:
        manifest = yaml.load(manifest_file)
    assert manifest["paths"] == [{"source": "%BOTTLE_PATH%/saves", "backup": "saves"}]


def test_program_backup_rejects_destination_inside_selected_directory(
    tmp_path, monkeypatch
):
    bottle = tmp_path / "bottle"
    saves = bottle / "saves"
    destination = saves / "backups"
    destination.mkdir(parents=True)
    (saves / "slot.sav").write_bytes(b"save-data")
    config = BottleConfig(Name="Bottle", Path="Bottle")
    program = {
        "id": "game-id",
        "name": "Game",
        "automatic_backup": {
            "enabled": True,
            "destination": str(destination),
            "paths": ["%BOTTLE_PATH%/saves"],
            "keep": 5,
        },
    }
    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )

    result = BackupManager.create_program_backup(config, program)

    assert not result.status
    assert list(destination.iterdir()) == []


def test_program_backup_rejects_sources_outside_bottle(tmp_path, monkeypatch):
    bottle = tmp_path / "bottle"
    bottle.mkdir()
    outside = tmp_path / "outside.dat"
    outside.write_bytes(b"private")
    destination = tmp_path / "backups"
    destination.mkdir()
    config = BottleConfig(Name="Bottle", Path="Bottle")
    program = {
        "name": "Game",
        "automatic_backup": {
            "enabled": True,
            "destination": str(destination),
            "paths": [str(outside)],
        },
    }
    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )

    result = BackupManager.create_program_backup(config, program)

    assert not result.status
    assert list(destination.iterdir()) == []


def test_program_backup_paths_stay_inside_bottle(tmp_path, monkeypatch):
    bottle = tmp_path / "bottle"
    bottle.mkdir()
    save = bottle / "save.dat"
    save.touch()
    outside = tmp_path / "outside.dat"
    outside.touch()
    config = BottleConfig(Name="Bottle", Path="Bottle")
    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )

    assert BackupManager.serialize_program_backup_path(config, str(save)) == (
        "%BOTTLE_PATH%/save.dat"
    )
    assert BackupManager.serialize_program_backup_path(config, str(bottle)) is None
    assert BackupManager.serialize_program_backup_path(config, str(outside)) is None
    assert BackupManager.resolve_program_backup_path(config, "%BOTTLE_PATH%") is None
    assert BackupManager.resolve_program_backup_path(config, str(save)) is None
    assert (
        BackupManager.resolve_program_backup_path(
            config, "%BOTTLE_PATH%/../outside.dat"
        )
        is None
    )


def test_program_backup_rejects_destination_inside_bottle_for_file_source(
    tmp_path, monkeypatch
):
    bottle = tmp_path / "bottle"
    bottle.mkdir()
    save = bottle / "save.dat"
    save.write_bytes(b"save-data")
    destination = bottle / "backups"
    destination.mkdir()
    config = BottleConfig(Name="Bottle", Path="Bottle")
    program = {
        "name": "Game",
        "automatic_backup": {
            "enabled": True,
            "destination": str(destination),
            "paths": ["%BOTTLE_PATH%/save.dat"],
        },
    }
    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )

    result = BackupManager.create_program_backup(config, program)

    assert not result.status
    assert list(destination.iterdir()) == []


def test_program_backup_rejects_destination_symlinked_into_bottle(
    tmp_path, monkeypatch
):
    bottle = tmp_path / "bottle"
    destination_target = bottle / "backups"
    destination_target.mkdir(parents=True)
    destination = tmp_path / "backups-link"
    destination.symlink_to(destination_target, target_is_directory=True)
    save = bottle / "save.dat"
    save.write_bytes(b"save-data")
    config = BottleConfig(Name="Bottle", Path="Bottle")
    program = {
        "name": "Game",
        "automatic_backup": {
            "enabled": True,
            "destination": str(destination),
            "paths": ["%BOTTLE_PATH%/save.dat"],
        },
    }
    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )

    result = BackupManager.create_program_backup(config, program)

    assert not result.status
    assert list(destination_target.iterdir()) == []


def test_program_backup_rejects_symlinked_program_root(tmp_path, monkeypatch):
    bottle = tmp_path / "bottle"
    bottle.mkdir()
    save = bottle / "save.dat"
    save.write_bytes(b"save-data")
    destination = tmp_path / "backups"
    destination.mkdir()
    (destination / "Bottle").symlink_to(bottle, target_is_directory=True)
    config = BottleConfig(Name="Bottle", Path="Bottle")
    program = {
        "name": "Game",
        "automatic_backup": {
            "enabled": True,
            "destination": str(destination),
            "paths": ["%BOTTLE_PATH%/save.dat"],
        },
    }
    monkeypatch.setattr(
        "bottles.backend.managers.backup.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )

    result = BackupManager.create_program_backup(config, program)

    assert not result.status
    assert not (bottle / "Game").exists()


def test_program_backup_names_cannot_escape_destination(tmp_path):
    destination = tmp_path / "backups"
    config = BottleConfig(Name="..", Path="Bottle")
    program = {
        "name": ".",
        "automatic_backup": {"destination": str(destination)},
    }

    root = BackupManager.get_program_backup_root(config, program)

    assert root == str(destination / "Bottle" / "Program")


def test_program_backup_roots_separate_programs_with_the_same_name(tmp_path):
    destination = tmp_path / "backups"
    config = BottleConfig(Name="Bottle", Path="Bottle")
    settings = {"destination": str(destination)}

    first = BackupManager.get_program_backup_root(
        config,
        {"id": "first-id", "name": "Game", "automatic_backup": settings},
    )
    second = BackupManager.get_program_backup_root(
        config,
        {"id": "second-id", "name": "Game", "automatic_backup": settings},
    )

    assert first == str(destination / "Bottle" / "Game-first-id")
    assert second == str(destination / "Bottle" / "Game-second-id")
