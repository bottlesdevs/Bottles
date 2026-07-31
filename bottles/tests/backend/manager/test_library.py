import base64
from pathlib import Path

import pytest

from bottles.backend.managers import library as library_module
from bottles.backend.managers.library import LibraryManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils

PNG_DATA = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zwe0AAAAASUVORK5CYII="
)


def _write_cover(path: Path) -> None:
    path.write_bytes(PNG_DATA)


@pytest.fixture
def library_manager(monkeypatch, tmp_path):
    library_path = tmp_path / "library.yml"
    bottle_path = tmp_path / "bottle"
    bottle_path.mkdir()

    monkeypatch.setattr(LibraryManager, "library_path", str(library_path))
    monkeypatch.setattr(
        ManagerUtils,
        "get_bottle_path",
        lambda _config: str(bottle_path),
    )

    return LibraryManager(), bottle_path


def _config(program_folder: Path) -> BottleConfig:
    return BottleConfig(
        Name="Games",
        Path="Games",
        External_Programs={
            "program-id": {
                "id": "program-id",
                "name": "Example",
                "executable": "example.exe",
                "path": str(program_folder / "example.exe"),
                "folder": str(program_folder / "working-directory"),
            }
        },
    )


def _entry() -> dict:
    return {
        "bottle": {"name": "Games", "path": "Games"},
        "name": "Example",
        "id": "program-id",
        "icon": "com.usebottles.bottles-program",
    }


def test_add_to_library_prefers_cover_next_to_program(
    monkeypatch, tmp_path, library_manager
):
    manager, bottle_path = library_manager
    program_folder = tmp_path / "program"
    program_folder.mkdir()
    program_cover = program_folder / "example.exe.png"
    _write_cover(program_cover)
    _write_cover(bottle_path / "library.png")

    monkeypatch.setattr(
        library_module.SteamGridDBManager,
        "get_game_grid",
        lambda *_args: pytest.fail("remote cover lookup should not run"),
    )

    manager.add_to_library(_entry(), _config(program_folder))

    entry = next(iter(manager.get_library().values()))
    assert entry["thumbnail"].startswith("grid:")
    cover = bottle_path / "grids" / entry["thumbnail"].removeprefix("grid:")
    assert cover.read_bytes() == PNG_DATA


def test_add_to_library_uses_bottle_cover_before_remote(
    monkeypatch, tmp_path, library_manager
):
    manager, bottle_path = library_manager
    program_folder = tmp_path / "program"
    program_folder.mkdir()
    _write_cover(bottle_path / "library.png")

    monkeypatch.setattr(
        library_module.SteamGridDBManager,
        "get_game_grid",
        lambda *_args: pytest.fail("remote cover lookup should not run"),
    )

    manager.add_to_library(_entry(), _config(program_folder))

    entry = next(iter(manager.get_library().values()))
    cover = bottle_path / "grids" / entry["thumbnail"].removeprefix("grid:")
    assert cover.read_bytes() == PNG_DATA


def test_add_to_library_ignores_invalid_local_cover(
    monkeypatch, tmp_path, library_manager
):
    manager, _bottle_path = library_manager
    program_folder = tmp_path / "program"
    program_folder.mkdir()
    (program_folder / "example.exe.png").write_bytes(b"not an image")
    remote_lookups = []

    monkeypatch.setattr(
        library_module.SteamGridDBManager,
        "get_game_grid",
        lambda *_args: remote_lookups.append(True),
    )

    manager.add_to_library(_entry(), _config(program_folder))

    entry = next(iter(manager.get_library().values()))
    assert entry.get("thumbnail") is None
    assert remote_lookups == [True]


def test_set_thumbnail_replaces_managed_cover(tmp_path, library_manager):
    manager, bottle_path = library_manager
    program_folder = tmp_path / "program"
    program_folder.mkdir()
    first_cover = tmp_path / "first.png"
    _write_cover(first_cover)
    second_cover = tmp_path / "second.jpg"
    _write_cover(second_cover)

    manager.add_to_library(
        {
            **_entry(),
            "thumbnail": manager.import_thumbnail(first_cover, _config(program_folder)),
        },
        _config(program_folder),
    )
    entry_uuid, entry = next(iter(manager.get_library().items()))
    old_cover = bottle_path / "grids" / entry["thumbnail"].removeprefix("grid:")

    assert manager.set_thumbnail(entry_uuid, second_cover, _config(program_folder))

    entry = manager.get_library()[entry_uuid]
    new_cover = bottle_path / "grids" / entry["thumbnail"].removeprefix("grid:")
    assert new_cover.read_bytes() == PNG_DATA
    assert not old_cover.exists()


def test_set_thumbnail_keeps_cover_used_by_another_entry(tmp_path, library_manager):
    manager, bottle_path = library_manager
    program_folder = tmp_path / "program"
    program_folder.mkdir()
    first_cover = tmp_path / "first.png"
    _write_cover(first_cover)
    second_cover = tmp_path / "second.png"
    _write_cover(second_cover)
    config = _config(program_folder)
    thumbnail = manager.import_thumbnail(first_cover, config)

    manager.add_to_library({**_entry(), "thumbnail": thumbnail}, config)
    manager.add_to_library(
        {**_entry(), "id": "other-program-id", "thumbnail": thumbnail}, config
    )
    entry_uuid = next(iter(manager.get_library()))
    old_cover = bottle_path / "grids" / thumbnail.removeprefix("grid:")

    assert manager.set_thumbnail(entry_uuid, second_cover, config)
    assert old_cover.exists()
