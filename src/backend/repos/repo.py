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

from bottles.backend.utils import yaml
import urllib.request
from http.client import RemoteDisconnected

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false

logging = Logger()


class Repo:
    name: str = ""

    def __init__(self, url: str, index: str, offline: bool = False):
        self.url = url
        self.catalog = self.__get_catalog(index, offline)

    def __get_catalog(self, index: str, offline: bool = False):
        if index in ["", None] or offline:
            return {}

        try:
            with urllib.request.urlopen(index) as url:
                index = yaml.load(url.read())
                logging.info(f"Catalog {self.name} loaded")
                return index
        except (urllib.error.HTTPError, urllib.error.URLError, yaml.YAMLError):
            logging.error(f"Cannot fetch {self.name} repository index.")
            return {}

    def get_manifest(self, url: str, plain: bool = False):
        try:
            with urllib.request.urlopen(url) as u:
                res = u.read()
                if plain:
                    return res.decode("utf-8")
                return yaml.load(res)
        except (urllib.error.HTTPError, urllib.error.URLError, RemoteDisconnected, yaml.YAMLError):
            logging.error(f"Cannot fetch {self.name} manifest.")
            return
