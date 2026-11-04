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


def _external_source(tmp_path, monkeypatch):
    internal = tmp_path / "Bottles"
    external = tmp_path / "External Drive"
    source = tmp_path / "Source"
    internal.mkdir()
    external.mkdir()
    (source / "drive_c").mkdir(parents=True)
    (source / "drive_c/document.txt").write_text("Keep this document")
    config = BottleConfig(Name="Source", Path=str(source), Custom_Path=True, Notes="Installation notes")
    config.dump(str(source / "bottle.yml"))
    monkeypatch.setattr(Paths, "bottles", str(internal))
    return config, source, internal, external


@pytest.mark.parametrize("custom", [False, True])
def test_duplicate_uses_the_selected_directory_and_keeps_the_source(tmp_path, monkeypatch, custom):
    config, source, internal, external = _external_source(tmp_path, monkeypatch)
    root = external if custom else internal

    result = BackupManager.duplicate_bottle(config, "New Copy", str(root))

    assert result.ok
    target = root / "New-Copy"
    assert (target / "drive_c/document.txt").read_text() == "Keep this document"
    assert (source / "drive_c/document.txt").read_text() == "Keep this document"
    copied = BottleConfig.load(str(target / "bottle.yml"))
    assert copied.ok and copied.data.Notes == config.Notes
    assert copied.data.Custom_Path is custom
    assert copied.data.Path == str(target)
    if custom:
        with (internal / "New-Copy/placeholder.yml").open() as file:
            assert yaml.load(file) == {"Path": str(target)}
    else:
        assert not (target / "placeholder.yml").exists()


@pytest.mark.parametrize("inside", [False, True])
def test_duplicate_rejects_full_or_recursive_destinations(tmp_path, monkeypatch, inside):
    config, source, internal, external = _external_source(tmp_path, monkeypatch)
    if inside:
        destination = external / "link-to-source"
        destination.symlink_to(source / "drive_c", target_is_directory=True)
    else:
        destination = external
        monkeypatch.setattr(shutil, "disk_usage", lambda _path: SimpleNamespace(free=0))

    result = BackupManager.duplicate_bottle(config, "Copy", str(destination))

    assert not result.ok
    assert not (destination / "Copy").exists()
    assert not list(internal.iterdir())
    assert (source / "drive_c/document.txt").read_text() == "Keep this document"


def test_duplicate_avoids_collisions_in_the_bottle_catalog(tmp_path, monkeypatch):
    config, source, internal, external = _external_source(tmp_path, monkeypatch)
    (internal / "Copy").mkdir()
    (internal / "Copy/marker").write_text("Existing bottle")

    result = BackupManager.duplicate_bottle(config, "Copy", str(external))

    assert result.ok
    assert (external / "Copy__1/drive_c/document.txt").is_file()
    assert (internal / "Copy/marker").read_text() == "Existing bottle"


def test_duplicate_rolls_back_if_the_external_reference_cannot_be_saved(tmp_path, monkeypatch):
    config, source, internal, external = _external_source(tmp_path, monkeypatch)
    mkdir = os.mkdir
    def fail_reference(path, *args, **kwargs):
        if os.fspath(path) == str(internal / "Copy"):
            raise PermissionError("Cannot write reference")
        return mkdir(path, *args, **kwargs)
    monkeypatch.setattr(os, "mkdir", fail_reference)

    result = BackupManager.duplicate_bottle(config, "Copy", str(external))

    assert not result.ok
    assert not (external / "Copy").exists()
    assert not (internal / "Copy").exists()
    assert (source / "drive_c/document.txt").read_text() == "Keep this document"


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


@pytest.mark.parametrize("external", [False, True])
@pytest.mark.parametrize("to_default", [False, True])
def test_move_preserves_full_prefix_and_registration(tmp_path, monkeypatch, external, to_default):
    from bottles.backend.wine.wineserver import WineServer
    config, source, internal, destination = _external_source(tmp_path, monkeypatch)
    reference = internal / "Source"
    if external:
        reference.mkdir()
        (reference / "placeholder.yml").write_text(yaml.dump({"Path": str(source)}))
    else:
        shutil.move(source, reference)
        source = reference
        config.Path = "Source"
        config.Custom_Path = False
    monkeypatch.setattr(WineServer, "is_alive", lambda self: False)
    if to_default and not external:
        result = BackupManager.move_bottle(config, str(internal))
        assert not result.status
        assert source.is_dir()
        return
    config.WorkingDir = str(source / "drive_c")
    config.External_Programs = {"game": {"name": "Game", "path": str(source / "drive_c/game.exe"), "folder": str(source / "drive_c"), "icon": "/other/icon.png"}}
    config.dump(str(source / "bottle.yml"))
    (source / "dosdevices").mkdir()
    (source / "dosdevices/c:").symlink_to("../drive_c")
    (source / "dosdevices/z:").symlink_to("/")
    (source / "dosdevices/d:").symlink_to(source / "drive_c")
    (source / "logs").mkdir()
    (source / "logs/run.log").write_text("Keep logs")
    (source / ".hidden").write_text("Keep metadata")
    parent = internal if to_default else destination
    target = parent / "Source"

    result = BackupManager.move_bottle(config, str(parent))

    assert result.status, result.message
    assert not (source / "drive_c").exists()
    assert (target / "logs/run.log").read_text() == "Keep logs"
    assert (target / ".hidden").read_text() == "Keep metadata"
    assert os.readlink(target / "dosdevices/c:") == "../drive_c"
    assert os.readlink(target / "dosdevices/z:") == "/"
    assert os.readlink(target / "dosdevices/d:") == str(target / "drive_c")
    loaded = BottleConfig.load(str(target / "bottle.yml")).data
    assert loaded.Name == "Source"
    assert loaded.Notes == "Installation notes"
    assert loaded.Custom_Path is (not to_default)
    assert loaded.WorkingDir == str(target / "drive_c")
    assert loaded.External_Programs["game"]["path"] == str(target / "drive_c/game.exe")
    assert loaded.External_Programs["game"]["icon"] == "/other/icon.png"
    if not to_default:
        assert yaml.load((reference / "placeholder.yml").read_text())["Path"] == str(target)
    assert not list(internal.glob(".bottles-move-*"))
    assert not list(parent.glob(".bottles-move-*"))


