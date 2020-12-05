# runner.py
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

import os, logging, subprocess, urllib.request, json, tarfile, time, shutil

from glob import glob
from threading import Thread
from pathlib import Path
from datetime import date

from .download import BottlesDownloadEntry
from .pages.list import BottlesListEntry

'''
Set the default logging level
'''
logging.basicConfig(level=logging.DEBUG)

class RunAsync(Thread):

    def __init__(self, task_name, task_func, task_args=False):
        Thread.__init__(self)

        self.task_name = task_name
        self.task_func = task_func
        self.task_args = task_args

    def run(self):
        logging.debug('Running async job `%s`.' % self.task_name)

        if not self.task_args:
            self.task_func()
        else:
            self.task_func(self.task_args)

class BottlesRunner:

    '''
    Define repositories URLs
    TODO: search for vanilla wine binary repository
    '''
    repository = "https://github.com/lutris/wine/releases"
    repository_api = "https://api.github.com/repos/lutris/wine/releases"
    dxvk_repository = "https://github.com/doitsujin/dxvk/releases"
    dxvk_repository_api = "https://api.github.com/repos/doitsujin/dxvk/releases"

    '''
    Define local path for temp and runners
    '''
    temp_path = "%s/.local/share/bottles/temp" % Path.home()
    runners_path = "%s/.local/share/bottles/runners" % Path.home()
    bottles_path = "%s/.local/share/bottles/bottles" % Path.home()
    dxvk_path = "%s/.local/share/bottles/dxvk" % Path.home()

    '''
    Do not implement dxgi.dll <https://github.com/doitsujin/dxvk/wiki/DXGI>
    '''
    dxvk_dlls = [
        "d3d10core.dll",
        "d3d11.dll",
        "d3d9.dll",
    ]

    runners_available = []
    dxvk_available = []
    local_bottles = {}

    '''
    Structure of bottle configuration file
    '''
    sample_configuration = {
        "Name": "",
        "Runner": "",
        "Path": "",
        "Custom_Path": False,
        "Environment": "",
        "Creation_Date": "",
        "Update_Date": "",
        "Parameters": {
            "dxvk": False,
            "esync": False,
            "fsync": False,
            "discrete_gpu": False,
            "virtual_desktop": False,
            "virtual_desktop_res": "",
            "pulseaudio_latency": False
        },
        "Installed_Dependencies" : []
    }

    '''
    TODO: fetch supported dependencies from an online repository
    for a more extensible support
    '''
    supported_dependencies = {
        "corefonts" : {
            "description" : "Microsoft Core Fonts",
            "url" : ""
        },
        "vcrun6" : {
            "description" : "Visual C++ 6 SP4 libraries",
            "url" : ""
        },
        "mfc40" : {
            "description" : "Microsoft Foundation Classes from win7sp1",
            "url" : ""
        }
    }

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        '''
        Common variables
        '''
        self.window = window
        self.settings = window.settings
        self.utils_conn = window.utils_conn

        self.check_runners(install_latest=False)
        self.check_dxvk(install_latest=False)
        self.check_bottles()

    '''
    Performs all checks in one async shot
    '''
    def async_checks(self):
        self.check_runners_dir()
        self.check_runners()
        self.check_dxvk()
        self.check_bottles()

    def checks(self):
        a = RunAsync('checks', self.async_checks)
        a.start()

    '''
    Clear temp path
    '''
    def clear_temp(self):
        logging.info("Cleaning the temp path.")

        for f in os.listdir(self.temp_path):
            os.remove(os.path.join(self.temp_path, f))


    '''
    Check if standard directories not exists, then create
    '''
    def check_runners_dir(self):
        if not os.path.isdir(self.runners_path):
            logging.info("Runners path doens't exist, creating now.")
            os.makedirs(self.runners_path, exist_ok=True)

        if not os.path.isdir(self.bottles_path):
            logging.info("Bottles path doens't exist, creating now.")
            os.makedirs(self.bottles_path, exist_ok=True)

        if not os.path.isdir(self.dxvk_path):
            logging.info("Dxvk path doens't exist, creating now.")
            os.makedirs(self.dxvk_path, exist_ok=True)

        if not os.path.isdir(self.temp_path):
            logging.info("Temp path doens't exist, creating now.")
            os.makedirs(self.temp_path, exist_ok=True)
        else:
            self.clear_temp()

        return True

    '''
    Extract a component archive
    '''
    def extract_component(self, component, archive):
        if component == "runner":
            path = self.runners_path

        if component == "dxvk":
            path = self.dxvk_path

        archive = tarfile.open("%s/%s" % (self.temp_path, archive))
        archive.extractall(path)

    '''
    Download a specific component release
    '''
    def download_component(self, component, tag, file):
        if component == "runner":
            repository = self.repository

        if component == "dxvk":
            repository = self.dxvk_repository


        urllib.request.urlretrieve("%s/download/%s/%s" % (repository,
                                                          tag,
                                                          file),
                                   "%s/%s" % (self.temp_path, file))

    '''
    Localy install a new component (runner, dxvk, ..) async
    '''
    def async_install_component(self, args):
        component, tag, file = args

        '''
        Send a notification for download start if the
        user settings allow it
        '''
        if self.settings.get_boolean("notifications"):
            self.window.send_notification("Download manager",
                                          "Installing `%s` runner …" % tag,
                                          "document-save-symbolic")

        '''
        Add a new entry to the download manager
        '''
        if component == "runner":
            file_name = tag
        if component == "dxvk":
            file_name = "dxvk-%s" % tag

        download_entry = BottlesDownloadEntry(file_name=file_name,
                                              stoppable=False)
        self.window.box_downloads.add(download_entry)

        logging.info("Installing the `%s` component." % tag)

        '''
        Run the progressbar update async
        '''
        a = RunAsync('pulse', download_entry.pulse)
        a.start()

        '''
        Download and extract the component archive
        '''
        self.download_component(component, tag, file)
        self.extract_component(component, file)

        '''
        Clear available component list and do the check again
        '''
        if component == "runner":
            self.runners_available = []
            self.check_runners()

        if component == "dxvk":
            self.dxvk_available = []
            self.check_dxvk()

        '''
        Send a notification for download end if the
        user settings allow it
        '''
        if self.settings.get_boolean("notifications"):
            self.window.send_notification("Download manager",
                                          "Installation of `%s` component finished!" % tag,
                                          "software-installed-symbolic")
        '''
        Remove the entry from the download manager
        '''
        download_entry.destroy()

        '''
        Update components
        '''
        if component == "runner":
            self.window.page_preferences.update_runners()
        if component == "dxvk":
            self.window.page_preferences.update_dxvk()

    def install_component(self, component,  tag, file):
        if self.utils_conn.check_connection(True):
            a = RunAsync('install', self.async_install_component, [component, tag, file])
            a.start()

    '''
    Check localy available runners
    '''
    def check_runners(self, install_latest=True):
        runners = glob("%s/*/" % self.runners_path)

        for runner in runners:
            self.runners_available.append(runner.split("/")[-2])

        if len(self.runners_available) > 0:
            logging.info("Runners found: \n%s" % ', '.join(
                self.runners_available))

        '''
        If there are no locally installed runners, download the
        latest version available from Lutris' GitHub repository
        (currently the only one providing the wine binaries)
        '''
        if len(self.runners_available) == 0 and install_latest:
            logging.info("No runners found.")

            '''
            Fetch runners from repository only if connected
            '''
            if self.utils_conn.check_connection():
                with urllib.request.urlopen(self.repository_api) as url:
                    releases = json.loads(url.read().decode())
                    tag = releases[0]["tag_name"]
                    file = releases[0]["assets"][0]["name"]

                    self.install_component("runner", tag, file)

    '''
    Check localy available dxvk
    '''
    def check_dxvk(self, install_latest=True):
        dxvk_list = glob("%s/*/" % self.dxvk_path)

        for dxvk in dxvk_list:
            self.dxvk_available.append(dxvk.split("/")[-2])

        if len(self.dxvk_available) > 0:
            logging.info("Dxvk found: \n%s" % ', '.join(
                self.dxvk_available))

        if len(self.dxvk_available) == 0 and install_latest:
            logging.info("No dxvk found.")

            '''
            Fetch dxvk from repository only if connected
            '''
            if self.utils_conn.check_connection():
                with urllib.request.urlopen(self.dxvk_repository_api) as url:
                    releases = json.loads(url.read().decode())
                    tag = releases[0]["tag_name"]
                    file = releases[0]["assets"][0]["name"]

                    self.install_component("dxvk", tag, file)

    '''
    Check local bottles
    '''
    def check_bottles(self):
        bottles = glob("%s/*/" % self.bottles_path)

        '''
        For each bottle add the path name to the `local_bottles` variable
        and append the configuration
        '''
        for bottle in bottles:
            bottle_name_path = bottle.split("/")[-2]
            configuration_file = open('%s/bottle.json' % bottle)
            configuration_file_json = json.load(configuration_file)
            configuration_file.close()

            self.local_bottles[bottle_name_path] = configuration_file_json

        if len(self.local_bottles) > 0:
            logging.info("Bottles found: \n%s" % ', '.join(self.local_bottles))

    '''
    Update parameters in bottle configuration file
    '''
    def update_configuration(self, configuration, key, value, is_parameter=False):
        logging.info("Setting `%s` parameter to `%s` for `%s` Bottle…" % (
            key, value, configuration.get("Name")
        ))

        if configuration.get("Custom_Path"):
            bottle_complete_path = configuration.get("Path")
        else:
            bottle_complete_path = "%s/%s" % (self.bottles_path,
                                              configuration.get("Path"))

        if is_parameter:
            configuration["Parameters"][key] = value
        else:
            configuration[key] = value

        with open("%s/bottle.json" % bottle_complete_path,
                  "w") as configuration_file:
            json.dump(configuration, configuration_file, indent=4)
            configuration_file.close()

        self.window.page_list.update_bottles()
        return configuration

    '''
    Create a new wineprefix async
    '''
    def async_create_bottle(self, args):
        logging.info("Creating the wineprefix…")

        name, environment, path = args

        '''
        Set UI to not usable
        '''
        self.window.set_usable_ui(False)

        '''
        Define bottle parameters
        '''
        bottle_name = name
        bottle_name_path = bottle_name.replace(" ", "-")

        if path == "":
            bottle_custom_path = False
            bottle_complete_path = "%s/%s" % (self.bottles_path, bottle_name_path)
        else:
            bottle_custom_path = True
            bottle_complete_path = path

        '''
        Run the progressbar update async
        '''
        a = RunAsync('pulse', self.window.page_create.pulse)
        a.start()

        '''
        Define reusable variables
        '''
        buffer_output = self.window.page_create.buffer_output
        btn_list = self.window.page_create.btn_list
        iter = buffer_output.get_end_iter()

        buffer_output.insert(iter, "The wine configuration is being updated…\n")
        iter = buffer_output.get_end_iter()

        '''
        Prepare and execute the command
        '''
        command = "WINEPREFIX={path} WINEARCH=win64 {runner} wineboot".format(
            path = bottle_complete_path,
            runner = "%s/%s/bin/wine64" % (self.runners_path,
                                         self.runners_available[0])
        )

        '''
        Get the command output and add to the buffer
        '''
        process = subprocess.Popen(command,
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        process_output = process.stdout.read().decode("utf-8")

        buffer_output.insert(iter, process_output)
        iter = buffer_output.get_end_iter()

        '''
        Generate bottle configuration file
        '''
        buffer_output.insert(iter, "\nGenerating Bottle configuration file…")
        iter = buffer_output.get_end_iter()

        configuration = self.sample_configuration
        configuration["Name"] = bottle_name
        configuration["Runner"] = self.runners_available[0]
        if path == "":
            configuration["Path"] = bottle_name_path
        else:
            configuration["Path"] = bottle_complete_path
        configuration["Custom_Path"] = bottle_custom_path
        configuration["Environment"] = environment
        configuration["Creation_Date"] = str(date.today())
        configuration["Update_Date"] = str(date.today())

        with open("%s/bottle.json" % bottle_complete_path,
                  "w") as configuration_file:
            json.dump(configuration, configuration_file, indent=4)
            configuration_file.close()

        '''
        Set the list button visible and set UI to usable again
        '''
        buffer_output.insert_markup(
            iter,
            "\n<span foreground='green'>%s</span>" % "Your new bottle with name `%s` is now ready!" % bottle_name,
            -1)
        iter = buffer_output.get_end_iter()

        btn_list.set_visible(True)
        self.window.set_usable_ui(True)


        '''
        Clear local bottles list and do the check again
        '''
        self.local_bottles = {}
        self.check_bottles()

    def create_bottle(self, name, environment, path=False):
        a = RunAsync('create', self.async_create_bottle, [name,
                                                          environment,
                                                          path])
        a.start()

    '''
    Get latest installed runner
    '''
    def get_latest_runner(self):
        return self.runners_available[0]

    '''
    Get human size
    '''
    def get_human_size(self, size):
        for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
            if abs(size) < 1024.0:
                return "%3.1f%s%s" % (size, unit, 'B')
            size /= 1024.0

        return "%.1f%s%s" % (size, 'Yi', 'B')

    '''
    Get path size
    '''
    def get_path_size(self, path, human=True):
        path = Path(path)
        size = sum(f.stat().st_size for f in path.glob('**/*') if f.is_file())

        if human:
            return self.get_human_size(size)

        return size

    '''
    Get disk size
    '''
    def get_disk_size(self, human=True):
        '''
        TODO: disk should be taken from configuration Path
        '''
        disk_total, disk_used, disk_free = shutil.disk_usage('/')

        if human:
            disk_total = self.get_human_size(disk_total)
            disk_used = self.get_human_size(disk_used)
            disk_free = self.get_human_size(disk_free)

        return {
            "total": disk_total,
            "used": disk_free,
            "free": disk_free,
        }

    '''
    Get bottle path size
    '''
    def get_bottle_size(self, configuration, human=True):
        path = configuration.get("Path")
        runner = configuration.get("Runner")

        if not configuration.get("Custom_Path"):
            path = "%s/%s" % (self.bottles_path, path)

        return self.get_path_size(path, human)

    '''
    Delete a wineprefix
    '''
    def async_delete_bottle(self, args):
        logging.info("Deleting the wineprefix…")

        configuration = args[0]

        '''
        Delete path with all files
        '''
        path = configuration.get("Path")

        if not configuration.get("Custom_Path"):
            path = "%s/%s" % (self.bottles_path, path)

        shutil.rmtree(path)

    def delete_bottle(self, configuration):
        a = RunAsync('delete', self.async_delete_bottle, [configuration])
        a.start()

    '''
    Methods for add and remove values to register
    '''
    def reg_delete(self, configuration, key, value):
        logging.info("Removing value `%s` for key `%s` in register for `%s` bottle." % (
            value, key, configuration.get("Name")
        ))

        self.run_command(configuration, "reg delete '%s' /v %s /f" % (
            key, value
        ))

    def reg_add(self, configuration, key, value, data):
        logging.info("Adding value `%s` with data `%s` for key `%s` in register for `%s` bottle." % (
            value, data, key, configuration.get("Name")
        ))

        self.run_command(configuration, "reg add '%s' /v %s /d %s /f" % (
            key, value, data
        ))

    '''
    Methods for install and remove dxvk using official setup script
    TODO: A good task for the future is to use the built-in methods to
    install the new dlls and register the override.
    '''
    def install_dxvk(self, configuration, remove=False):
        logging.info("Installing dxvk for `%s` bottle." % configuration.get("Name"))

        if remove:
            option = "uninstall"
        else:
            option = "install"

        command = 'WINEPREFIX="{path}" PATH="{runner}:$PATH" {dxvk_setup} {option}'.format (
            path = "%s/%s" % (self.bottles_path, configuration.get("Path")),
            runner = "%s/%s/bin" % (self.runners_path, configuration.get("Runner")),
            dxvk_setup = "%s/%s/setup_dxvk.sh" % (self.dxvk_path, self.dxvk_available[0]),
            option = option
        )
        return subprocess.Popen(command, shell=True)

    def remove_dxvk(self, configuration):
        logging.info("Removing dxvk for `%s` bottle." % configuration.get("Name"))

        self.install_dxvk(configuration, remove=True)

    '''
    Method for override dll in system32/syswow64 paths
    '''
    def dll_override(self, configuration, arch, dlls, source, revert=False):
        if arch == 32:
            arch = "system32"
        else:
            arch = "syswow64"

        path = "%s/%s/drive_c/windows/%s" % (self.bottles_path,
                                             configuration.get("Path"),
                                             arch)

        '''
        Revert dll from backup
        '''
        if revert:
            for dll in dlls:
                shutil.move("%s/%s.back" % (path, dll), "%s/%s" % (path, dll))
        else:
            '''
            Backup old dlls and install new one
            '''
            for dll in dlls:
                shutil.move("%s/%s" % (path, dll), "%s/%s.old" % (path, dll))
                shutil.copy("%s/%s" % (source, dll), "%s/%s" % (path, dll))

    '''
    Methods for running wine applications in wineprefixes
    '''
    def run_executable(self, configuration, file_path):
        logging.info("Running an executable on the wineprefix…")

        '''
        Escape spaces in command
        '''
        file_path = file_path.replace(" ", "\ ")

        self.run_command(configuration, file_path)

    def run_winecfg(self, configuration):
        logging.info("Running winecfg on the wineprefix…")
        self.run_command(configuration, "winecfg")

    def run_winetricks(self, configuration):
        logging.info("Running winetricks on the wineprefix…")
        self.run_command(configuration, "winetricks")

    def run_debug(self, configuration):
        logging.info("Running a debug console on the wineprefix…")
        self.run_command(configuration, "winedbg")

    def run_cmd(self, configuration):
        logging.info("Running a CMD on the wineprefix…")
        self.run_command(configuration, "wineconsole cmd")

    def run_taskmanager(self, configuration):
        logging.info("Running a Task Manager on the wineprefix…")
        self.run_command(configuration, "taskmgr")

    def run_controlpanel(self, configuration):
        logging.info("Running a Control Panel on the wineprefix…")
        self.run_command(configuration, "control")

    def run_uninstaller(self, configuration):
        logging.info("Running an Uninstaller on the wineprefix…")
        self.run_command(configuration, "uninstaller")

    def run_regedit(self, configuration):
        logging.info("Running a Regedit on the wineprefix…")
        self.run_command(configuration, "regedit")

    '''
    Run wine command in a bottle
    '''
    def run_command(self, configuration, command):
        '''
        Prepare and execute the command
        '''
        path = configuration.get("Path")
        runner = configuration.get("Runner")
        if not configuration.get("Custom_Path"):
            path = "%s/%s" % (self.bottles_path, path)

        '''
        Get environment variables from configuration to pass
        as command arguments
        '''
        environment_vars = []
        parameters = configuration["Parameters"]

        if parameters["dxvk"]:
            '''
            TODO: dxvk hud should be removed in stable release
            '''
            environment_vars.append("WINEDLLOVERRIDES='d3d11,dxgi=n'")
            environment_vars.append("DXVK_HUD='1'")

        if parameters["esync"]:
            environment_vars.append("WINEESYNC=1 WINEDEBUG=+esync")

        if parameters["fsync"]:
            environment_vars.append("WINEFSYNC=1")

        if parameters["discrete_gpu"]:
            environment_vars.append("__NV_PRIME_RENDER_OFFLOAD=1")
            environment_vars.append("__GLX_VENDOR_LIBRARY_NAME='nvidia'")
            environment_vars.append("__VK_LAYER_NV_optimus='NVIDIA_only'")

        if parameters["pulseaudio_latency"]:
            environment_vars.append("PULSE_LATENCY_MSEC=60")

        environment_vars = " ".join(environment_vars)

        command = "WINEPREFIX={path} WINEARCH=win64 {env} {runner} {command}".format(
            path = path,
            env = environment_vars,
            runner = "%s/%s/bin/wine64" % (self.runners_path, runner),
            command = command
        )
        return subprocess.Popen(command, shell=True)

    '''
    Method for sending status to wineprefixes
    '''
    def send_status(self, configuration, status):
        logging.info("Sending %s status to the wineprefix…" % status)

        available_status = {
            "shutdown": "-s",
            "reboot": "-r",
            "kill": "-k"
        }
        option = available_status[status]
        bottle_name = configuration.get("Name")

        '''
        Prepare and execute the command
        '''
        self.run_command(configuration, "wineboot %s" % option)

        '''
        Send a notification for statush change if the
        user settings allow it
        '''
        if self.settings.get_boolean("notifications"):
            self.window.send_notification("Bottles",
                                          "`%s` completed for `%s`." % (
                                              status,
                                              bottle_name
                                          ), "applications-system-symbolic")

    '''
    Method for open wineprefixes path in file manager
    '''
    def open_filemanager(self, configuration):
        logging.info("Opening the file manager on the wineprefix path…")

        bottle_path = configuration.get("Path")

        '''
        Prepare and execute the command
        '''
        command = "xdg-open %s/%s/drive_c" % (self.bottles_path, bottle_path)
        return subprocess.Popen(command, shell=True)


