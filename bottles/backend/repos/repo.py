import os
from hashlib import sha256

# repo.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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

from io import BytesIO

import pycurl

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger
from bottles.backend.state import EventManager, Events
from bottles.backend.utils import yaml
from bottles.backend.utils.threading import RunAsync

logging = Logger()


class Repo:
    name: str = ""

    def __init__(
        self,
        url: str,
        index: str,
        offline: bool = False,
        callback_in_main_loop: bool = True,
        catalog_data: bytes | None = None,
        cache_url: str | None = None,
    ):
        self.url = url
        self.cache_url = cache_url or url
        self.offline = offline
        self.catalog = None

        if catalog_data is not None and not offline:
            self.catalog = self.__parse_catalog(catalog_data)
            EventManager.done(Events(self.name + ".fetching"))
            return

        def set_catalog(result, error=None):
            self.catalog = result
            EventManager.done(Events(self.name + ".fetching"))

        RunAsync(
            self.__get_catalog,
            callback=set_catalog,
            callback_in_main_loop=callback_in_main_loop,
            index=index,
            offline=offline,
        )

    def __get_catalog(self, index: str, offline: bool = False):
        cache_path = self.__get_cache_path("catalog.yml")
        if index in ["", None] or offline:
            return self.__read_cache(cache_path) or {}

        try:
            buffer = BytesIO()

            c = pycurl.Curl()
            try:
                _proxy = os.environ.get("http_proxy") or os.environ.get("https_proxy")

                if _proxy:
                    c.setopt(pycurl.PROXY, _proxy)
                c.setopt(c.URL, index)
                c.setopt(c.FOLLOWLOCATION, True)
                c.setopt(c.WRITEDATA, buffer)
                c.setopt(pycurl.CONNECTTIMEOUT, 10)
                c.setopt(pycurl.TIMEOUT, 30)
                c.perform()
            finally:
                c.close()

            return self.__parse_catalog(buffer.getvalue())
        except (pycurl.error, yaml.YAMLError):
            logging.error(f"Cannot fetch {self.name} repository index.")
            return self.__read_cache(cache_path) or {}

    def __parse_catalog(self, data: bytes) -> dict:
        cache_path = self.__get_cache_path("catalog.yml")
        try:
            index = yaml.load(data)
        except yaml.YAMLError:
            index = None
        if not isinstance(index, dict):
            logging.error(f"Invalid catalog returned by {self.name} repository.")
            return self.__read_cache(cache_path) or {}

        self.__write_cache(cache_path, data)
        logging.info(f"Catalog {self.name} loaded")
        return index

    def get_manifest(self, url: str, plain: bool = False) -> str | dict | bool:
        cache_url = url
        canonical_url = getattr(self, "cache_url", self.url)
        if url.startswith(self.url):
            cache_url = canonical_url + url[len(self.url) :]
        cache_name = sha256(cache_url.encode("utf-8")).hexdigest() + ".yml"
        cache_path = self.__get_cache_path(cache_name)
        if self.offline:
            return self.__read_cache(cache_path, plain=plain) or False

        try:
            buffer = BytesIO()

            c = pycurl.Curl()
            try:
                _proxy = os.environ.get("http_proxy") or os.environ.get("https_proxy")

                if _proxy:
                    c.setopt(pycurl.PROXY, _proxy)
                c.setopt(c.URL, url)
                c.setopt(c.FOLLOWLOCATION, True)
                c.setopt(c.WRITEDATA, buffer)
                c.setopt(pycurl.CONNECTTIMEOUT, 10)
                c.setopt(pycurl.TIMEOUT, 30)
                c.perform()
            finally:
                c.close()

            res = buffer.getvalue()
            manifest = yaml.load(res)
            if not isinstance(manifest, dict):
                logging.error(f"Invalid manifest returned by {self.name} repository.")
                return self.__read_cache(cache_path, plain=plain) or False

            self.__write_cache(cache_path, res)
            if plain:
                return res.decode("utf-8")
            return manifest
        except (OSError, UnicodeDecodeError, pycurl.error, yaml.YAMLError):
            logging.error(f"Cannot fetch {self.name} manifest.")
            return self.__read_cache(cache_path, plain=plain) or False

    def __get_cache_path(self, name: str) -> str:
        cache_url = getattr(self, "cache_url", self.url)
        repo_id = sha256(cache_url.encode("utf-8")).hexdigest()[:16]
        return os.path.join(Paths.temp, "repositories", self.name, repo_id, name)

    @staticmethod
    def __read_cache(path: str, plain: bool = False) -> str | dict | bool:
        try:
            with open(path, "rb") as cache:
                data = cache.read()
            parsed = yaml.load(data)
            if not isinstance(parsed, dict):
                return False
            if plain:
                return data.decode("utf-8")
            return parsed
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            return False

    @staticmethod
    def __write_cache(path: str, data: bytes) -> None:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            temp_path = f"{path}.tmp"
            with open(temp_path, "wb") as cache:
                cache.write(data)
            os.replace(temp_path, path)
        except OSError:
            logging.warning(f"Cannot cache repository data at {path}.")
