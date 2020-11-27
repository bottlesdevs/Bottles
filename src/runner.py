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

import os, logging, subprocess, urllib.request, json, tarfile, time, psutil, shutil

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

    '''
    Define local path for temp and runners
    '''
    temp_path = "%s/.local/share/bottles/temp" % Path.home()
    runners_path = "%s/.local/share/bottles/runners" % Path.home()
    bottles_path = "%s/.local/share/bottles/bottles" % Path.home()

    runners_available = []
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
        "Update_Date": ""
    }

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        logging.debug("Runner")

        '''
        Common variables
        '''
        self.window = window
        self.settings = window.settings

        self.check_runners(install_latest=False)
        self.check_bottles()

    '''
    Performs all checks in one async shot
    '''
    def async_checks(self):
        self.check_runners_dir()
        self.check_runners()
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

        if not os.path.isdir(self.temp_path):
            logging.info("Temp path doens't exist, creating now.")
            os.makedirs(self.temp_path, exist_ok=True)
        else:
            self.clear_temp()

        return True

    '''
    Extract a runner archive
    '''
    def extract_runner(self, archive):
        archive = tarfile.open("%s/%s" % (self.temp_path, archive))
        archive.extractall(self.runners_path)

    '''
    Download a specific runner release
    '''
    def download_runner(self, tag, file):
        urllib.request.urlretrieve("%s/download/%s/%s" % (self.repository,
                                                          tag,
                                                          file),
                                   "%s/%s" % (self.temp_path, file))

    '''
    Localy install a new runner async
    '''
    def async_install_runner(self, args):

        '''
        Send a notification for download start if the
        user settings allow it
        '''
        if self.settings.get_boolean("notifications"):
            self.window.send_notification("Download manager",
                                          "Installing `%s` runner …" % args[0],
                                          "document-save-symbolic")

        '''
        Add a new entry to the download manager
        '''
        download_entry = BottlesDownloadEntry(file_name=args[0],
                                              stoppable=False)
        self.window.box_downloads.add(download_entry)

        logging.info("Installing the `%s` runner." % args[0])

        '''
        Run the progressbar update async
        '''
        a = RunAsync('pulse', download_entry.pulse)
        a.start()

        '''
        Download and extract the runner archive
        '''
        self.download_runner(args[0], args[1])
        self.extract_runner(args[1])

        '''
        Clear available runners list and do the check again
        '''
        self.runners_available = []
        self.check_runners()

        '''
        Send a notification for download end if the
        user settings allow it
        '''
        if self.settings.get_boolean("notifications"):
            self.window.send_notification("Download manager",
                                          "Installation of `%s` runner finished!" % args[0],
                                          "software-installed-symbolic")
        '''
        Remove the entry from the download manager
        '''
        download_entry.destroy()

        '''
        Update runners
        '''
        self.window.page_preferences.update_runners()

    def install_runner(self, tag, file):
        a = RunAsync('install', self.async_install_runner, [tag, file])
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

            with urllib.request.urlopen(self.repository_api) as url:
                releases = json.loads(url.read().decode())
                tag = releases[0]["tag_name"]
                file = releases[0]["assets"][0]["name"]

                self.install_runner(tag, file)

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
    Create a new wineprefix async
    '''
    def async_create_bottle(self, args):
        logging.info("Creating the wineprefix…")

        '''
        Set UI to not usable
        '''
        self.window.set_usable_ui(False)

        '''
        Define bottle parameters
        '''
        bottle_name = args[0]
        bottle_name_path = bottle_name.replace(" ", "-")

        if args[2] == "":
            bottle_custom_path = False
            bottle_complete_path = "%s/%s" % (self.bottles_path, bottle_name_path)
        else:
            bottle_custom_path = True
            bottle_complete_path = args[2]

        bottle_environment = args[1]

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

        '''
        Prepare and execute the command
        '''
        command = "WINEPREFIX={path} WINEARCH=win64 {runner} wineboot".format(
            path = bottle_complete_path,
            runner = "%s/%s/bin/wine" % (self.runners_path,
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
        end_iter = buffer_output.get_end_iter()
        buffer_output.insert(end_iter, process_output)

        '''
        Generate bottle configuration file
        '''
        buffer_output.insert(end_iter, "Generating Bottle configuration file…")
        configuration = self.sample_configuration
        configuration["Name"] = bottle_name
        configuration["Runner"] = self.runners_available[0]
        if args[2] == "":
            configuration["Path"] = bottle_name_path
        else:
            configuration["Path"] = bottle_complete_path
        configuration["Custom_Path"] = bottle_custom_path
        configuration["Environment"] = bottle_environment
        configuration["Creation_Date"] = str(date.today())
        configuration["Update_Date"] = str(date.today())

        with open("%s/bottle.json" % bottle_complete_path,
                  "w") as configuration_file:
            json.dump(configuration, configuration_file, indent=4)
            configuration_file.close()

        '''
        Set the list button visible and set UI to usable again
        '''
        buffer_output.insert(
            end_iter,
            "Your new bottle with name `%s` is now ready!" % bottle_name)
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
        disk = psutil.disk_usage('/')

        disk_total = disk.total
        disk_used = disk.used
        disk_free = disk.free

        if human:
            disk_total = self.get_human_size(disk.total)
            disk_used = self.get_human_size(disk.used)
            disk_free = self.get_human_size(disk.free)

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

        command = "WINEPREFIX={path} WINEARCH=win64 {runner} {command}".format(
            path = path,
            runner = "%s/%s/bin/wine" % (self.runners_path, runner),
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
            "reboot": "-r"
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


