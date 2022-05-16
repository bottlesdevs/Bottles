# repo.py
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

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false

logging = Logger()


class Repo:
    name: str = ""

    def __init__(self, url: str, index: str):
        self.url = url
        self.catalog = self.__get_catalog(index)

    def __get_catalog(self, index: str):
        if index in ["", None]:
            return {}

        try:
            with urllib.request.urlopen(index) as url:
                index = yaml.safe_load(url.read())
                logging.info(f"Catalog {self.name} loaded")
        except (urllib.error.HTTPError, urllib.error.URLError, yaml.YAMLError):
            logging.error(f"Cannot fetch {self.name} repository index.", )
            return {}

        return index

    def get_manifest(self, url: str, plain: bool = False) -> dict:
        try:
            with urllib.request.urlopen(url) as u:
                res = u.read()
                if plain:
                    return res.decode("utf-8")
                return yaml.safe_load(res)
        except (urllib.error.HTTPError, urllib.error.URLError, yaml.YAMLError):
            logging.error(f"Cannot fetch {self.name} manifest.", )
            return False
