# umu.py
#
# Copyright 2026 mirkobrombin <brombin94@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from gettext import gettext as _
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


UMU_STORE_LABELS = {
    "none": _("Game"),
    "amazon": "Amazon",
    "battlenet": "Battle.net",
    "ea": "EA",
    "egs": "Epic Games",
    "gog": "GOG",
    "humble": "Humble",
    "itchio": "itch.io",
    "steam": "Steam",
    "ubisoft": "Ubisoft Connect",
    "umu": "UMU",
    "zoomplatform": "ZOOM Platform",
}


def get_umu_store_title(store):
    return UMU_STORE_LABELS.get(store, store)


class UmuFrontendProvider:
    def __init__(self, repository=None, manager=None):
        self.repository = repository
        self.manager = manager

    @classmethod
    def from_backend(cls, manager):
        try:
            from bottles.backend.umu import UmuGameRepository
        except ImportError:
            return cls(manager=manager)

        repository = getattr(manager, "umu_repository", None)
        return cls(repository or UmuGameRepository(), manager)

    @property
    def available(self):
        return self.repository is not None

    def get_status(self, refresh=False):
        if not self.available:
            return {
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

        games = self.repository.list_games()
        discovered = self.repository.discover_standard_prefixes()
        installation = None
        if self.manager is not None and hasattr(self.manager, "get_umu_installation"):
            installation = self.manager.get_umu_installation(refresh=refresh)

        return {
            "available": True,
            "game_count": len(games),
            "discovered_count": len(discovered),
            "root": str(self.repository.root),
            "runtime_root": str(Path.home().joinpath(".local", "share", "umu")),
            "standard_prefix_root": str(Path.home().joinpath("Games", "umu")),
            "installation": installation,
            "error": getattr(self.manager, "umu_error", ""),
            "default_proton": self.__get_setting("umu-proton"),
            "dependency_tool": self.__get_setting("umu-dependency-tool"),
        }

    def __get_setting(self, key):
        settings = getattr(self.manager, "settings", None)
        if settings is None:
            return ""
        try:
            return settings.get_string(key)
        except (AttributeError, KeyError):
            return ""

    def list_prefixes(self):
        if not self.available:
            return []

        entries = []
        for game in self.repository.list_games():
            entries.append(self.__to_entry(game))
        for path in self.repository.discover_standard_prefixes():
            entries.append(self.__to_discovered_entry(path))

        return sorted(entries, key=lambda entry: entry["name"].casefold())

    def __to_entry(self, game):
        game_id = str(game.id)
        return {
            "id": game.library_id,
            "source": "umu",
            "source_id": game_id,
            "name": game.name,
            "path": str(self.repository.prefix_path(game)),
            "proton": game.proton,
            "store": game.store,
            "state": game.state,
            "managed": game.prefix.managed,
            "detected": False,
        }

    @staticmethod
    def __to_discovered_entry(path):
        detected_id = str(uuid5(NAMESPACE_URL, str(path)))
        return {
            "id": f"umu-detected:{detected_id}",
            "source": "umu",
            "source_id": str(path),
            "name": path.name,
            "path": str(path),
            "proton": "",
            "store": "none",
            "state": "detected",
            "managed": False,
            "detected": True,
            "game_id": path.name,
        }
