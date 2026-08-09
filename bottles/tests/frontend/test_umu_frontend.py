from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from bottles.frontend.utils.umu import UmuFrontendProvider


class Repository:
    root = "/data/umu"

    def __init__(self, games, discovered=None):
        self.games = games
        self.discovered = discovered or []

    def list_games(self):
        return self.games

    def discover_standard_prefixes(self):
        return self.discovered

    def prefix_path(self, game):
        return f"{self.root}/prefixes/{game.id}"


class Settings:
    def __init__(self, values):
        self.values = values

    def get_string(self, key):
        return self.values[key]


class Manager:
    def __init__(self):
        self.settings = Settings(
            {
                "umu-proton": "GE-Proton9-27",
                "umu-dependency-tool": "bottles",
            }
        )
        self.umu_error = ""
        self.refreshes = []

    def get_umu_installation(self, refresh=False):
        self.refreshes.append(refresh)
        return SimpleNamespace(
            path="/usr/bin/umu-run",
            version="1.2.9",
            source="system",
        )


def _game(game_id, name, *, managed=True):
    return SimpleNamespace(
        id=UUID(game_id),
        library_id=f"umu:{game_id}",
        name=name,
        proton="GE-Proton9-27",
        store="gog",
        state="ready",
        prefix=SimpleNamespace(managed=managed),
    )


def test_unavailable_provider_has_no_prefixes():
    provider = UmuFrontendProvider()

    assert provider.available is False
    assert provider.list_prefixes() == []
    assert provider.get_status() == {
        "available": False,
        "game_count": 0,
        "discovered_count": 0,
        "root": "",
        "runtime_root": "",
        "standard_prefix_root": "",
        "installation": None,
        "error": "",
        "default_proton": "",
        "dependency_tool": "",
    }


def test_provider_maps_umu_games_without_bottle_configs():
    alpha_id = "14f15146-88af-46ae-ab8d-ca45b6fa6cbf"
    zeta_id = "be3b1681-1d56-4ea6-bafe-dd4510757359"
    repository = Repository(
        [
            _game(zeta_id, "Zeta", managed=False),
            _game(alpha_id, "Alpha"),
        ]
    )

    entries = UmuFrontendProvider(repository).list_prefixes()

    assert entries == [
        {
            "id": f"umu:{alpha_id}",
            "source": "umu",
            "source_id": alpha_id,
            "name": "Alpha",
            "path": f"/data/umu/prefixes/{alpha_id}",
            "proton": "GE-Proton9-27",
            "store": "gog",
            "state": "ready",
            "managed": True,
            "detected": False,
        },
        {
            "id": f"umu:{zeta_id}",
            "source": "umu",
            "source_id": zeta_id,
            "name": "Zeta",
            "path": f"/data/umu/prefixes/{zeta_id}",
            "proton": "GE-Proton9-27",
            "store": "gog",
            "state": "ready",
            "managed": False,
            "detected": False,
        },
    ]


def test_provider_status_reads_repository_state():
    repository = Repository([_game("14f15146-88af-46ae-ab8d-ca45b6fa6cbf", "Alpha")])
    manager = Manager()

    status = UmuFrontendProvider(repository, manager).get_status(refresh=True)

    assert status == {
        "available": True,
        "game_count": 1,
        "discovered_count": 0,
        "root": "/data/umu",
        "runtime_root": str(Path.home().joinpath(".local", "share", "umu")),
        "standard_prefix_root": str(Path.home().joinpath("Games", "umu")),
        "installation": SimpleNamespace(
            path="/usr/bin/umu-run",
            version="1.2.9",
            source="system",
        ),
        "error": "",
        "default_proton": "GE-Proton9-27",
        "dependency_tool": "bottles",
    }
    assert manager.refreshes == [True]


def test_provider_maps_detected_standard_prefix(tmp_path):
    prefix = tmp_path / "Games" / "umu" / "umu-1234"
    repository = Repository([], [prefix])

    entries = UmuFrontendProvider(repository).list_prefixes()

    assert len(entries) == 1
    assert entries[0] == {
        "id": entries[0]["id"],
        "source": "umu",
        "source_id": str(prefix),
        "name": "umu-1234",
        "path": str(prefix),
        "proton": "",
        "store": "none",
        "state": "detected",
        "managed": False,
        "detected": True,
        "game_id": "umu-1234",
    }
