import base64
from pathlib import Path

import pytest

from bottles.backend.globals import Paths
from bottles.backend.managers import library as library_module
from bottles.backend.managers import steamgriddb as steamgriddb_module
from bottles.backend.managers.library import LibraryManager
from bottles.backend.managers.thumbnail import ThumbnailManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.umu import UmuGameRepository
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
    monkeypatch.setattr(
        library_module.SteamGridDBManager,
        "get_game_grid",
        lambda *_args: None,
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
    second_cover.write_bytes(PNG_DATA + b"\n")

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
    assert new_cover.read_bytes() == PNG_DATA + b"\n"
    assert not old_cover.exists()


def test_set_thumbnail_reuses_identical_managed_cover(tmp_path, library_manager):
    manager, bottle_path = library_manager
    program_folder = tmp_path / "program"
    program_folder.mkdir()
    first_cover = tmp_path / "first.png"
    second_cover = tmp_path / "second.png"
    _write_cover(first_cover)
    _write_cover(second_cover)
    config = _config(program_folder)
    thumbnail = manager.import_thumbnail(first_cover, config)
    entry_uuid = manager.add_to_library({**_entry(), "thumbnail": thumbnail}, config)

    assert manager.set_thumbnail(entry_uuid, second_cover, config)

    assert manager.get_library()[entry_uuid]["thumbnail"] == thumbnail
    assert (bottle_path / "grids" / thumbnail.removeprefix("grid:")).exists()


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


def test_remove_from_library_removes_managed_cover(tmp_path, library_manager):
    manager, bottle_path = library_manager
    program_folder = tmp_path / "program"
    program_folder.mkdir()
    cover = tmp_path / "cover.png"
    _write_cover(cover)
    config = _config(program_folder)
    thumbnail = manager.import_thumbnail(cover, config)
    entry_uuid = manager.add_to_library({**_entry(), "thumbnail": thumbnail}, config)
    stored_cover = bottle_path / "grids" / thumbnail.removeprefix("grid:")

    manager.remove_from_library(entry_uuid, config)

    assert entry_uuid not in manager.get_library()
    assert not stored_cover.exists()


def test_import_thumbnail_reuses_identical_cover(tmp_path, library_manager):
    manager, bottle_path = library_manager
    program_folder = tmp_path / "program"
    program_folder.mkdir()
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    _write_cover(first)
    _write_cover(second)
    config = _config(program_folder)

    first_thumbnail = manager.import_thumbnail(first, config)
    second_thumbnail = manager.import_thumbnail(second, config)

    assert second_thumbnail == first_thumbnail
    assert len(list((bottle_path / "grids").iterdir())) == 1


def test_umu_entry_does_not_require_bottle_config(
    monkeypatch, tmp_path, library_manager
):
    manager, _bottle_path = library_manager
    monkeypatch.setattr(Paths, "base", str(tmp_path / "data"))
    monkeypatch.setattr(
        library_module.SteamGridDBManager,
        "get_game_grid",
        lambda *_args: pytest.fail("UMU cover lookup must run asynchronously"),
    )

    manager.add_to_library(
        {
            "id": "umu:5f99167d-0a72-477b-b995-bb628770e438",
            "source": "umu",
            "source_id": "5f99167d-0a72-477b-b995-bb628770e438",
            "name": "Control",
        }
    )

    entry = next(iter(manager.get_library().values()))
    assert entry["source"] == "umu"
    assert entry["name"] == "Control"
    assert "thumbnail" not in entry


def test_umu_thumbnail_uses_separate_cover_storage(
    monkeypatch, tmp_path, library_manager
):
    manager, _bottle_path = library_manager
    monkeypatch.setattr(Paths, "base", str(tmp_path / "data"))
    cover = tmp_path / "cover.png"
    _write_cover(cover)
    manager.add_to_library(
        {
            "id": "umu:5f99167d-0a72-477b-b995-bb628770e438",
            "source": "umu",
            "source_id": "5f99167d-0a72-477b-b995-bb628770e438",
            "name": "Control",
        }
    )
    entry_uuid = next(iter(manager.get_library()))

    assert manager.set_thumbnail(entry_uuid, cover)

    thumbnail = manager.get_library()[entry_uuid]["thumbnail"]
    assert thumbnail.startswith("umu-grid:")
    stored = ThumbnailManager.get_path(None, thumbnail)
    assert stored is not None
    assert Path(stored).read_bytes() == PNG_DATA


def test_umu_remote_thumbnail_uses_separate_cover_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(Paths, "base", str(tmp_path / "data"))

    class SearchResponse:
        status_code = 200

        @staticmethod
        def json():
            return "https://example.com/control.png"

    class ImageResponse:
        content = PNG_DATA

    monkeypatch.setattr(
        steamgriddb_module.requests,
        "get",
        lambda url, **_kwargs: ImageResponse()
        if url == "https://example.com/control.png"
        else SearchResponse(),
    )

    thumbnail = library_module.SteamGridDBManager.get_game_grid("Control")

    assert thumbnail.startswith("umu-grid:")
    stored = ThumbnailManager.get_path(None, thumbnail)
    assert stored is not None
    assert Path(stored).read_bytes() == PNG_DATA


def test_remote_thumbnail_preserves_new_library_entries(
    monkeypatch, tmp_path, library_manager
):
    manager, _bottle_path = library_manager
    first_id = manager.add_to_library(
        {
            "id": "umu:first",
            "source": "umu",
            "source_id": "first",
            "name": "First",
        }
    )

    def download_cover(*_args):
        LibraryManager().add_to_library(
            {
                "id": "umu:second",
                "source": "umu",
                "source_id": "second",
                "name": "Second",
            }
        )
        return "umu-grid:first.png"

    monkeypatch.setattr(
        library_module.SteamGridDBManager,
        "get_game_grid",
        download_cover,
    )

    assert manager.download_thumbnail(first_id)

    entries = LibraryManager().get_library()
    assert len(entries) == 2
    assert entries[first_id]["thumbnail"] == "umu-grid:first.png"


def test_remote_thumbnail_does_not_replace_newer_selection(
    monkeypatch, tmp_path, library_manager
):
    manager, _bottle_path = library_manager
    first_id = manager.add_to_library(
        {
            "id": "umu:first",
            "source": "umu",
            "source_id": "first",
            "name": "First",
        }
    )

    def download_cover(*_args):
        current = LibraryManager()
        current.load_library(silent=True)
        current.get_library()[first_id]["thumbnail"] = "umu-grid:manual.png"
        current.save_library()
        return "umu-grid:auto.png"

    monkeypatch.setattr(
        library_module.SteamGridDBManager,
        "get_game_grid",
        download_cover,
    )

    assert manager.download_thumbnail(first_id) is False
    assert LibraryManager().get_library()[first_id]["thumbnail"] == (
        "umu-grid:manual.png"
    )


def test_remote_thumbnail_replaces_missing_managed_cover(
    monkeypatch, tmp_path, library_manager
):
    manager, _bottle_path = library_manager
    program_folder = tmp_path / "program"
    program_folder.mkdir()
    entry_id = manager.add_to_library(
        {**_entry(), "thumbnail": "grid:missing.png"},
        _config(program_folder),
    )
    monkeypatch.setattr(
        library_module.SteamGridDBManager,
        "get_game_grid",
        lambda *_args: "grid:replacement.png",
    )

    assert manager.download_thumbnail(entry_id, _config(program_folder))
    assert manager.get_library()[entry_id]["thumbnail"] == "grid:replacement.png"


def test_sync_umu_game_updates_existing_library_entry(tmp_path, library_manager):
    manager, _bottle_path = library_manager
    repository = UmuGameRepository(tmp_path / "umu")
    game = repository.new_game("Control", tmp_path / "Control.exe", proton="GE-Proton")
    repository.save(game)

    manager.sync_umu_game(game)
    updated = repository.update(game, name="Control Ultimate Edition", store="gog")
    manager.sync_umu_game(updated)

    entries = list(manager.get_library().values())
    assert len(entries) == 1
    assert entries[0]["name"] == "Control Ultimate Edition"
    assert entries[0]["store"] == "gog"


def test_remove_umu_game_keeps_other_entries(tmp_path, library_manager):
    manager, _bottle_path = library_manager
    repository = UmuGameRepository(tmp_path / "umu")
    first = repository.new_game("First", tmp_path / "first.exe", proton="GE-Proton")
    second = repository.new_game("Second", tmp_path / "second.exe", proton="GE-Proton")
    manager.sync_umu_game(first)
    manager.sync_umu_game(second)

    manager.remove_umu_game(str(first.id))

    entries = list(manager.get_library().values())
    assert len(entries) == 1
    assert entries[0]["id"] == second.library_id


def test_remove_bottle_entries_ignores_umu_entries(tmp_path, library_manager):
    manager, _bottle_path = library_manager
    program_folder = tmp_path / "program"
    program_folder.mkdir()
    config = _config(program_folder)
    bottle_id = manager.add_to_library(_entry(), config)
    umu_id = manager.add_to_library(
        {
            "id": "umu:1",
            "source": "umu",
            "source_id": "1",
            "name": "UMU Game",
        }
    )

    manager.remove_bottle_entries(config.Name)

    assert bottle_id not in manager.get_library()
    assert umu_id in manager.get_library()
