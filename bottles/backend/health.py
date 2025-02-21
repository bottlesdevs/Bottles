# health.py
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
from bottles.backend.utils import yaml
import contextlib

from bottles.backend.utils.display import DisplayUtils
from bottles.backend.utils.gpu import GPUUtils
from bottles.backend.utils.generic import is_glibc_min_available
from bottles.backend.utils.file import FileUtils
from bottles.backend.params import APP_VERSION


class HealthChecker:
    x11: bool = False
    x11_port: str = ""
    wayland: bool = False
    xwayland: bool = False
    desktop: str = ""
    gpus: dict = {}
    cabextract: bool = False
    p7zip: bool = False
    patool: bool = False
    icoextract: bool = False
    pefile: bool = False
    orjson: bool = False
    markdown: bool = False
    xdpyinfo: bool = False
    ImageMagick: bool = False
    FVS: bool = False
    glibc_min: str = ""
    kernel: str = ""
    kernel_version: str = ""
    bottles_envs: dict = {}

    def __init__(self):
        self.file_utils = FileUtils()
        self.x11 = self.check_x11()
        self.wayland = self.check_wayland()
        self.xwayland = self.x11 and self.wayland
        self.desktop = self.check_desktop()
        self.gpus = GPUUtils().get_gpu()
        self.glibc_min = is_glibc_min_available()
        self.bottles_envs = self.get_bottles_envs()
        self.check_system_info()
        self.disk = self.get_disk_data()
        self.ram = {"MemTotal": "n/a", "MemAvailable": "n/a"}
        self.get_ram_data()

    def check_x11(self):
        port = DisplayUtils.get_x_display()
        if port:
            self.x11_port = port
            return True
        return False

    @staticmethod
    def check_wayland():
        return "WAYLAND_DISPLAY" in os.environ or "WAYLAND_SOCKET" in os.environ

    def check_desktop(self):
        return os.environ.get("DESKTOP_SESSION")

    @staticmethod
    def get_bottles_envs():
        look = [
            "TESTING_REPOS",
            "LOCAL_INSTALLERS",
            "LOCAL_COMPONENTS",
            "LOCAL_DEPENDENCIES",
        ]

        for _look in look:
            if _look in os.environ:
                return {_look: os.environ[_look]}

    def check_system_info(self):
        self.kernel = os.uname().sysname
        self.kernel_version = os.uname().release

    def get_disk_data(self):
        disk_data = self.file_utils.get_disk_size(False)
        return {"Total": disk_data["total"], "Free": disk_data["free"]}

    def get_ram_data(self):
        with contextlib.suppress(FileNotFoundError, PermissionError):
            with open("/proc/meminfo") as file:
                for line in file:
                    if "MemTotal" in line:
                        self.ram["MemTotal"] = self.file_utils.get_human_size_legacy(
                            float(line.split()[1]) * 1024.0
                        )
                    if "MemAvailable" in line:
                        self.ram["MemAvailable"] = (
                            self.file_utils.get_human_size_legacy(
                                float(line.split()[1]) * 1024.0
                            )
                        )

    def get_results(self, plain: bool = False):
        results = {
            "Official Package": "FLATPAK_ID" in os.environ,
            "Version": APP_VERSION,
            "DE/WM": self.desktop,
            "Display": {
                "X.org": self.x11,
                "X.org (port)": self.x11_port,
                "Wayland": self.wayland,
            },
            "Graphics": self.gpus,
            "Kernel": {"Type": self.kernel, "Version": self.kernel_version},
            "Disk": self.disk,
            "RAM": self.ram,
            "Bottles_envs": self.bottles_envs,
        }

        if plain:
            _yaml = yaml.dump(results, sort_keys=False, indent=4)
            _yaml = _yaml.replace("&id", "&amp;id")
            return _yaml

        return results
