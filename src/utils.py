# utils.py
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
import re
import sys
import shutil
import logging
import socket
import subprocess
import hashlib
import threading
import traceback

from datetime import datetime
from pathlib import Path

from gi.repository import GLib

from .pages.dialog import BottlesDialog

# Set default logging level
logging.basicConfig(level=logging.DEBUG)

# Check online connection
class UtilsConnection():

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        self.window = window

    def check_connection(self, show_notification=False):
        try:
            socket.gethostbyname('usebottles.com')
            self.window.toggle_btn_noconnection(False)

            self.last_check = datetime.now()
            self.status = True

            return True
        except socket.error:
            logging.warning("Connection status: offline …")
            self.window.toggle_btn_noconnection(True)

            if show_notification:
                self.window.send_notification("Bottles",
                                              _("You are offline, unable to download."),
                                              "network-wireless-disabled-symbolic")
            self.last_check = datetime.now()
            self.status = False

        return False

# Launch commands in system terminal
class UtilsTerminal():

    terminals = [
        ['xterm', '-e %s'],
        ['konsole', '-e %s'],
        ['gnome-terminal', '-- %s'],
        ['xfce4-terminal', '--command %s'],
        ['mate-terminal', '--command %s'],
        ['tilix', '-- %s'],
    ]

    def __init__(self, command):
        for terminal in self.terminals:
            terminal_check = subprocess.Popen(
                "command -v %s > /dev/null && echo 1 || echo 0" % terminal[0],
                shell=True,
                stdout=subprocess.PIPE).communicate()[0].decode("utf-8")
            if "1" in terminal_check:
                subprocess.Popen(
                    " ".join(terminal) % 'bash -c "%s"' % command,
                    shell=True,
                    stdout=subprocess.PIPE).communicate()[0].decode("utf-8")
                break

# Custom formatted logger
class UtilsLogger(logging.getLoggerClass()):

    color_map = {
        "debug": 37,
        "info": 36,
        "warning": 33,
        "error": 31,
        "critical": 41
    }

    format_log = {
        'fmt': '%(asctime)s \033[1m%(levelname)s\033[0m: %(message)s',
        'datefmt': '%Y-%m-%d %H:%M:%S',
    }

    def color(self, level, message):
        color_id = self.color_map[level]
        return "\033[%dm%s\033[0m" % (color_id, message)

    def __init__(self, formatter=None):
        if formatter is None:
            formatter = self.format_log
        formatter = logging.Formatter(**formatter)

        self.root.setLevel(logging.INFO)
        self.root.handlers = []

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.root.addHandler(handler)

    def debug(self, message):
        self.root.debug(self.color("debug", message))

    def info(self, message):
        self.root.info(self.color("info", message))

    def warning(self, message):
        self.root.warning(self.color("warning", message))

    def error(self, message):
        self.root.error(self.color("error", message))

    def critical(self, message):
        self.root.critical(self.color("critical", message))

# Files utilities
class UtilsFiles():

    @staticmethod
    def get_checksum(file):
        checksum = hashlib.md5()

        try:
            with open(file, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    checksum.update(chunk)
            return checksum.hexdigest().lower()
        except FileNotFoundError:
            return False

    @staticmethod
    def use_insensitive_ext(string):
        # Converts a glob pattern into a case-insensitive glob pattern
        ext = string.split('.')[1]
        globlist = ["[%s%s]" % (c.lower(), c.upper()) for c in ext]
        return '*.%s' % ''.join(globlist)


def write_log(data:list):
    log_path = f"{Path.home()}/.local/share/bottles/crash.log"
    if "IS_FLATPAK" in os.environ:
        log_path = f"{Path.home()}/.var/app/{os.environ['FLATPAK_ID']}/data/crash.log"

    with open(log_path, "w") as crash_log:
        for d in data:
            crash_log.write(d)


# Execute synchronous tasks
class RunAsync(threading.Thread):

    def __init__(self, task_func, callback, *args, **kwargs):
        self.source_id = None
        self.stop_request = threading.Event()

        super(RunAsync, self).__init__(target=self.target, args=args, kwargs=kwargs)

        self.task_func = task_func

        self.callback = callback if callback else lambda r, e: None
        self.daemon = kwargs.pop("daemon", True)

        self.start()

    def target(self, *args, **kwargs):
        result = None
        error = None

        logging.debug(f"Running async job [{self.task_func}].")

        try:
            result = self.task_func(*args, **kwargs)
        except Exception as exception:
            logging.error(f"Error while running async job: {self.task_func}\nException: {exception}")

            error = exception
            _ex_type, _ex_value, trace = sys.exc_info()
            traceback.print_tb(trace)
            traceback_info = '\n'.join(traceback.format_tb(trace))

            write_log([str(exception), traceback_info])

        self.source_id = GLib.idle_add(self.callback, result, error)
        return self.source_id


# Extract a Windows cabinet
class CabExtract():

    requirements = False

    def __init__(self, path: str, name: str):
        self.path = path
        self.name = name

        self.__checks()
        self.__extract()

    def __checks(self):
        if not os.path.exists(self.path):
            logging.error(f"Cab file {self.path} not found")
            write_log(f"Cab file {self.path} not found")
            exit()

        if not self.path.endswith((".exe", ".msi")):
            logging.error(f"{self.path} is not a cab file")
            write_log(f"{self.path} is not a cab file")
            exit()
        
        if not shutil.which("cabextract"):
            logging.fatal("cabextract utility not found, please install to use dependencies wich need this feature")
            write_log("cabextract utility not found, please install to use dependencies wich need this feature")
            exit()
        
        return True

    def __extract(self) -> bool:
        temp_path = f"{Path.home()}/.local/share/bottles/temp"
        if "IS_FLATPAK" in os.environ:
            temp_path = f"{Path.home()}/.var/app/{os.environ['FLATPAK_ID']}/data/bottles/temp"

        try:
            subprocess.Popen(
                f"cabextract {self.path} -d {temp_path}/{self.name}",
                shell=True
            ).communicate()
        except Exception as exception:
            logging.error(f"Error while extracting cab file {self.path}:\n{exception}")
            return False

        return True


        
def validate_url(url: str):
    regex = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return re.match(regex, url) is not None
