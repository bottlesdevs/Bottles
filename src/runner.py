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

import os, logging, subprocess, urllib.request, json, tarfile, time

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
        if self.settings.get_boolean("download-notifications"):
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
        if self.settings.get_boolean("download-notifications"):
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
            logging.info("Runners found: \n%s" % ', '.join(self.runners_available))

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
        Define bottle parameters
        '''
        bottle_name = args[0]
        bottle_name_path = bottle_name.replace(" ", "-")
        if not args[2]:
            bottle_path = self.bottles_path
        else:
            bottle_path = args[2]
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
        btn_open = self.window.page_create.btn_open

        '''
        Prepare and execute the command
        '''
        command = "WINEPREFIX={path} WINEARCH=win64 {runner} wineboot".format(
            path = "%s/%s" % (bottle_path, bottle_name_path),
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
        configuration["Path"] = bottle_name_path
        configuration["Environment"] = bottle_environment
        configuration["Creation_Date"] = str(date.today())
        configuration["Update_Date"] = str(date.today())

        with open("%s/%s/bottle.json" % (bottle_path, bottle_name_path),
                  "w") as configuration_file:
            json.dump(configuration, configuration_file, indent=4)
            configuration_file.close()

        '''
        Set the open button visible
        '''
        buffer_output.insert(
            end_iter,
            "Your new bottle with name `%s` is now ready!" % bottle_name)
        btn_open.set_visible(True)

    def create_bottle(self, name, environment, path=False):
        a = RunAsync('create', self.async_create_bottle, [name,
                                                          environment,
                                                          path])
        a.start()

    '''
    Delete a wineprefix
    '''
    def delete_bottle(self):
        logging.info("Deleting the wineprefix…")

    '''
    Methods for running wine applications in wineprefixes
    '''
    def run_executable(self):
        logging.info("Running an executable on the wineprefix…")

    def run_winecfg(self):
        logging.info("Running winecfg on the wineprefix…")

    def run_winetricks(self):
        logging.info("Running winetricks on the wineprefix…")

    def run_debug(self):
        logging.info("Running a debug console on the wineprefix…")

    def run_cmd(self):
        logging.info("Running a CMD on the wineprefix…")

    def run_taskmanager(self):
        logging.info("Running a Task Manager on the wineprefix…")

    def run_controlpanel(self):
        logging.info("Running a Control Panel on the wineprefix…")

    def run_uninstaller(self):
        logging.info("Running an Uninstaller on the wineprefix…")

    def run_regedit(self):
        logging.info("Running a Regedit on the wineprefix…")

    '''
    Method for sending status to wineprefixes
    '''
    def send_status(self, status):
        available_status = ["shutdown",
                            "reboot"]
        logging.info("Sending %s status to the wineprefix…" % available_status[status])

    '''
    Method for open wineprefixes path in file manager
    '''
    def open_filemanager(self):
        logging.info("Opening the file manager on the wineprefix path…")

