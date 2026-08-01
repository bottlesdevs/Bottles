from bottles.backend.globals import Paths
from bottles.backend.managers.library import LibraryManager
from bottles.backend.managers.steam import SteamManager
from bottles.backend.managers.steamgriddb import SteamGridDBManager
from bottles.backend.models.config import BottleConfig


def test_steam_refresh_preserves_library_grids(tmp_path, monkeypatch):
    monkeypatch.setattr(Paths, "steam", str(tmp_path))
    grid = tmp_path / "123" / "grids" / "cover.png"
    grid.parent.mkdir(parents=True)
    grid.write_bytes(b"cover")
    stale = tmp_path / "456"
    stale.mkdir()

    config = BottleConfig(
        Name="Example Game",
        Path="/steamapps/compatdata/123/pfx",
        Environment="Steam",
        CompatData="123",
    )
    manager = object.__new__(SteamManager)
    manager.list_prefixes = lambda: {"123": config}

    manager.update_bottles()

    assert grid.read_bytes() == b"cover"
    assert (tmp_path / "123" / "bottle.yml").is_file()
    assert not stale.exists()


def test_steam_library_entry_roundtrips_and_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(LibraryManager, "library_path", str(tmp_path / "library.yml"))
    monkeypatch.setattr(SteamGridDBManager, "get_game_grid", lambda *_args: None)
    config = BottleConfig(
        Name="Example Game",
        Path="/steamapps/compatdata/123/pfx",
        Environment="Steam",
        CompatData="123",
    )
    data = {
        "bottle": {"name": "123", "path": config.Path},
        "name": "Example Game",
        "id": "steam:123",
        "steam": True,
    }

    manager = LibraryManager()
    manager.add_to_library(data, config)
    manager = LibraryManager()
    manager.add_to_library(data, config)

    assert list(manager.get_library().values()) == [data]
