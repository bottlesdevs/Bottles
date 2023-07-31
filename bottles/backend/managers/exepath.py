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

from bottles.backend.utils import json

from bottles.backend.logger import Logger
from bottles.backend.globals import Paths

logging = Logger()


class ExePathManager:
    """
    The ExePathManager class is used to read and write the mapping
    between real and mangled paths from the user exe_paths.json file.
    """

    json_path: str = Paths.exe_paths
    __paths: dict = {}

    def __init__(self):
        self.load_paths(silent=True)

    def load_paths(self, silent=False):
        """
        Loads data from the exe_paths file.
        """
        if not os.path.exists(self.json_path):
            logging.warning('exe_paths file not found, creating new one')
            self.__paths = {}
            self.save_paths()
        else:
            with open(self.json_path, 'r') as paths_file:
                self.__paths = json.load(paths_file)

        if self.__paths is None:
            self.__paths = {}

        self.save_paths(silent=silent)

    def add_path(self, real_path: str, mangled_path: str):
        """
        Adds a new entry to the exe_paths.json file.
        """
        if self.__already_exists(real_path):
            logging.warning(f'Exe path already exists, nothing to add: {real_path}, {mangled_path}')
            return
        
        logging.info(f'Adding new entry to exe paths: {real_path}')

        self.__paths[real_path] = mangled_path
        self.save_paths()

    def __already_exists(self, real_path: str):
        """
        Checks if the real path is already in the exe_paths.json file.
        """
        for k, _ in self.__paths.items():
            if k == real_path:
                return True

        return False

    def remove_path(self, _real_path: str):
        """
        Removes an entry from the exe_paths.json file.
        """
        if self.__paths.get(_real_path):
            logging.info(f'Removing entry from exe paths: {_real_path}')
            del self.__paths[_real_path]
            self.save_paths()
            return
        logging.warning(f'Entry not found in exe paths, nothing to remove: {_real_path}')

    def save_paths(self, silent=False):
        """
        Saves the exe_paths.json file.
        """
        with open(self.json_path, 'w') as json_file:
            json.dump(self.__paths, json_file)
            
        if not silent:
            logging.info(f'Exe paths saved')

    def get_mangled_path(self, real_path: str):
        return self.__paths.get(real_path)

    def get_paths(self):
        """
        Returns the exe_paths.json file.
        """
        return self.__paths
