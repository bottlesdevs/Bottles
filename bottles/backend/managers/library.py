# library.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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

import filecmp
import os
import shutil
import threading
import uuid
from pathlib import Path
from typing import Optional

import gi

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.managers.steamgriddb import SteamGridDBManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils import yaml
from bottles.backend.utils.manager import ManagerUtils

gi.require_version("GdkPixbuf", "2.0")
# ruff: noqa: E402
from gi.repository import GdkPixbuf

logging = Logger()


class LibraryManager:
    """
    The LibraryManager class is used to store and retrieve data
    from the user library.yml file.
    """

    library_path: str = Paths.library
    __library: dict = {}
    __lock = threading.RLock()

    def __init__(self):
        self.load_library(silent=True)

    def load_library(self, silent=False):
        """
        Loads data from the library.yml file.
        """
        with self.__lock:
            if not os.path.exists(self.library_path):
                logging.warning("Library file not found, creating new one")
                self.__library = {}
                self.save_library()
            else:
                with open(self.library_path, "r") as library_file:
                    self.__library = yaml.load(library_file)

            if self.__library is None:
                self.__library = {}

            _tmp = self.__library.copy()
            for k, v in _tmp.items():
                if "id" not in v:
                    del self.__library[k]

            self.save_library(silent=silent)

    def add_to_library(self, data: dict, config: Optional[BottleConfig] = None):
        """
        Adds a new entry to the library.yml file.
        """
        source = data.get("source", "bottle")
        if config is None and source != "umu":
            logging.warning("A bottle config is required for this library entry")
            return

        if not data.get("thumbnail") and config is not None:
            for cover in self.__get_local_covers(data, config):
                data["thumbnail"] = self.import_thumbnail(cover, config)
                if data["thumbnail"]:
                    break

        if not data.get("thumbnail") and config is not None:
            try:
                data["thumbnail"] = SteamGridDBManager.get_game_grid(
                    data["name"], config
                )
            except Exception as e:
                logging.warning(f"Could not fetch thumbnail: {e}")

        with self.__lock:
            self.load_library(silent=True)
            if self.__already_in_library(data):
                logging.warning(f"Entry already in library, nothing to add: {data}")
                return

            _uuid = str(uuid.uuid4())
            logging.info(f"Adding new entry to library: {_uuid}")
            self.__library[_uuid] = data
            self.save_library()
            return _uuid

    def sync_umu_game(self, game):
        data = {
            "id": game.library_id,
            "source": "umu",
            "source_id": str(game.id),
            "name": game.name,
            "store": game.store,
        }
        with self.__lock:
            self.load_library(silent=True)
            for entry in self.__library.values():
                if entry.get("id") != game.library_id:
                    continue
                entry.update(data)
                self.save_library()
                return

            self.add_to_library(data)

    @staticmethod
    def __get_local_covers(data: dict, config: BottleConfig):
        program = config.External_Programs.get(data["id"], {})
        program_path = program.get("path")

        if program_path:
            executable = program_path.replace("\\", "/").rsplit("/", 1)[-1]
            folder = ManagerUtils.get_exe_parent_dir(config, program_path)
            yield os.path.join(folder, f"{executable}.png")

        yield os.path.join(ManagerUtils.get_bottle_path(config), "library.png")

    @staticmethod
    def import_thumbnail(source_path, config: Optional[BottleConfig] = None):
        source_path = os.fspath(source_path)
        if not os.path.isfile(source_path):
            return None

        image_format, width, height = GdkPixbuf.Pixbuf.get_file_info(source_path)
        if image_format is None or width <= 0 or height <= 0:
            logging.warning(f"Invalid library thumbnail: {source_path}")
            return None

        extension = os.path.splitext(source_path)[1].lower()
        if config is None:
            grids_path = Path(Paths.base) / "umu" / "covers"
            uri_prefix = "umu-grid:"
        else:
            grids_path = Path(ManagerUtils.get_bottle_path(config)) / "grids"
            uri_prefix = "grid:"
        filename = f"{uuid.uuid4()}{extension}"
        destination = grids_path / filename

        try:
            grids_path.mkdir(parents=True, exist_ok=True)
            for candidate in grids_path.iterdir():
                if candidate.is_file() and filecmp.cmp(
                    source_path, candidate, shallow=False
                ):
                    return f"{uri_prefix}{candidate.name}"
            shutil.copy2(source_path, destination)
        except OSError as error:
            logging.warning(f"Could not import library thumbnail: {error}")
            return None

        return f"{uri_prefix}{filename}"

    def set_thumbnail(
        self,
        _uuid: str,
        source_path,
        config: Optional[BottleConfig] = None,
    ):
        thumbnail = self.import_thumbnail(source_path, config)
        if thumbnail is None:
            return False

        with self.__lock:
            self.load_library(silent=True)
            entry = self.__library.get(_uuid)
            if entry is None:
                logging.warning(
                    f"Entry not found in library, can't set thumbnail: {_uuid}"
                )
                return False

            old_thumbnail = entry.get("thumbnail")
            entry["thumbnail"] = thumbnail
            self.save_library()

            thumbnail_is_shared = any(
                uuid != _uuid and item.get("thumbnail") == old_thumbnail
                for uuid, item in self.__library.items()
            )
        managed_prefix = "umu-grid:" if config is None else "grid:"
        if (
            old_thumbnail
            and old_thumbnail != thumbnail
            and old_thumbnail.startswith(managed_prefix)
            and not thumbnail_is_shared
        ):
            self.__remove_thumbnail(old_thumbnail, config)

        return True

    def download_thumbnail(self, _uuid: str, config: Optional[BottleConfig] = None):
        with self.__lock:
            self.load_library(silent=True)
            data = self.__library.get(_uuid)
            if data is None:
                logging.warning(
                    f"Entry not found in library, can't download thumbnail: {_uuid}"
                )
                return False
            name = data["name"]
            thumbnail = data.get("thumbnail")

        value = SteamGridDBManager.get_game_grid(name, config)

        if not value:
            return False

        with self.__lock:
            self.load_library(silent=True)
            current = self.__library.get(_uuid)
            if (
                current is None
                or current.get("name") != name
                or current.get("thumbnail") != thumbnail
            ):
                return False
            current["thumbnail"] = value
            self.save_library()
            return True

    def __already_in_library(self, data: dict):
        """
        Checks if the entry UUID is already in the library.yml file.
        """
        for k, v in self.__library.items():
            if v["id"] == data["id"]:
                return True

        return False

    @staticmethod
    def __remove_thumbnail(
        thumbnail: str, config: Optional[BottleConfig] = None
    ) -> None:
        managed_prefix = "umu-grid:" if config is None else "grid:"
        if not thumbnail.startswith(managed_prefix):
            return

        filename = thumbnail.removeprefix(managed_prefix)
        if os.path.basename(filename) != filename:
            return
        if config is None:
            path = Path(Paths.base) / "umu" / "covers" / filename
        else:
            path = Path(ManagerUtils.get_bottle_path(config)) / "grids" / filename
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    def remove_from_library(
        self, _uuid: str, config: Optional[BottleConfig] = None
    ):
        """
        Removes an entry from the library.yml file.
        """
        with self.__lock:
            self.load_library(silent=True)
            entry = self.__library.get(_uuid)
            if entry:
                logging.info(f"Removing entry from library: {_uuid}")
                thumbnail = entry.get("thumbnail")
                thumbnail_is_shared = any(
                    uuid != _uuid and item.get("thumbnail") == thumbnail
                    for uuid, item in self.__library.items()
                )
                del self.__library[_uuid]
                self.save_library()
                if thumbnail and not thumbnail_is_shared:
                    if entry.get("source") == "umu":
                        self.__remove_thumbnail(thumbnail)
                    elif config is not None:
                        self.__remove_thumbnail(thumbnail, config)
                return
            logging.warning(f"Entry not found in library, nothing to remove: {_uuid}")

    def remove_bottle_entries(self, bottle_name: str):
        with self.__lock:
            self.load_library(silent=True)
            entries = [
                entry_id
                for entry_id, entry in self.__library.items()
                if (entry.get("bottle") or {}).get("name") == bottle_name
            ]
            for entry_id in entries:
                del self.__library[entry_id]
            if entries:
                self.save_library()

    def remove_umu_game(self, game_id: str):
        with self.__lock:
            self.load_library(silent=True)
            library_id = f"umu:{game_id}"
            entries = [
                entry_id
                for entry_id, entry in self.__library.items()
                if entry.get("id") == library_id
            ]
            for entry_id in entries:
                del self.__library[entry_id]
            if entries:
                self.save_library()

    def save_library(self, silent=False):
        """
        Saves the library.yml file.
        """
        with self.__lock:
            with open(self.library_path, "w") as library_file:
                yaml.dump(self.__library, library_file)

            if not silent:
                logging.info("Library saved")

    def get_library(self):
        """
        Returns the library.yml file.
        """
        return self.__library
