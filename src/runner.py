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

import logging, subprocess

'''
Set the default logging level
'''
logging.basicConfig(level=logging.DEBUG)

class Runner:

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        logging.debug("runner")

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

