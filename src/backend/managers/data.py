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

from bottles.backend.logger import Logger # pyright: reportMissingImports=false
from bottles.backend.globals import Paths
from bottles.backend.models.samples import Samples

logging = Logger()

class DataManager:
    '''
    The DataManager class is used to store and retrieve data
    from the user data.yml file. Should be stored only info
    and settings that should not be stored in gsettings.
    '''

    __data: dict = {}
    
    def __init__(self):
        self.__get_data()
    
    def __get_data(self):
        try:
            with open(Paths.data, 'r') as s:
                self.__data = yaml.safe_load(s)
        except FileNotFoundError:
            logging.error('Data file not found. Creating new one.')
            self.__create_data_file()
    
    def __create_data_file(self):
        if not os.path.exists(Paths.base):
            os.makedirs(Paths.base)
        with open(Paths.data, 'w') as s:
            yaml.dump(Samples.data, s)
        self.__get_data()
    
    def list(self):
        '''
        This function returns the whole data dictionary.
        '''
        return self.__data
    
    def set(self, key, value):
        '''
        This function sets a value in the data dictionary.
        '''
        if isinstance(self.__data[key], list):
            self.__data[key].append(value)
        else:
            self.__data[key] = value
        
        try:
            with open(Paths.data, 'w') as s:
                yaml.dump(self.__data, s)
        except FileNotFoundError:
            pass
    
    def get(self, key):
        '''
        This function returns the value of a key in the data dictionary.
        '''
        return self.__data[key]
