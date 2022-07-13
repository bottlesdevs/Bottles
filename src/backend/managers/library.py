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

import os
import uuid
import yaml
from pathlib import Path

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.globals import Paths

logging = Logger()


class LibraryManager:
    """
    The LibraryManager class is used to store and retrieve data
    from the user library.yml file.
    """

    library_path: str = Paths.library
    __library: dict = {}

    def __init__(self):
        self.load_library()

    def load_library(self):
        """
        Loads data from the library.yml file.
        """
        if not os.path.exists(self.library_path):
            logging.warning('Library file not found, creating new one')
            self.__library = {}
            self.save_library()
        else:
            with open(self.library_path, 'r') as library_file:
                self.__library = yaml.safe_load(library_file)

        if self.__library is None:
            self.__library = {}

        _tmp = self.__library.copy()
        for k, v in _tmp.items():
            if "id" not in v:
                del self.__library[k]

        self.save_library()

    def add_to_library(self, data: dict):
        """
        Adds a new entry to the library.yml file.
        """
        _uuid = str(uuid.uuid4())
        logging.info(f'Adding new entry to library: {_uuid}')

        self.__library[_uuid] = data
        self.save_library()

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

    def save_library(self):
        """
        Saves the library.yml file.
        """
        with open(self.library_path, 'w') as library_file:
            yaml.dump(self.__library, library_file)
        logging.info(f'Library saved')

    def get_library(self):
        """
        Returns the library.yml file.
        """
        return self.__library
