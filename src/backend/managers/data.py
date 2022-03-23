# data.py
#
# Copyright 2020 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import yaml
from pathlib import Path

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.models.samples import Samples

logging = Logger()


class DataManager:
    """
    The DataManager class is used to store and retrieve data
    from the user data.yml file. Should be stored only info
    and settings that should not be stored in gsettings.
    """

    __data: dict = {}
    __p_xdg_data_home = os.environ.get("XDG_DATA_HOME", f"{Path.home()}/.local/share")
    __p_base = f"{__p_xdg_data_home}/bottles"
    __p_data = f"{__p_base}/data.yml"

    def __init__(self):
        self.__get_data()

    def __get_data(self):
        try:
            with open(self.__p_data, 'r') as s:
                self.__data = yaml.safe_load(s)
        except FileNotFoundError:
            logging.error('Data file not found. Creating new one.', )
            self.__create_data_file()

    def __create_data_file(self):
        if not os.path.exists(self.__p_base):
            os.makedirs(self.__p_base)
        with open(self.__p_data, 'w') as s:
            yaml.dump(Samples.data, s)
        self.__get_data()

    def list(self):
        """Returns the whole data dictionary."""
        return self.__data

    def set(self, key, value, of_type=None):
        """Sets a value in the data dictionary."""
        if self.__data.get(key):
            if isinstance(self.__data[key], list):
                self.__data[key].append(value)
            else:
                self.__data[key] = value
        else:
            if of_type == list:
                self.__data[key] = [value]
            else:
                self.__data[key] = value

        try:
            with open(self.__p_data, 'w') as s:
                yaml.dump(self.__data, s)
        except FileNotFoundError:
            pass

    def remove(self, key):
        """Removes a key from the data dictionary."""
        if self.__data.get(key):
            del self.__data[key]
            try:
                with open(self.__p_data, 'w') as s:
                    yaml.dump(self.__data, s)
            except FileNotFoundError:
                pass

    def get(self, key):
        """Returns the value of a key in the data dictionary."""
        return self.__data.get(key)
