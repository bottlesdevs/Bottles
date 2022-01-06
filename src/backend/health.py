import os
import yaml
import shutil

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

    def __init__(self):
        self.x11 = self.check_x11()
        self.wayland = self.check_wayland()
        self.xwayland = self.check_xwayland()
        self.gpus = self.check_gpus()
        self.cabextract = self.check_cabextract()
        self.p7zip = self.check_p7zip()
        self.patool = self.check_patool()
    
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

    def get_results(self, plain:bool = False):
        results = {
            "x11": self.x11,
            "x11_port": self.x11_port,
            "wayland": self.wayland,
            "gpus": self.gpus,
            "cabextract": self.cabextract,
            "p7zip": self.p7zip,
            "patool": self.patool
        }
        
        if plain:
            _yaml = yaml.dump(results)
            return _yaml
        
        return results
