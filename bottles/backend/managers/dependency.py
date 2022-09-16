# dependency.py
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
import uuid
import shutil
import patoolib
from glob import glob
from functools import lru_cache
from typing import Union, NewType
from gi.repository import GLib

try:
    from bottles.frontend.operation import OperationManager  # pyright: reportMissingImports=false
except (RuntimeError, GLib.GError):
    from bottles.frontend.cli.operation_cli import OperationManager

from bottles.backend.utils.generic import validate_url
from bottles.backend.models.result import Result
from bottles.backend.runner import Runner
from bottles.backend.logger import Logger
from bottles.backend.cabextract import CabExtract
from bottles.backend.globals import Paths
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.uninstaller import Uninstaller
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.reg import Reg
from bottles.backend.wine.regsvr32 import Regsvr32
from bottles.backend.wine.regkeys import RegKeys
from bottles.backend.wine.executor import WineExecutor

logging = Logger()


class DependencyManager:

    def __init__(self, manager, offline: bool = False):
        self.__manager = manager
        self.__repo = manager.repository_manager.get_repo("dependencies", offline)
        self.__window = manager.window
        self.__utils_conn = manager.utils_conn
        self.__operation_manager = OperationManager(self.__window)

    @lru_cache
    def get_dependency(self, name: str, plain: bool = False) -> Union[str, dict]:
        return self.__repo.get(name, plain)

    @lru_cache
    def fetch_catalog(self) -> dict:
        """
        Fetch all dependencies from the Bottles repository
        and return these as a dictionary. It also returns an empty dictionary
        if there are no dependencies or fails to fetch them.
        """
        if not self.__utils_conn.check_connection():
            return {}

        catalog = {}
        index = self.__repo.catalog

        for dependency in index.items():
            catalog[dependency[0]] = dependency[1]

        catalog = dict(sorted(catalog.items()))
        return catalog

    def install(
            self,
            config: dict,
            dependency: list,
            reinstall: bool = False
    ) -> Result:
        """
        Install a given dependency in a bottle. It will
        return True if the installation was successful.
        """
        task_id = str(uuid.uuid4())
        uninstaller = True

        if config["Parameters"]["versioning_automatic"]:
            '''
            If the bottle has the versioning system enabled, we need
            to create a new version of the bottle, before installing
            the dependency.
            '''
            self.__manager.versioning_manager.create_state(
                config=config,
                message=f"Before installing {dependency[0]}"
            )

        GLib.idle_add(
            self.__operation_manager.new_task, task_id, dependency[0], False
        )

        logging.info("Installing dependency [%s] in bottle [%s]." % (
            dependency[0],
            config['Name']
        ), )
        manifest = self.get_dependency(dependency[0])
        if not manifest:
            '''
            If the manifest is not found, return a Result
            object with the error.
            '''
            GLib.idle_add(self.__operation_manager.remove_task, task_id)
            return Result(
                status=False,
                message=f"Cannot find manifest for {dependency[0]}."
            )

        if manifest.get("Dependencies"):
            '''
            If the manifest has dependencies, we need to install them
            before installing the current one.
            '''
            for _ext_dep in manifest.get("Dependencies"):
                if _ext_dep in config["Installed_Dependencies"]:
                    continue
                if _ext_dep in self.__manager.supported_dependencies:
                    _dep = self.__manager.supported_dependencies[_ext_dep]
                    _res = self.install(config, [_ext_dep, _dep])
                    if not _res.status:
                        return _res

        for step in manifest.get("Steps"):
            '''
            Here we execute all steps in the manifest.
            Steps are the actions performed to install the dependency.
            '''
            res = self.__perform_steps(config, step)
            if not res.status:
                GLib.idle_add(self.__operation_manager.remove_task, task_id)
                return Result(
                    status=False,
                    message=f"One or more steps failed for {dependency[0]}."
                )
            if not res.data.get("uninstaller"):
                uninstaller = False

        if dependency[0] not in config.get("Installed_Dependencies") \
                or reinstall:
            '''
            If the dependency is not already listed in the installed
            dependencies list of the bottle, add it.
            '''
            dependencies = [dependency[0]]

            if config.get("Installed_Dependencies"):
                dependencies = config["Installed_Dependencies"] + \
                               [dependency[0]]

            self.__manager.update_config(
                config=config,
                key="Installed_Dependencies",
                value=dependencies
            )

        if manifest.get("Uninstaller"):
            '''
            If the manifest has an uninstaller, add it to the
            uninstaller list in the bottle config.
            Set it to NO_UNINSTALLER if the dependency cannot be uninstalled.
            '''
            uninstaller = manifest.get("Uninstaller")

        if dependency[0] not in config["Installed_Dependencies"]:
            self.__manager.update_config(
                config,
                dependency[0],
                uninstaller,
                "Uninstallers"
            )

        # Remove entry from operation manager
        GLib.idle_add(self.__operation_manager.remove_task, task_id)

        # Hide installation button and show remove button
        logging.info(f"Dependency installed: {dependency[0]} in {config['Name']}", jn=True)
        if not uninstaller:
            return Result(
                status=True,
                data={"uninstaller": False}
            )
        return Result(
            status=True,
            data={"uninstaller": True}
        )

    def __perform_steps(
            self,
            config: dict,
            step: dict
    ) -> bool:
        """
        This method execute a step in the bottle (e.g. changing the Windows
        version, installing fonts, etc.)
        ---
        Returns True if the dependency cannot be uninstalled.
        """
        uninstaller = True

        if step["action"] == "delete_dlls":
            self.__step_delete_dlls(config, step)

        if step["action"] == "download_archive":
            if not self.__step_download_archive(step):
                return Result(status=False)

        if step["action"] in ["install_exe", "install_msi"]:
            if not self.__step_install_exe_msi(config=config, step=step):
                return Result(status=False)

        if step["action"] == "uninstall":
            self.__step_uninstall(config=config, file_name=step["file_name"])

        if step["action"] == "cab_extract":
            uninstaller = False
            if not self.__step_cab_extract(step=step):
                return Result(status=False)

        if step["action"] == "get_from_cab":
            uninstaller = False
            if not self.__step_get_from_cab(config=config, step=step):
                return Result(status=False)

        if step["action"] == "archive_extract":
            uninstaller = False
            if not self.__step_archive_extract(step):
                return Result(status=False)

        if step["action"] in ["install_cab_fonts", "install_fonts"]:
            uninstaller = False
            if not self.__step_install_fonts(config=config, step=step):
                return Result(status=False)

        if step["action"] in ["copy_dll", "copy_file"]:
            uninstaller = False
            if not self.__step_copy_dll(config=config, step=step):
                return Result(status=False)

        if step["action"] == "register_dll":
            self.__step_register_dll(
                config=config,
                step=step
            )

        if step["action"] == "override_dll":
            self.__step_override_dll(
                config=config,
                step=step
            )

        if step["action"] == "set_register_key":
            self.__step_set_register_key(
                config=config,
                step=step
            )

        if step["action"] == "register_font":
            self.__step_register_font(
                config=config,
                step=step
            )

        if step["action"] == "replace_font":
            self.__step_replace_font(
                config=config,
                step=step
            )

        if step["action"] == "set_windows":
            self.__step_set_windows(
                config=config,
                step=step
            )

        if step["action"] == "use_windows":
            self.__step_use_windows(
                config=config,
                step=step
            )

        return Result(
            status=True,
            data={"uninstaller": uninstaller}
        )

    @staticmethod
    def __get_real_dest(config: dict, dest: str) -> Union[str, bool]:
        """This function return the real destination path."""
        bottle = ManagerUtils.get_bottle_path(config)
        _dest = dest

        if dest.startswith("temp/"):
            dest = dest.replace("temp/", f"{Paths.temp}/")
        elif dest.startswith("windows/"):
            dest = f"{bottle}/drive_c/{dest}"
        elif dest.startswith("win32"):
            dest = f"{bottle}/drive_c/windows/system32/"
            if config.get("Arch") == "win64":
                dest = f"{bottle}/drive_c/windows/syswow64/"
            dest = _dest.replace("win32", dest)
        elif dest.startswith("win64"):
            if config.get("Arch") == "win64":
                dest = f"{bottle}/drive_c/windows/system32/"
                dest = _dest.replace("win64", dest)
            else:
                return True
        else:
            logging.error("Destination path not supported!")
            return False

        return dest

    def __step_download_archive(self, step: dict):
        """
        This function download an archive from the given step.
        Can be used for any file type (cab, zip, ...). Please don't
        use this method for exe/msi files as the install_exe already
        download the exe/msi file before installation.
        """
        download = self.__manager.component_manager.download(
            download_url=step.get("url"),
            file=step.get("file_name"),
            rename=step.get("rename"),
            checksum=step.get("file_checksum")
        )

        return download

    def __step_install_exe_msi(self, config: dict, step: dict) -> bool:
        """
        Download and install the .exe or .msi file
        declared in the step, in a bottle.
        """
        winedbg = WineDbg(config)
        download = self.__manager.component_manager.download(
            download_url=step.get("url"),
            file=step.get("file_name"),
            rename=step.get("rename"),
            checksum=step.get("file_checksum")
        )
        file = step.get("file_name")
        if step.get("rename"):
            file = step.get("rename")

        if download:
            if step.get("url").startswith("temp/"):
                _file = step.get("url").replace("temp/", f"{Paths.temp}/")
                file = f"{_file}/{file}"
            else:
                file = f"{Paths.temp}/{file}"
            executor = WineExecutor(
                config,
                exec_path=file,
                args=step.get("arguments"),
                environment=step.get("environment")
            )
            executor.run()
            winedbg.wait_for_process(file)
            return True

        return False

    @staticmethod
    def __step_uninstall(config: dict, file_name: str) -> bool:
        """
        This function find an uninstaller in the bottle by the given
        file name and execute it.
        """
        Uninstaller(config).from_name(file_name)
        return True

    def __step_cab_extract(self, step: dict):
        """
        This function download and extract a Windows Cabinet to the
        temp folder.
        """
        dest = step.get("dest")
        if dest.startswith("temp/"):
            dest = dest.replace("temp/", f"{Paths.temp}/")
        else:
            logging.error("Destination path not supported!")
            return False

        if validate_url(step["url"]):
            download = self.__manager.component_manager.download(
                download_url=step.get("url"),
                file=step.get("file_name"),
                rename=step.get("rename"),
                checksum=step.get("file_checksum")
            )

            if download:
                if step.get("rename"):
                    file = step.get("rename")
                else:
                    file = step.get("file_name")

                if not CabExtract().run(
                        path=os.path.join(Paths.temp, file),
                        name=file,
                        destination=dest
                ):
                    return False

        elif step["url"].startswith("temp/"):
            path = step["url"]
            path = path.replace("temp/", f"{Paths.temp}/")

            if step.get("rename"):
                file_path = os.path.splitext(
                    f"{step.get('rename')}")[0]
            else:
                file_path = os.path.splitext(
                    f"{step.get('file_name')}")[0]

            if not CabExtract().run(
                    f"{path}/{step.get('file_name')}",
                    file_path
            ):
                return False

        return True

    def __step_delete_dlls(self, config: dict, step: dict):
        """Deletes the given dlls from the system32 or syswow64 paths"""
        dest = self.__get_real_dest(config, step.get("dest"))

        for d in step.get("dlls", []):
            _d = os.path.join(dest, d)
            if os.path.exists(_d):
                os.remove(_d)

        return True

    def __step_get_from_cab(self, config: dict, step: dict):
        """Take a file from a cabiner and extract to a path."""
        source = step.get("source")
        file_name = step.get("file_name")
        rename = step.get("rename")
        dest = self.__get_real_dest(config, step.get("dest"))

        if isinstance(dest, bool):
            return dest

        res = CabExtract().run(
            path=os.path.join(Paths.temp, source),
            files=[file_name],
            destination=dest
        )

        if rename:
            _file_name = file_name.split("/")[-1]

            if os.path.exists(os.path.join(dest, rename)):
                os.remove(os.path.join(dest, rename))

            shutil.move(
                os.path.join(dest, _file_name),
                os.path.join(dest, rename)
            )

        if not res:
            return False
        return True

    def __step_archive_extract(self, step: dict):
        """Download and extract an archive to the temp folder."""
        download = self.__manager.component_manager.download(
            download_url=step.get("url"),
            file=step.get("file_name"),
            rename=step.get("rename"),
            checksum=step.get("file_checksum")
        )

        if download:
            if step.get("rename"):
                file = step.get("rename")
            else:
                file = step.get("file_name")

            archive_path = os.path.join(Paths.temp, os.path.splitext(file)[0])

            if os.path.exists(archive_path):
                shutil.rmtree(archive_path)

            os.makedirs(archive_path)
            try:
                patoolib.extract_archive(
                    os.path.join(Paths.temp, file),
                    outdir=archive_path
                )
            except:
                return False
            return True

        return False

    @staticmethod
    def __step_install_fonts(config: dict, step: dict):
        """Move fonts to the drive_c/windows/Fonts path."""
        path = step["url"]
        path = path.replace("temp/", f"{Paths.temp}/")
        bottle_path = ManagerUtils.get_bottle_path(config)

        for font in step.get('fonts'):
            font_path = f"{bottle_path}/drive_c/windows/Fonts/"
            if not os.path.exists(font_path):
                os.makedirs(font_path)

            try:
                shutil.copyfile(f"{path}/{font}", f"{font_path}/{font}")
            except (FileNotFoundError, FileExistsError):
                logging.warning(f"Font {font} already exists or is not found.")

            # print(f"Copying {font} to {bottle_path}/drive_c/windows/Fonts/")

        return True

    # noinspection PyTypeChecker
    def __step_copy_dll(self, config: dict, step: dict):
        """
        This function copy dlls from temp folder to a directory
        declared in the step. The bottle drive_c path will be used as
        root path.
        """
        path = step["url"]
        path = path.replace("temp/", f"{Paths.temp}/")
        dest = self.__get_real_dest(config, step.get("dest"))

        if isinstance(dest, bool):
            return dest
            
        if not os.path.exists(dest):
            os.makedirs(dest)

        try:
            if "*" in step.get('file_name'):
                files = glob(f"{path}/{step.get('file_name')}")
                for fg in files:
                    _name = fg.split("/")[-1]
                    _path = os.path.join(path, _name)
                    _dest = os.path.join(dest, _name)
                    logging.info(f"Copying {_name} to {_dest}")

                    if os.path.exists(_dest) and os.path.islink(_dest):
                        os.unlink(_dest)

                    try:
                        shutil.copyfile(_path, _dest)
                    except shutil.SameFileError:
                        logging.info(f"{_name} already exists at the same version, skipping.")
            else:
                _name = step.get('file_name')
                _dest = os.path.join(dest, _name)
                logging.info(f"Copying {_name} to {_dest}")

                if os.path.exists(_dest) and os.path.islink(_dest):
                    os.unlink(_dest)

                try:
                    shutil.copyfile(os.path.join(path, _name), _dest)
                except shutil.SameFileError:
                    logging.info(f"{_name} already exists at the same version, skipping.")

        except Exception as e:
            print(e)
            logging.warning("An error occurred while copying dlls.")
            return False

        return True

    @staticmethod
    def __step_register_dll(config: dict, step: dict):
        """Register one or more dll and ActiveX control"""
        regsvr32 = Regsvr32(config)

        for dll in step.get('dlls', []):
            regsvr32.register(dll)

        return True

    @staticmethod
    def __step_override_dll(config: dict, step: dict):
        """Register a new override for each dll."""
        reg = Reg(config)

        if step.get("url") and step.get("url").startswith("temp/"):
            path = step["url"].replace("temp/", f"{Paths.temp}/")
            dlls = glob(os.path.join(path, step.get("dll")))

            for dll in dlls:
                reg.add(
                    key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                    value=dll,
                    data=step.get("type")
                )
            return True

        if step.get("bundle"):
            _bundle = {"HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides": step.get("bundle")}
            reg.import_bundle(_bundle)
            return True

        reg.add(
            key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
            value=step.get("dll"),
            data=step.get("type")
        )
        return True

    @staticmethod
    def __step_set_register_key(config: dict, step: dict):
        """Set a registry key."""
        reg = Reg(config)
        reg.add(
            key=step.get("key"),
            value=step.get("value"),
            data=step.get("data"),
            key_type=step.get("type")
        )
        return True

    @staticmethod
    def __step_register_font(config: dict, step: dict):
        """Register a font in the registry."""
        reg = Reg(config)
        reg.add(
            key="HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts",
            value=step.get("name"),
            data=step.get("file")
        )
        return True

    @staticmethod
    def __step_replace_font(config: dict, step: dict):
        """Register a font replacement in the registry."""
        reg = Reg(config)
        replaces = step.get("replace")

        if len(replaces) == 1:
            reg.add(
                key="HKEY_CURRENT_USER\\Software\\Wine\\Fonts\\Replacements",
                value=step.get("font"),
                data=step.get("replace")
            )
        else:
            for r in replaces:
                reg.add(
                    key="HKEY_CURRENT_USER\\Software\\Wine\\Fonts\\Replacements",
                    value=step.get("font"),
                    data=r
                )
        return True

    @staticmethod
    def __step_set_windows(config: dict, step: dict):
        """Set the Windows version."""
        rk = RegKeys(config)
        rk.set_windows(step.get("version"))
        return True

    @staticmethod
    def __step_use_windows(config: dict, step: dict):
        """Set a Windows version per program."""
        rk = RegKeys(config)
        rk.set_app_default(step.get("version"), step.get("executable"))
        return True
