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

from bottles.backend.logger import Logger
from bottles.backend.models.result import Result
from bottles.backend.params import APP_VERSION
from bottles.backend.repos.component import ComponentRepo
from bottles.backend.repos.dependency import DependencyRepo
from bottles.backend.repos.installer import InstallerRepo
from bottles.backend.state import SignalManager, Signals
from bottles.backend.utils.threading import RunAsync

logging = Logger()


class RepositoryManager:
    __repositories = {
        "components": {
            "url": "https://proxy.usebottles.com/repo/components/",
            "index": "",
            "cls": ComponentRepo,
        },
        "dependencies": {
            "url": "https://proxy.usebottles.com/repo/dependencies/",
            "index": "",
            "cls": DependencyRepo,
        },
        "installers": {
            "url": "https://proxy.usebottles.com/repo/programs/",
            "index": "",
            "cls": InstallerRepo,
        },
    }

    def __init__(self, get_index=True):
        self.do_get_index = True
        self.aborted_connections = 0
        SignalManager.connect(Signals.ForceStopNetworking, self.__stop_index)

        self.__check_personals()
        if get_index:
            self.__get_index()

    def get_repo(self, name: str, offline: bool = False):
        if name in self.__repositories:
            repo = self.__repositories[name]
            return repo["cls"](repo["url"], repo["index"], offline=offline)

        logging.error(f"Repository {name} not found")

    def __check_personals(self):
        _personals = {}

        if "PERSONAL_COMPONENTS" in os.environ:
            _personals["components"] = os.environ["PERSONAL_COMPONENTS"]

        if "PERSONAL_DEPENDENCIES" in os.environ:
            _personals["dependencies"] = os.environ["PERSONAL_DEPENDENCIES"]

        if "PERSONAL_INSTALLERS" in os.environ:
            _personals["installers"] = os.environ["PERSONAL_INSTALLERS"]

        if not _personals:
            return

        for repo in self.__repositories:
            if repo not in _personals:
                continue

            _url = _personals[repo]
            self.__repositories[repo]["url"] = _url
            logging.info(f"Using personal {repo} repository at {_url}")

    def __curl_progress(self, _download_t, _download_d, _upload_t, _upload_d):
        if self.do_get_index:
            return pycurl.E_OK
        else:
            self.aborted_connections += 1
            return pycurl.E_ABORTED_BY_CALLBACK

    def __stop_index(self, res: Result):
        if res.status:
            self.do_get_index = False

    def __get_index(self):
        total = len(self.__repositories)

        threads = []

        for repo, data in self.__repositories.items():

            def query(_repo, _data):
                __index = os.path.join(_data["url"], f"{APP_VERSION}.yml")
                __fallback = os.path.join(_data["url"], "index.yml")

                for url in (__index, __fallback):
                    c = pycurl.Curl()
                    c.setopt(c.URL, url)
                    c.setopt(c.NOBODY, True)
                    c.setopt(c.FOLLOWLOCATION, True)
                    c.setopt(c.TIMEOUT, 10)
                    c.setopt(c.NOPROGRESS, False)
                    c.setopt(c.XFERINFOFUNCTION, self.__curl_progress)

                    try:
                        c.perform()
                    except pycurl.error as e:
                        if url is not __index:
                            logging.error(
                                f"Could not get index for {_repo} repository: {e}"
                            )
                        continue

                    if url.startswith("file://") or c.getinfo(c.RESPONSE_CODE) == 200:
                        _data["index"] = url
                        SignalManager.send(
                            Signals.RepositoryFetched, Result(True, data=total)
                        )
                        break

                    c.close()
                else:
                    SignalManager.send(
                        Signals.RepositoryFetched, Result(False, data=total)
                    )
                    logging.error(f"Could not get index for {_repo} repository")

            thread = RunAsync(query, _repo=repo, _data=data)
            threads.append(thread)

        for t in threads:
            t.join()

        self.do_get_index = True
