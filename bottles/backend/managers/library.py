# library.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
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
import uuid

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils import yaml

from bottles.backend.logger import Logger
from bottles.backend.globals import Paths
from bottles.backend.managers.steamgriddb import SteamGridDBManager

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
            logging.warning('Library file not found, creating new one')
            self.__library = {}
            self.save_library()
        else:
            with open(self.library_path, 'r') as library_file:
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
            logging.warning(f'Entry already in library, nothing to add: {data}')
            return

        _uuid = str(uuid.uuid4())
        logging.info(f'Adding new entry to library: {_uuid}')

        if not data.get("thumbnail"):
            data['thumbnail'] = SteamGridDBManager.get_game_grid(data['name'], config)

        self.__library[_uuid] = data
        self.save_library()

    def download_thumbnail(self, _uuid: str, config: BottleConfig):
        if not self.__library.get(_uuid):
            logging.warning(f'Entry not found in library, can\'t download thumbnail: {_uuid}')
            return False

        data = self.__library.get(_uuid)
        value = SteamGridDBManager.get_game_grid(data['name'], config)

        if not value:
            return False

        self.__library[_uuid]['thumbnail'] = value
        self.save_library()
        return True

    def __already_in_library(self, data: dict):
        """
        Checks if the entry UUID is already in the library.yml file.
        """
        for k, v in self.__library.items():
            if v['id'] == data['id']:
                return True

        return False

    def remove_from_library(self, _uuid: str):
        """
        Removes an entry from the library.yml file.
        """
        if self.__library.get(_uuid):
            logging.info(f'Removing entry from library: {_uuid}')
            del self.__library[_uuid]
            self.save_library()
            return
        logging.warning(f'Entry not found in library, nothing to remove: {_uuid}')

    def save_library(self, silent=False):
        """
        Saves the library.yml file.
        """
        with open(self.library_path, 'w') as library_file:
            yaml.dump(self.__library, library_file)
            
        if not silent:
            logging.info(f'Library saved')

    def get_library(self):
        """
        Returns the library.yml file.
        """
        return self.__library
