# component.py
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

import time
import requests
from gi.repository import GLib

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.utils.file import FileUtils

logging = Logger()


class Downloader:
    """
    Download a resource from a given URL. It shows and update a progress
    bar while downloading but can also be used to update external progress
    bars using the func parameter.
    """

    def __init__(self, url: str, file: str, func: callable = None, task_id: int = None):
        self.start_time = None
        self.url = url
        self.file = file
        self.func = func
        self.task_id = task_id

    def download(self):
        """Start the download."""
        try:
            with open(self.file, "wb") as file:
                self.start_time = time.time()
                headers = {"User-Agent": "curl/7.79.1"}
                response = requests.get(self.url, stream=True, headers=headers)
                total_size = int(response.headers.get("content-length", 0))
                block_size = 1024
                count = 0

                if total_size != 0:
                    for data in response.iter_content(block_size):
                        file.write(data)
                        count += 1
                        if self.func is not None:
                            if self.task_id:
                                GLib.idle_add(
                                    self.func,
                                    self.task_id,
                                    count,
                                    block_size,
                                    total_size
                                )
                            else:
                                GLib.idle_add(
                                    self.func,
                                    count,
                                    block_size,
                                    total_size
                                )
                            self.__progress(count, block_size, total_size)
                else:
                    file.write(response.content)
                    if self.func is not None:
                        GLib.idle_add(self.func, 1, 1, 1)
                        self.__progress(1, 1, 1)
        except requests.exceptions.SSLError:
            logging.error("Download failed due to a SSL error. Your system may have a wrong date/time or wrong certificates.")
            return False
        except (requests.exceptions.RequestException, OSError):
            logging.error("Download failed! Check your internet connection.")
            return False

        return True

    def __progress(self, count, block_size, total_size):
        """Update the progress bar."""
        percent = int(count * block_size * 100 / total_size)
        done_str = FileUtils.get_human_size(count * block_size)
        total_str = FileUtils.get_human_size(total_size)
        speed_str = FileUtils.get_human_size(count * block_size / (time.time() - self.start_time))
        name = self.file.split("/")[-1]
        c_close, c_complete, c_incomplete = "\033[0m", "\033[92m", "\033[90m"
        print(
            f"\r{c_incomplete if percent < 100 else c_complete}{name} ({percent}%) \
{'━' * int(percent / 2)} ({done_str}/{total_str} - {speed_str})",
            end=""
        )
        if percent == 100:
            print(f"{c_close}\n")
