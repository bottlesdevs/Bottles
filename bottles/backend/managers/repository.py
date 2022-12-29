# repository.py
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

import pycurl
from bottles.frontend.params import APP_VERSION
from gi.repository import GLib

from bottles.backend.logger import Logger
from bottles.backend.repos.component import ComponentRepo
from bottles.backend.repos.dependency import DependencyRepo
from bottles.backend.repos.installer import InstallerRepo
from bottles.frontend.utils.threading import RunAsync

logging = Logger()


class RepositoryManager:
    __repositories = {
        "components": {
            "url": "https://proxy.usebottles.com/repo/components/",
            "index": "",
            "cls": ComponentRepo
        },
        "dependencies": {
            "url": "https://proxy.usebottles.com/repo/dependencies/",
            "index": "",
            "cls": DependencyRepo
        },
        "installers": {
            "url": "https://proxy.usebottles.com/repo/programs/",
            "index": "",
            "cls": InstallerRepo
        }
    }

    def __init__(self, repo_fn_update=None):
        self.repo_fn_update = repo_fn_update
        self.__check_locals()
        self.__get_index()

    def get_repo(self, name: str, offline: bool = False, callback=None):
        if name in self.__repositories:
            repo = self.__repositories[name]
            return repo["cls"](repo["url"], repo["index"], offline=offline, callback=callback)

        logging.error(f"Repository {name} not found")

    def __check_locals(self):
        _locals = {}

        if "LOCAL_COMPONENTS" in os.environ:
            _locals["components"] = os.environ["LOCAL_COMPONENTS"]

        if "LOCAL_DEPENDENCIES" in os.environ:
            _locals["dependencies"] = os.environ["LOCAL_DEPENDENCIES"]

        if "LOCAL_INSTALLERS" in os.environ:
            _locals["installers"] = os.environ["LOCAL_INSTALLERS"]

        if not _locals:
            return

        for repo in self.__repositories:
            if repo not in _locals:
                continue

            _path = _locals[repo]

            if os.path.exists(_path):
                self.__repositories[repo]["url"] = f"file://{_path}/"
                logging.info(f"Using local {repo} repository at {_path}")
            else:
                logging.error(f"Local {repo} path does not exist: {_path}")

    def __get_index(self):
        total = len(self.__repositories)

        threads = []

        for repo, data in self.__repositories.items():
            def query(repo, data):
                __index = os.path.join(data["url"], f"{APP_VERSION}.yml")
                __fallback = os.path.join(data["url"], "index.yml")

                for url in (__index, __fallback):
                    c = pycurl.Curl()
                    c.setopt(c.URL, url)
                    c.setopt(c.NOBODY, True)
                    c.setopt(c.FOLLOWLOCATION, True)
                    c.setopt(c.TIMEOUT, 10)

                    try:
                        c.perform()
                    except pycurl.error as e:
                        if url is not __index:
                            logging.error(f"Could not get index for {repo} repository: {e}")
                        continue

                    if url.startswith("file://") or c.getinfo(c.RESPONSE_CODE) == 200:
                        data["index"] = url
                        if self.repo_fn_update is not None:
                            GLib.idle_add(self.repo_fn_update, total)
                        break

                    c.close()
                else:
                    logging.error(f"Could not get index for {repo} repository")

            thread = RunAsync(query, repo=repo, data=data)
            threads.append(thread)

        for t in threads:
            t.join()
