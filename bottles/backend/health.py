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
import shutil
import platform
import contextlib
import subprocess

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false
from bottles.backend.utils.display import DisplayUtils
from bottles.backend.utils.gpu import GPUUtils
from bottles.backend.utils.generic import is_glibc_min_available
from bottles.backend.utils.file import FileUtils
from bottles.frontend.params import VERSION

logging = Logger()


class HealthChecker:
    x11: bool = False
    x11_port: str = ""
    wayland: bool = False
    xwayland: bool = False
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
    distro: str = ""
    distro_version: str = ""
    bottles_envs: dict = {}

    def __init__(self):
        self.file_utils = FileUtils()
        self.x11 = self.check_x11()
        self.wayland = self.check_wayland()
        self.xwayland = self.check_xwayland()
        self.gpus = self.check_gpus()
        self.glibc_min = is_glibc_min_available()
        self.bottles_envs = self.get_bottles_envs()
        self.check_system_info()
        self.disk = self.get_disk_data()
        self.ram = {
            "MemTotal": "n/a",
            "MemAvailable": "n/a"
        }
        self.get_ram_data()
        if not "FLATPAK_ID" in os.environ:
            self.cabextract = self.check_cabextract()
            self.p7zip = self.check_p7zip()
            self.patool = self.check_patool()
            self.icoextract = self.check_icoextract()
            self.pefile = self.check_pefile()
            self.orjson = self.check_orjson()
            self.markdown = self.check_markdown()
            self.xdpyinfo = self.check_xdpyinfo()
            self.ImageMagick = self.check_ImageMagick()
            self.FVS = self.check_FVS()
        else:
            self.cabextract = True
            self.p7zip = True
            self.patool = True
            self.icoextract = True
            self.pefile = True
            self.orjson = True
            self.markdown = True
            self.ImageMagick = True
            self.FVS = True

    @staticmethod
    def check_gpus():
        return GPUUtils().get_gpu()

    def check_x11(self):
        port = DisplayUtils.get_x_display()
        if port:
            self.x11_port = port
            return True
        return False

    @staticmethod
    def check_wayland():
        if "WAYLAND_DISPLAY" in os.environ:
            return True
        return False

    def check_xwayland(self):
        if self.x11 and self.wayland:
            return True
        return False

    @staticmethod
    def check_cabextract():
        res = shutil.which("cabextract")
        if res is None:
            return False
        return True

    @staticmethod
    def check_p7zip():
        res = shutil.which("7z")
        if res is None:
            return False
        return True

    @staticmethod
    def check_patool():
        res = shutil.which("patool")
        if res is None:
            return False
        return True

    @staticmethod
    def check_icoextract():
        try:
            import icoextract
            return True
        except ModuleNotFoundError:
            return False

    @staticmethod
    def check_pefile():
        try:
            import pefile
            return True
        except ModuleNotFoundError:
            return False

    @staticmethod
    def check_markdown():
        try:
            import markdown
            return True
        except ModuleNotFoundError:
            return False

    @staticmethod
    def check_orjson():
        try:
            import orjson
            return True
        except ModuleNotFoundError:
            return False

    @staticmethod
    def check_xdpyinfo():
        res = shutil.which("xdpyinfo")
        if res is None:
            return False
        return True

    @staticmethod
    def check_ImageMagick():
        res = shutil.which("identify")
        if res is None:
            return False
        return True

    @staticmethod
    def check_FVS():
        try:
            from fvs.repo import FVSRepo
            return True
        except ModuleNotFoundError:
            return False

    @staticmethod
    def __get_distro():
        with contextlib.suppress(AttributeError):
            _platform = platform.freedesktop_os_release()
            return {
                "name": _platform.get("NAME", "Unknown"),
                "version": _platform.get("VERSION_ID", "Unknown")
            }

        if shutil.which("lsb_release"):
            _proc = subprocess.Popen(
                "lsb_release -a",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True
            ).communicate()[0].decode("utf-8").lower()
            _lines = _proc.split("\n")
            _name = _lines[0].split(":")[1].strip()
            _version = _lines[1].split(":")[1].strip()
            return {
                "name": _name,
                "version": _version
            }

        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r") as _file:
                _lines = _file.readlines()
                _name = _lines[0].split("=")[1].strip()
                _version = _lines[1].split("=")[1].strip()
                return {
                    "name": _name,
                    "version": _version
                }

        return {
            "name": "Unknown",
            "version": "Unknown"
        }

    @staticmethod
    def get_bottles_envs():
        look = [
            "LAYERS",
            "TESTING_REPOS",
            "LOCAL_INSTALLERS",
            "LOCAL_COMPONENTS",
            "LOCAL_DEPENDENCIES"
        ]

        for _look in look:
            if _look in os.environ:
                return {
                    _look: os.environ[_look]
                }

    def check_system_info(self):
        distro = self.__get_distro()
        self.kernel = os.uname().sysname
        self.kernel_version = os.uname().release
        self.distro = distro["name"]
        self.distro_version = distro["version"]

    def get_disk_data(self):
        disk_data = self.file_utils.get_disk_size(False)
        return {
            "Total": disk_data["total"],
            "Free": disk_data["free"]
        }

    def get_ram_data(self):
        with contextlib.suppress(FileNotFoundError, PermissionError):
            with open('/proc/meminfo') as file:
                for line in file:
                    if 'MemTotal' in line:
                        self.ram["MemTotal"] = self.file_utils.get_human_size(float(line.split()[1])*1024.0)
                    if 'MemAvailable' in line:
                        self.ram["MemAvailable"] = self.file_utils.get_human_size(float(line.split()[1])*1024.0)

    def get_results(self, plain: bool = False):
        results = {
            "Version": VERSION,
            "Display": {
                "X.org": self.x11,
                "X.org (port)": self.x11_port,
                "Wayland": self.wayland,
            },
            "Graphics": self.gpus,
            "Kernel": {
                "Type": self.kernel,
                "Version": self.kernel_version
            },
            "Distro": {
                "Name": self.distro,
                "Version": self.distro_version
            },
            "Disk": self.disk,
            "RAM": self.ram,
            "Bottles_envs": self.bottles_envs
        }

        if not "FLATPAK_ID" in os.environ:
            results["Tools and Libraries"] = {
                "cabextract": self.cabextract,
                "p7zip": self.p7zip,
                "patool": self.patool,
                "glibc_min": self.glibc_min,
                "icoextract": self.icoextract,
                "pefile": self.pefile,
                "orjson": self.orjson,
                "markdown": self.markdown,
                "ImageMagick": self.ImageMagick,
                "FVS": self.FVS,
                "xdpyinfo": self.xdpyinfo
            }

        if plain:
            _yaml = yaml.dump(results, sort_keys=False, indent=4)
            _yaml = _yaml.replace("&id", "&amp;id")
            return _yaml

        return results

    def has_core_deps(self):
        result = True

        for k, v in self.get_results()["Tools and Libraries"].items():
            if v is False:
                logging.error(f"Core dependency {k} not found, Bottles can't be started.")
                result = False

        return result