@pytest.mark.parametrize("failure", ["running", "space", "copy", "verification", "registration"])
def test_move_keeps_original_after_failure(tmp_path, monkeypatch, failure):
    from bottles.backend.wine.wineserver import WineServer
    config, source, internal, destination = _external_source(tmp_path, monkeypatch)
    reference = internal / "Source"
    reference.mkdir()
    original_reference = yaml.dump({"Path": str(source)})
    (reference / "placeholder.yml").write_text(original_reference)
    monkeypatch.setattr(WineServer, "is_alive", lambda self: failure == "running")
    if failure == "space":
        monkeypatch.setattr(shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    elif failure == "copy":
        def fail(*args, **kwargs):
            raise OSError("copy failed")
        monkeypatch.setattr(shutil, "copytree", fail)
    elif failure == "verification":
        copytree = shutil.copytree
        def corrupt(source, target, *args, **kwargs):
            result = copytree(source, target, *args, **kwargs)
            document = Path(target) / "drive_c/document.txt"
            if document.exists():
                document.write_text("corrupted")
            return result
        monkeypatch.setattr(shutil, "copytree", corrupt)
    elif failure == "registration":
        rename = os.rename
        def fail(source_path, target):
            if str(source_path).endswith("replacement"):
                raise OSError("registration failed")
            return rename(source_path, target)
        monkeypatch.setattr(os, "rename", fail)

    result = BackupManager.move_bottle(config, str(destination))

    assert not result.status
    assert (source / "drive_c/document.txt").read_text() == "Keep this document"
    assert (reference / "placeholder.yml").read_text() == original_reference
    assert config.Path == str(source)
    assert not list(destination.iterdir())
    assert not list(internal.glob(".bottles-move-*"))


def test_move_never_removes_an_existing_destination(tmp_path, monkeypatch):
    config, source, internal, destination = _external_source(tmp_path, monkeypatch)
    (internal / "Source").mkdir()
    (internal / "Source/placeholder.yml").write_text(yaml.dump({"Path": str(source)}))
    target = destination / "Source"
    target.mkdir()
    (target / "marker").write_text("Do not touch")

    assert not BackupManager.move_bottle(config, str(destination)).status
    assert (target / "marker").read_text() == "Do not touch"
    assert source.exists()


def test_move_keeps_recovery_copy_if_registration_and_rollback_fail(tmp_path, monkeypatch):
    from bottles.backend.wine.wineserver import WineServer
    config, source, internal, destination = _external_source(tmp_path, monkeypatch)
    reference = internal / "Source"
    shutil.move(source, reference)
    source = reference
    config.Path, config.Custom_Path = "Source", False
    config.dump(str(source / "bottle.yml"))
    monkeypatch.setattr(WineServer, "is_alive", lambda self: False)
    rename = os.rename

    def fail(source_path, target):
        if str(source_path).endswith(("replacement", "previous")):
            raise OSError("registration unavailable")
        return rename(source_path, target)

    monkeypatch.setattr(os, "rename", fail)
    result = BackupManager.move_bottle(config, str(destination))

    assert not result.status
    recovery, = internal.glob(".bottles-move-*/previous")
    assert (recovery / "drive_c/document.txt").read_text() == "Keep this document"
    assert not list(destination.iterdir())


@pytest.mark.parametrize("stage", ["copy", "finish"])
def test_move_refuses_a_prefix_that_changes_during_copy(tmp_path, monkeypatch, stage):
    from bottles.backend.wine.wineserver import WineServer
    config, source, internal, destination = _external_source(tmp_path, monkeypatch)
    reference = internal / "Source"
    reference.mkdir()
    (reference / "placeholder.yml").write_text(yaml.dump({"Path": str(source)}))
    calls = []

    def is_alive(self):
        calls.append(True)
        return stage == "finish" and len(calls) > 1

    monkeypatch.setattr(WineServer, "is_alive", is_alive)
    if stage == "copy":
        copytree = shutil.copytree
        def change(source_path, target, *args, **kwargs):
            result = copytree(source_path, target, *args, **kwargs)
            if str(source_path) == str(source):
                (source / "drive_c/new.txt").write_text("New data")
            return result
        monkeypatch.setattr(shutil, "copytree", change)

    assert not BackupManager.move_bottle(config, str(destination)).status
    assert (source / "drive_c/document.txt").exists()
    assert (reference / "placeholder.yml").exists()
    assert not list(destination.iterdir())
