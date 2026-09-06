# repository.py
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

import os
from io import BytesIO

import pycurl

from bottles.backend.logger import Logger
from bottles.backend.managers.data import DataManager, UserDataKeys
from bottles.backend.models.result import Result
from bottles.backend.params import APP_VERSION
from bottles.backend.repos.component import ComponentRepo
from bottles.backend.repos.dependency import DependencyRepo
from bottles.backend.repos.installer import InstallerRepo
from bottles.backend.state import SignalManager, Signals
from bottles.backend.utils import yaml
from bottles.backend.utils.threading import RunAsync

logging = Logger()


class RepositoryManager:
    __repositories = {
        "components": {
            "sources": (
                "https://proxy.usebottles.com/repo/components/",
                "https://raw.githubusercontent.com/bottlesdevs/components/f63f670e12f015003b3f751cd53777377d9ec725/",
            ),
            "index": "",
            "cls": ComponentRepo,
        },
        "dependencies": {
            "sources": (
                "https://proxy.usebottles.com/repo/dependencies/",
                "https://raw.githubusercontent.com/bottlesdevs/dependencies/2c0c19707c252d9ec49f1bf26ac4793fd041332b/",
            ),
            "index": "",
            "cls": DependencyRepo,
        },
        "installers": {
            "sources": (
                "https://proxy.usebottles.com/repo/programs/",
                "https://raw.githubusercontent.com/bottlesdevs/programs/d1160b816ca44a1cc803ab9a0050071517cc1960/",
            ),
            "index": "",
            "cls": InstallerRepo,
        },
    }

    def __init__(self, get_index=True):
        self.do_get_index = True
        self.aborted_connections = 0
        SignalManager.connect(Signals.ForceStopNetworking, self.__stop_index)
        self.data = DataManager()
        self.__repositories = {
            name: {
                **repository,
                "sources": list(repository["sources"]),
                "url": repository["sources"][0],
                "cache_url": repository["sources"][0],
                "index": "",
                "catalog": None,
            }
            for name, repository in self.__repositories.items()
        }

        self.__check_personals()
        if get_index:
            self.__get_index()

    def get_repo(
        self,
        name: str,
        offline: bool = False,
        callback_in_main_loop: bool = True,
    ):
        if name in self.__repositories:
            repo = self.__repositories[name]
            return repo["cls"](
                repo["url"],
                repo["index"],
                offline=offline,
                callback_in_main_loop=callback_in_main_loop,
                catalog_data=None if offline else repo["catalog"],
                cache_url=repo["cache_url"],
            )

        logging.error(f"Repository {name} not found")

    def __check_personals(self):
        _personals = {}

        stored_personals = self.data.get(UserDataKeys.PersonalRepositories) or {}
        for repo_name in ("components", "dependencies", "installers"):
            url = stored_personals.get(repo_name)
            if url:
                _personals[repo_name] = url

        env_personals = {
            "components": "PERSONAL_COMPONENTS",
            "dependencies": "PERSONAL_DEPENDENCIES",
            "installers": "PERSONAL_INSTALLERS",
        }

        for repo_name, env_var in env_personals.items():
            if env_var in os.environ and os.environ[env_var]:
                _personals[repo_name] = os.environ[env_var]

        if not _personals:
            return

        for repo in self.__repositories:
            if repo not in _personals:
                continue

            _url = _personals[repo]
            self.__repositories[repo]["sources"] = [_url]
            self.__repositories[repo]["url"] = _url
            self.__repositories[repo]["cache_url"] = _url
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

    @staticmethod
    def __perform_index_request(c, buffer):
        try:
            c.perform()
        except pycurl.error as error:
            if error.args[0] not in (
                pycurl.E_COULDNT_RESOLVE_HOST,
                pycurl.E_COULDNT_CONNECT,
                pycurl.E_OPERATION_TIMEDOUT,
            ):
                raise

            buffer.seek(0)
            buffer.truncate()
            c.setopt(pycurl.IPRESOLVE, pycurl.IPRESOLVE_V4)
            c.perform()

    def __get_index(self):
        total = len(self.__repositories)

        threads = []

        for repo, data in self.__repositories.items():

            def query(_repo, _data):
                for source in _data["sources"]:
                    for filename in (f"{APP_VERSION}.yml", "index.yml"):
                        if not self.do_get_index:
                            break

                        url = os.path.join(source, filename)
                        buffer = BytesIO()
                        c = pycurl.Curl()
                        try:
                            _proxy = os.environ.get("http_proxy") or os.environ.get(
                                "https_proxy"
                            )
                            if _proxy:
                                c.setopt(pycurl.PROXY, _proxy)
                            c.setopt(c.URL, url)
                            c.setopt(c.FOLLOWLOCATION, True)
                            c.setopt(c.WRITEDATA, buffer)
                            c.setopt(c.CONNECTTIMEOUT, 5)
                            c.setopt(c.TIMEOUT, 10)
                            c.setopt(c.NOPROGRESS, False)
                            c.setopt(c.XFERINFOFUNCTION, self.__curl_progress)
                            c.setopt(pycurl.USERAGENT,f"Bottles/{APP_VERSION}")
                            self.__perform_index_request(c, buffer)
                            response_code = c.getinfo(c.RESPONSE_CODE)
                        except pycurl.error as e:
                            logging.error(
                                f"Could not get index for {_repo} repository: {e}"
                            )
                            if url.startswith("file://"):
                                continue
                            break
                        finally:
                            c.close()

                        if url.startswith("file://") or response_code == 200:
                            catalog = buffer.getvalue()
                            try:
                                parsed_catalog = yaml.load(catalog)
                            except yaml.YAMLError:
                                parsed_catalog = None
                            if not isinstance(parsed_catalog, dict):
                                logging.error(
                                    f"Invalid index for {_repo} repository at {url}"
                                )
                                break

                            _data["url"] = source
                            _data["index"] = url
                            _data["catalog"] = catalog
                            SignalManager.send(
                                Signals.RepositoryFetched, Result(True, data=total)
                            )
                            return

                        if response_code != 404:
                            logging.error(
                                f"Could not get index for {_repo} repository: "
                                f"HTTP {response_code}"
                            )
                            break

                    if not self.do_get_index:
                        break

                SignalManager.send(Signals.RepositoryFetched, Result(False, data=total))
                logging.error(f"Could not get index for {_repo} repository")

            thread = RunAsync(query, _repo=repo, _data=data)
            threads.append(thread)

        for t in threads:
            t.join()

        self.do_get_index = True
