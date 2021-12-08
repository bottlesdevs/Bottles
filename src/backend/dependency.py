# dependency.py
#
# Copyright 2020 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import yaml
import shutil
import patoolib
from glob import glob
import urllib.request
from functools import lru_cache
from typing import Union, NewType
from gi.repository import Gtk, GLib

from .result import Result
from .runner import Runner
from .globals import BottlesRepositories, Paths
from ..operation import OperationManager
from .manager_utils import ManagerUtils
from ..utils import UtilsLogger, CabExtract, validate_url

logging = UtilsLogger()

# Define custom types for better understanding of the code
BottleConfig = NewType('BottleConfig', dict)


class DependencyManager:

    def __init__(self, manager):
        self.__manager = manager
        self.__window = manager.window
        self.__utils_conn = manager.utils_conn
        self.__operation_manager = OperationManager(self.__window)

    @lru_cache
    def get_dependency(
        self,
        dependency_name: str,
        dependency_category: str,
        plain: bool = False
    ) -> Union[str, dict, bool]:
        '''
        This function can be used to fetch the manifest for a given
        dependency. It can be returned as plain text or as a dictionary.
        It will return False if the dependency is not found.
        '''
        if self.__utils_conn.check_connection():
            try:
                with urllib.request.urlopen("%s/%s/%s.yml" % (
                    BottlesRepositories.dependencies,
                    dependency_category,
                    dependency_name
                )) as url:
                    if plain:
                        '''
                        Caller required the component manifest
                        as plain text.
                        '''
                        return url.read().decode("utf-8")

                    # return as dictionary
                    return yaml.safe_load(url.read())
            except:
                logging.error(f"Cannot fetch manifest for {dependency_name}.")
                return False

        return False

    @lru_cache
    def fetch_catalog(self) -> list:
        '''
        This function fetch all dependencies from the Bottles repository
        and return these as a dictionary. It also returns an empty dictionary
        if there are no dependencies or fails to fetch them.
        '''
        catalog = {}
        if not self.__utils_conn.check_connection():
            return {}

        try:
            with urllib.request.urlopen(
                BottlesRepositories.dependencies_index
            ) as url:
                index = yaml.safe_load(url.read())
        except:
            logging.error(F"Cannot fetch dependencies list.")
            return {}

        for dependency in index.items():
            catalog[dependency[0]] = dependency[1]
            
        catalog = dict(sorted(catalog.items()))
        return catalog

    def install(
        self,
        config: BottleConfig,
        dependency: list
    ) -> Result:
        '''
        This function install a given dependency in a bottle. It will
        return True if the installation was successful.
        '''
        uninstaller = True

        if config["Versioning"]:
            '''
            If the bottle has the versioning system enabled, we need
            to create a new version of the bottle, before installing
            the dependency.
            '''
            self.__manager.versioning_manager.create_state(
                config=config,
                comment=f"before {dependency[0]}",
                update=True
            )

        task_entry = self.__operation_manager.new_task(
            file_name=dependency[0],
            cancellable=False
        )

        logging.info(
            "Installing dependency [%s] in bottle [%s]." % (
                dependency[0],
                config['Name']
            )
        )
        manifest = self.get_dependency(
            dependency_name=dependency[0],
            dependency_category=dependency[1]["Category"]
        )
        if not manifest:
            '''
            If the manifest is not found, return a Result
            object with the error.
            '''
            GLib.idle_add(task_entry.remove)
            return Result(
                status=False,
                message=f"Cannot find manifest for {dependency[0]}."
            )

        for step in manifest.get("Steps"):
            '''
            Here we execute all steps in the manifest.
            Steps are the actions performed to install the dependency.
            '''
            res = self.__perform_steps(config, step)
            if not res.status:
                GLib.idle_add(task_entry.remove)
                return Result(
                    status=False,
                    message=f"One or more steps failed for {dependency[0]}."
                )
            if not res.data.get("uninstaller"):
                uninstaller = False

        if dependency[0] not in config.get("Installed_Dependencies"):
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

        self.__manager.update_config(
            config,
            dependency[0],
            uninstaller,
            "Uninstallers"
        )

        # Remove entry from download manager
        GLib.idle_add(task_entry.remove)

        # Hide installation button and show remove button
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
        config:BottleConfig, 
        step:dict
    ) -> bool:
        """
        This method execute a step in the bottle (e.g. changing the Windows
        version, installing fonts, etc.)
        ---
        Returns True if the dependency cannot be uninstalled.
        """
        uninstaller = True
        
        if step["action"] == "download_archive":
            if not self.__step_download_archive(step):
                return Result(status=False)

        if step["action"] == "delete_sys32_dlls":
            self.__step_delete_sys32_dlls(
                config=config,
                dlls=step["dlls"]
            )

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

        if step["action"] in ["copy_cab_dll", "copy_dll"]:
            uninstaller = False
            if not self.__step_copy_dll(config=config, step=step):
                return Result(status=False)

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


    def __step_download_archive(self, step: dict):
        '''
        This function download an archive from the given step.
        Can be used for any file type (cab, zip, ...). Please don't
        use this method for exe/msi files as the install_exe already
        download the exe/msi file before installation.
        '''
        download = self.__manager.component_manager.download(
            component="dependency",
            download_url=step.get("url"),
            file=step.get("file_name"),
            rename=step.get("rename"),
            checksum=step.get("file_checksum")
        )

        return download

    def __step_delete_sys32_dlls(self, config: BottleConfig, dlls: list):
        '''
        This function deletes the given dlls from the system32 folder
        of the bottle.
        '''
        for dll in dlls:
            try:
                logging.info(
                    "Removing [%s] from system32 in bottle: [%s]" % (
                        dll,
                        config['Name']
                    )
                )
                os.remove(
                    "%s/%s/drive_c/windows/system32/%s" % (
                        Paths.bottles,
                        config.get("Name"),
                        dll
                    )
                )
            except FileNotFoundError:
                logging.error(
                    "DLL [%s] not found in bottle [%s]." % (
                        dll,
                        config['Name'],
                    )
                )
        
        # return True in both cases, has it is a non-critical error
        return True

    def __step_install_exe_msi(
        self,
        config: BottleConfig,
        step: dict
    ) -> bool:
        '''
        This function download and install the .exe or .msi file
        declared in the step, in a bottle.
        '''
        download = self.__manager.component_manager.download(
            component="dependency",
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

            Runner.run_executable(
                config=config,
                file_path=f"{Paths.temp}/{file}",
                arguments=step.get("arguments"),
                environment=step.get("environment"),
                no_async=True
            )
            Runner.wait_for_process(config, file)
            return True

        return False

    def __step_uninstall(self, config: BottleConfig, file_name: str) -> bool:
        '''
        This function find an uninstaller in the bottle by the given
        file name and execute it.
        '''
        command = f"uninstaller --list | grep '{file_name}' | cut -f1 -d\|"

        uuid = Runner.run_command(
            config=config,
            command=command,
            terminal=False,
            environment=False,
            comunicate=True
        )
        uuid = uuid.strip()

        if uuid != "":
            logging.info(
                "Uninstalling [%s] from bottle: [%s]." % (
                    file_name,
                    config['Name']
                )
            )
            Runner.run_uninstaller(config, uuid)
        
        return True

    def __step_cab_extract(self, step: dict):
        '''
        This function download and extract a Windows Cabinet to the
        temp folder.
        '''
        if validate_url(step["url"]):
            download = self.__manager.component_manager.download(
                component="dependency",
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
                    path=f"{Paths.temp}/{file}",
                    name=file
                ):
                    return False

                if not CabExtract().run(
                    f"{Paths.temp}/{file}",
                    os.path.splitext(f"{file}")[0]
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

    def __step_get_from_cab(
        self,
        config: BottleConfig,
        step: dict
    ):
        '''
        This function take a file from a cab file and extract it to
        the defined path.
        '''
        source = step.get("source")
        file_name = step.get("file_name")

        res = CabExtract().run(
            path=f"{Paths.temp}/{source}",
            files=[file_name]
        )

        if not res:
            return False

        if step.get("dest"):
            dest = step.get("dest")
            dest_file_name = step.get("file_name")

            if step.get("rename"):
                dest_file_name = step.get("rename")

            if dest.startswith("temp/"):
                dest = dest.replace("temp/", f"{Paths.temp}/")

            if dest.startswith("drive_c/"):
                bottle_path = ManagerUtils.get_bottle_path(config)
                dest = dest.replace(
                    "drive_c/",
                    f"{bottle_path}/drive_c/"
                )
            elif dest.startswith("temp/"):
                dest = dest.replace("temp/", f"{Paths.temp}/")
            else:
                dest = f"{Paths.temp}/{dest}"

            shutil.copy(
                f"{Paths.temp}/{file_name}",
                f"{dest}/{dest_file_name}"
            )
        
        return True

    def __step_archive_extract(self, step: dict):
        '''
        This function download and extract the archive declared
        in the step, in the temp folder.
        '''
        download = self.__manager.component_manager.download(
            component="dependency",
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

            archive_name = os.path.splitext(file)[0]

            if os.path.exists(f"{Paths.temp}/{archive_name}"):
                shutil.rmtree(
                    f"{Paths.temp}/{archive_name}")

            os.makedirs(f"{Paths.temp}/{archive_name}")
            patoolib.extract_archive(
                f"{Paths.temp}/{file}",
                outdir=f"{Paths.temp}/{archive_name}"
            )
            return True
        
        return False

    def __step_install_fonts(self, config: BottleConfig, step: dict):
        '''
        This function copy the fonts declared in the step in
        the bottle drive_c/windows/Fonts path.
        '''
        path = step["url"]
        path = path.replace("temp/", f"{Paths.temp}/")
        bottle_path = ManagerUtils.get_bottle_path(config)

        for font in step.get('fonts'):
            try:
                shutil.copyfile(
                    f"{path}/{font}",
                    f"{bottle_path}/drive_c/windows/Fonts/{font}"
                )
            except FileNotFoundError:
                logging.error(
                    "Font [%s] not found in [%s]." % (
                        font,
                        path
                    )
                )
                return False
        
        return True

    def __step_copy_dll(self, config: BottleConfig, step: dict):
        '''
        This function copy dlls from temp folder to a directory
        declared in the step. The bottle drive_c path will be used as
        root path.
        '''
        path = step["url"]
        path = path.replace("temp/", f"{Paths.temp}/")
        bottle_path = ManagerUtils.get_bottle_path(config)

        try:
            if "*" in step.get('file_name'):
                files = glob(f"{path}/{step.get('file_name')}")
                for fg in files:
                    dest = "%s/drive_c/%s/%s" % (
                        bottle_path,
                        step.get('dest'),
                        os.path.basename(fg)
                    )
                    shutil.copyfile(fg, dest)
            else:
                shutil.copyfile(
                    f"{path}/{step.get('file_name')}",
                    f"{bottle_path}/drive_c/{step.get('dest')}"
                )

        except FileNotFoundError:
            logging.error(
                f"dll {step.get('file_name')} not found in temp, \
                    there should be other errors from cabextract."
            )
            return False
        
        return True

    def __step_override_dll(self, config: BottleConfig, step: dict):
        '''
        This function register a new override for each dll declared
        in the step, for a bottle.
        '''
        if step.get("url") and step.get("url").startswith("temp/"):
            path = step["url"].replace(
                "temp/",
                f"{Paths.temp}/"
            )
            path = f"{path}/{step.get('dll')}"

            for dll in glob(path):
                dll_name = os.path.splitext(os.path.basename(dll))[0]
                Runner.reg_add(
                    config,
                    key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
                    value=dll_name,
                    data=step.get("type")
                )
            return True

        Runner.reg_add(
            config,
            key="HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides",
            value=step.get("dll"),
            data=step.get("type")
        )
        return True

    def __step_set_register_key(self, config: BottleConfig, step: dict):
        '''
        This function set a register key in the bottle registry. It is
        just a mirror of the reg_add function from the manager. 
        '''
        Runner.reg_add(
            config,
            key=step.get("key"),
            value=step.get("value"),
            data=step.get("data"),
            keyType=step.get("type")
        )
        return True

    def __step_register_font(self, config: BottleConfig, step: dict):
        '''
        This function register a font in the bottle registry. It is
        important to make the font available in the system.
        '''
        Runner.reg_add(
            config,
            key="HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts",
            value=step.get("name"),
            data=step.get("file")
        )
        return True

    def __step_replace_font(self, config: BottleConfig, step: dict):
        '''
        This function replace the font declared in the step in
        the bottle registry.
        '''
        replaces = step.get("replace")

        if len(replaces) == 1:
            Runner.reg_add(
                config,
                key="HKEY_CURRENT_USER\\Software\\Wine\\Fonts\\Replacements",
                value=step.get("font"),
                data=step.get("replace")
            )
        else:
            for r in replaces:
                Runner.reg_add(
                    config,
                    key="HKEY_CURRENT_USER\\Software\\Wine\\Fonts\\Replacements",
                    value=step.get("font"),
                    data=r
                )
        return True

    def __step_set_windows(self, config: BottleConfig, step: dict):
        '''
        This function set the windows version in the bottle registry.
        '''
        Runner.set_windows(config, step.get("version"))
        return True

    def __step_use_windows(self, config: BottleConfig, step: dict):
        '''
        This function set the windows version for a specifc executable 
        in the bottle registry.
        '''
        Runner.set_app_default(config, step.get("version"), step.get("executable"))
        return True
