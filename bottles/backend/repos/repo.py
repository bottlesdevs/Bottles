# repo.py
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

from bottles.backend.utils import yaml
import pycurl
from io import BytesIO
from threading import Lock as PyLock
from typing import Dict

from bottles.backend.logger import Logger

from bottles.backend.utils.threading import RunAsync

logging = Logger()


class Repo:
    name: str = ""

    def __init__(self, url: str, index: str, offline: bool = False, callback = None):
        self.url = url
        self.catalog = None

        def set_catalog(result, error=None):
            self.catalog = result
            RepoStatus.repo_done_operation(self.name + ".fetching")
            if callback: callback()
        RunAsync(self.__get_catalog, callback=set_catalog, index=index, offline=offline)

    def __get_catalog(self, index: str, offline: bool = False):
        RepoStatus.repo_start_operation(self.name + ".fetching")

        if index in ["", None] or offline:
            return {}

        try:
            buffer = BytesIO()

            c = pycurl.Curl()
            c.setopt(c.URL, index)
            c.setopt(c.FOLLOWLOCATION, True)
            c.setopt(c.WRITEDATA, buffer)
            c.perform()
            c.close()

            index = yaml.load(buffer.getvalue())
            logging.info(f"Catalog {self.name} loaded")

            return index
        except (pycurl.error, yaml.YAMLError):
            logging.error(f"Cannot fetch {self.name} repository index.")
            return {}

    def get_manifest(self, url: str, plain: bool = False):
        try:
            buffer = BytesIO()

            c = pycurl.Curl()
            c.setopt(c.URL, url)
            c.setopt(c.FOLLOWLOCATION, True)
            c.setopt(c.WRITEDATA, buffer)
            c.perform()
            c.close()
            
            res = buffer.getvalue()

            if plain:
                return res.decode("utf-8")

            return yaml.load(res)
        except (pycurl.error, yaml.YAMLError):
            logging.error(f"Cannot fetch {self.name} manifest.")
            return {}

class RepoStatus:
    LOCKS: Dict[str, PyLock] = {}

    @staticmethod
    def repo_start_operation(name: str):
        lock = RepoStatus.LOCKS.setdefault(name, PyLock())
        lock.acquire()
        logging.debug(f"Start operation {name}")

    @staticmethod
    def repo_done_operation(name: str):
        lock = RepoStatus.LOCKS.setdefault(name, PyLock())
        if lock.locked():
            lock.release()
        logging.debug(f"Done operation {name}")

    def repo_wait_operation(name: str):
        lock = RepoStatus.LOCKS.setdefault(name, PyLock())
        logging.debug(f"Wait operation {name}")
        lock.acquire()
        lock.release()
        logging.debug(f"Done wait operation {name}")