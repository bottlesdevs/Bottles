# data.py
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

import contextlib
import os

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.models.samples import Samples
from bottles.backend.utils import yaml

logging = Logger()


class UserDataKeys:
    CustomBottlesPath = "custom_bottles_path"


class DataManager:
    """
    The DataManager class is used to store and retrieve data
    from the user data.yml file. Should be stored only info
    and settings that should not be stored in gsettings.
    """

    __data: dict = {}
    __p_data = f"{Paths.base}/data.yml"

    def __init__(self):
        self.__get_data()

    def __get_data(self):
        try:
            with open(self.__p_data, 'r') as s:
                self.__data = yaml.load(s)
                if self.__data is None:
                    raise AttributeError
        except FileNotFoundError:
            logging.error('Data file not found. Creating new one.', )
            self.__create_data_file()
        except AttributeError:
            logging.error('Data file is empty. Creating new one.', )
            self.__create_data_file()

    def __create_data_file(self):
        if not os.path.exists(Paths.base):
            os.makedirs(Paths.base)
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

        with contextlib.suppress(FileNotFoundError):
            with open(self.__p_data, 'w') as s:
                yaml.dump(self.__data, s)

    def remove(self, key):
        """Removes a key from the data dictionary."""
        if self.__data.get(key):
            del self.__data[key]
            with contextlib.suppress(FileNotFoundError):
                with open(self.__p_data, 'w') as s:
                    yaml.dump(self.__data, s)

    def get(self, key):
        """Returns the value of a key in the data dictionary."""
        return self.__data.get(key)
