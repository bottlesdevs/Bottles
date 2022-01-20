import os
import shutil
from typing import NewType

from .runner import Runner
from .manager_utils import ManagerUtils

BottleConfig = NewType('BottleConfig', dict)


class DLLComponent():
    base_path:str = None
    dlls:dict = {}
    version:str = None

    def __init__(self, version:str):
        self.version = version
        self.check()
    
    def check(self):
        for path in self.dlls:
            if not os.path.exists(f"{self.base_path}/{path}"):
                self.dlls.remove(path)
                for dll in self.dlls[path]:
                    if not os.path.exists(f"{self.base_path}/{path}/{dll}"):
                        self.dlls[path].remove(dll)
        if len(self.dlls) == 0:
            return False
        return True
    
    def install(self, config:BottleConfig, overrides_only:bool=False, exclude:list=[]):
        for path in self.dlls:
            for dll in self.dlls[path]:
                if dll not in exclude:
                    self.__install_dll(config, path, dll, False, overrides_only)

    def uninstall(self, config:BottleConfig, exclude:list=[]):
        for path in self.dlls:
            for dll in self.dlls[path]:
                if dll not in exclude:
                    self.__uninstall_dll(config, path, dll)
    
    def __get_sys_path(self, config, path:str):
        if config["Arch"] == "win32":
            if path in ["x32", "x86"]:
                return "system32"
        elif config["Arch"] == "win64":
            if path in ["x64"]:
                return "system32"
            elif path in ["x32", "x86"]:
                return "syswow64"
        return None

    def __install_dll(self, config, path:str, dll:str, remove:bool=False, overrides_only:bool=False):
        dll_name = dll.split('/')[-1]
        bottle = ManagerUtils.get_bottle_path(config)
        bottle = f"{bottle}/drive_c/windows/"
        source = f"{self.base_path}/{path}/{dll}"
        target = f"{bottle}/{self.__get_sys_path(config, path)}/{dll_name}"
        #print(f"{source} -> {target}")
        
        if target is not None:
            if not remove:
                if not overrides_only:
                    if os.path.exists(target):
                        shutil.copy(target, f"{target}.bck")
                    shutil.copyfile(source, target)
                Runner.reg_add(
                    config,
                    key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                    value=dll_name.split('.')[0],
                    data="native,builtin"
                )
            else:
                Runner.reg_delete(
                    config,
                    key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                    value=dll_name.split('.')[0]
                )
                if os.path.exists(f"{target}.bck"):
                    shutil.move(f"{target}.bck", target)
                elif os.path.exists(target):
                    os.remove(target)

    def __uninstall_dll(self, config, path:str, dll:str):
        self.__install_dll(config, path, dll, remove=True)
