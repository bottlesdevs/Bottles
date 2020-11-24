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

import os, logging, subprocess, urllib.request, json, tarfile
from glob import glob

'''
Set the default logging level
'''
logging.basicConfig(level=logging.DEBUG)

class Runner:

    '''
    Define repositories URLs
    TODO: search for vanilla wine binary repository
    '''
    repository = "https://github.com/lutris/wine/releases"
    repository_api = "https://api.github.com/repos/lutris/wine/releases"

    '''
    Define local path for temp and runners
    '''
    temp_path = "./.local/share/bottles/temp"
    runners_path = "./.local/share/bottles/runners"

    runners_available = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        logging.debug("Runner")
        self.check_runners(install_latest=False)

    '''
    Performs all checks in one shot
    '''
    def checks(self):
        self.check_runners_dir()
        self.check_runners()

    '''
    Clear temp path
    '''
    def clear_temp(self):
        logging.info("Cleaning the temp path.")
        for f in os.listdir(self.temp_path):
            os.remove(os.path.join(self.temp_path, f))


    '''
    Check if `runners` directory not exists, then create
    '''
    def check_runners_dir(self):
        if not os.path.isdir(self.runners_path):
            logging.info("Runners path doens't exist, creating now.")
            os.makedirs(self.runners_path, exist_ok=True)

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
    Localy install a new runner
    '''
    def install_runner(self, tag, file):
        logging.info("Installing the `%s` runner." % tag)
        self.download_runner(tag, file)
        self.extract_runner(file)

        '''
        Clear available runners list and do the check again
        '''
        self.runners_available = []
        self.check_runners()

    '''
    Check localy available runners
    '''
    def check_runners(self, install_latest=True):
        runners = glob("%s/*/" % self.runners_path)

        for runner in runners:
            self.runners_available.append(runner.split("/")[5])

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
    Create/delete method for wineprefixes
    '''
    def create_bottle(self):
        logging.info("Creating the wineprefix…")

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

