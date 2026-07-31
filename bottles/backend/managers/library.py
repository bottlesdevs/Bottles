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

import os
import shutil
import uuid

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

    def __init__(self):
        self.load_library(silent=True)

    def load_library(self, silent=False):
        """
        Loads data from the library.yml file.
        """
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

    def add_to_library(self, data: dict, config: BottleConfig):
        """
        Adds a new entry to the library.yml file.
        """
        if self.__already_in_library(data):
            logging.warning(f"Entry already in library, nothing to add: {data}")
            return

        _uuid = str(uuid.uuid4())
        logging.info(f"Adding new entry to library: {_uuid}")

        if not data.get("thumbnail"):
            for cover in self.__get_local_covers(data, config):
                data["thumbnail"] = self.import_thumbnail(cover, config)
                if data["thumbnail"]:
                    break

        if not data.get("thumbnail"):
            try:
                data["thumbnail"] = SteamGridDBManager.get_game_grid(
                    data["name"], config
                )
            except Exception as e:
                logging.warning(f"Could not fetch thumbnail: {e}")

        self.__library[_uuid] = data
        self.save_library()

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
    def import_thumbnail(source_path, config: BottleConfig):
        source_path = os.fspath(source_path)
        if not os.path.isfile(source_path):
            return None

        image_format, width, height = GdkPixbuf.Pixbuf.get_file_info(source_path)
        if image_format is None or width <= 0 or height <= 0:
            logging.warning(f"Invalid library thumbnail: {source_path}")
            return None

        extension = os.path.splitext(source_path)[1].lower()
        grids_path = os.path.join(ManagerUtils.get_bottle_path(config), "grids")
        filename = f"{uuid.uuid4()}{extension}"
        destination = os.path.join(grids_path, filename)

        try:
            os.makedirs(grids_path, exist_ok=True)
            shutil.copy2(source_path, destination)
        except OSError as error:
            logging.warning(f"Could not import library thumbnail: {error}")
            return None

        return f"grid:{filename}"

    def set_thumbnail(self, _uuid: str, source_path, config: BottleConfig):
        entry = self.__library.get(_uuid)
        if entry is None:
            logging.warning(f"Entry not found in library, can't set thumbnail: {_uuid}")
            return False

        thumbnail = self.import_thumbnail(source_path, config)
        if thumbnail is None:
            return False

        old_thumbnail = entry.get("thumbnail")
        entry["thumbnail"] = thumbnail
        self.save_library()

        thumbnail_is_shared = any(
            uuid != _uuid and item.get("thumbnail") == old_thumbnail
            for uuid, item in self.__library.items()
        )
        if (
            old_thumbnail
            and old_thumbnail.startswith("grid:")
            and not thumbnail_is_shared
        ):
            old_filename = old_thumbnail.removeprefix("grid:")
            if os.path.basename(old_filename) == old_filename:
                old_path = os.path.join(
                    ManagerUtils.get_bottle_path(config), "grids", old_filename
                )
                try:
                    os.remove(old_path)
                except FileNotFoundError:
                    pass

        return True

    def download_thumbnail(self, _uuid: str, config: BottleConfig):
        if not self.__library.get(_uuid):
            logging.warning(
                f"Entry not found in library, can't download thumbnail: {_uuid}"
            )
            return False

        data = self.__library.get(_uuid)
        value = SteamGridDBManager.get_game_grid(data["name"], config)

        if not value:
            return False

        self.__library[_uuid]["thumbnail"] = value
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

    def remove_from_library(self, _uuid: str):
        """
        Removes an entry from the library.yml file.
        """
        if self.__library.get(_uuid):
            logging.info(f"Removing entry from library: {_uuid}")
            del self.__library[_uuid]
            self.save_library()
            return
        logging.warning(f"Entry not found in library, nothing to remove: {_uuid}")

    def save_library(self, silent=False):
        """
        Saves the library.yml file.
        """
        with open(self.library_path, "w") as library_file:
            yaml.dump(self.__library, library_file)

        if not silent:
            logging.info("Library saved")

    def get_library(self):
        """
        Returns the library.yml file.
        """
        return self.__library
