import os
import yaml
import shutil
import platform
import subprocess

from .display import DisplayUtils
from .gpu import GPUUtils


class HealthChecker:

    x11: bool = False
    x11_port: str = ""
    wayland: bool = False
    xwayland: bool = False
    gpus: dict = {}
    cabextract: bool = False
    p7zip: bool = False
    patool: bool = False
    kernel: str = ""
    kernel_version: str = ""
    distro: str = ""
    distro_version: str = ""
    bottles_envs: dict = {}

    def __init__(self):
        self.x11 = self.check_x11()
        self.wayland = self.check_wayland()
        self.xwayland = self.check_xwayland()
        self.gpus = self.check_gpus()
        self.cabextract = self.check_cabextract()
        self.p7zip = self.check_p7zip()
        self.patool = self.check_patool()
        self.bottles_envs = self.get_bottles_envs()
        self.check_system_info()
    
    def check_gpus(self):
        return GPUUtils().get_gpu()

    def check_x11(self):
        port = DisplayUtils.get_x_display()
        if port:
            self.x11_port = port
            return True
        return False

    def check_wayland(self):
        if "WAYLAND_DISPLAY" in os.environ:
            return True
        return False

    def check_xwayland(self):
        if self.x11 and self.wayland:
            return True
        return False

    def check_cabextract(self):
        res = shutil.which("cabextract")
        if res is None:
            return False
        return True

    def check_p7zip(self):
        res = shutil.which("7z")
        if res is None:
            return False
        return True

    def check_patool(self):
        res = shutil.which("patool")
        if res is None:
            return False
        return True
    
    def __get_distro(self):
        try: # only Python 3.10+
            _platform = platform.freedesktop_os_release()
            return {
                "name": _platform.get("NAME", "Unknown"),
                "version": _platform.get("VERSION_ID", "Unknown")
            }
        except AttributeError:
            pass

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
    
    def get_bottles_envs(self):
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

    def get_results(self, plain:bool = False):
        results = {
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
            "Tools": {
                "cabextract": self.cabextract,
                "p7zip": self.p7zip,
                "patool": self.patool
            },
            "Bottles_envs": self.bottles_envs
        }
        
        if plain:
            _yaml = yaml.dump(results, sort_keys=False, indent=4)
            _yaml = _yaml.replace("&id", "&amp;id")
            return _yaml
        
        return results
