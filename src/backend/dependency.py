# dependency.py
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


import yaml
import urllib.request
from typing import Union, NewType
from datetime import datetime
from gi.repository import Gtk, GLib

from .runner import Runner
from .globals import BottlesRepositories, Paths
from ..utils import RunAsync, UtilsLogger

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)

class DependencyManager:

    def __init__(self, manager):
        self.__manager = manager
        self.__utils_conn = manager.utils_conn

    def get_dependency(
        self, 
        dependency_name: str, 
        dependency_category: str, 
        plain: bool = False
    ) -> Union[str, dict, bool]:
        '''
        This function can be used to fetch the manifest for a given
        dependency. It can be returned as plain text or as a dictionary.
        It will return False if the dependency is not found.
        '''
        if self.__utils_conn.check_connection():
            try:
                with urllib.request.urlopen("%s/%s/%s.yml" % (
                    BottlesRepositories.dependencies,
                    dependency_category,
                    dependency_name
                )) as url:
                    if plain:
                        '''
                        Caller required the component manifest
                        as plain text.
                        '''
                        return url.read().decode("utf-8")

                    # return as dictionary
                    return yaml.safe_load(url.read())
            except:
                logging.error(f"Cannot fetch manifest for {dependency_name}.")
                return False

        return False
    def fetch_catalog(self) -> list:
        '''
        This function fetch all dependencies from the Bottles repository
        and return these as a dictionary. It also returns an empty dictionary
        if there are no dependencies or fails to fetch them.
        '''
        catalog = {}
        if not self.__utils_conn.check_connection():
            return {}

        try:
            with urllib.request.urlopen(
                BottlesRepositories.dependencies_index
            ) as url:
                index = yaml.safe_load(url.read())
        except:
            logging.error(F"Cannot fetch dependencies list.")
            return {}

        for dependency in index.items():
            catalog[dependency[0]] = dependency[1]
        return catalog

    def install(self, bottle: BottleConfig) -> list:
        return
