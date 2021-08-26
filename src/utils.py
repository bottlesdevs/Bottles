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

from typing import Union
from datetime import datetime
from pathlib import Path

from gi.repository import GLib

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
                self.window.send_notification(
                    title="Bottles",
                    text=_("You are offline, unable to download."),
                    image="network-wireless-disabled-symbolic"
                )
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
                f"command -v {terminal[0]} > /dev/null && echo 1 || echo 0",
                shell=True,
                stdout=subprocess.PIPE).communicate()[0].decode("utf-8")

            if "1" in terminal_check:
                subprocess.Popen(
                    ' '.join(terminal) % f"bash -c '{command}'",
                    shell=True,
                    stdout=subprocess.PIPE).communicate()[0].decode("utf-8")
                break

# Custom formatted logger
class UtilsLogger(logging.getLoggerClass()):

    __color_map = {
        "debug": 37,
        "info": 36,
        "warning": 33,
        "error": 31,
        "critical": 41
    }

    __format_log = {
        'fmt': '%(asctime)s \033[1m%(levelname)s\033[0m: %(message)s',
        'datefmt': '%Y-%m-%d %H:%M:%S',
    }

    def __color(self, level, message):
        color_id = self.__color_map[level]
        return "\033[%dm%s\033[0m" % (color_id, message)

    def __init__(self, formatter=None):
        if formatter is None:
            formatter = self.__format_log
        formatter = logging.Formatter(**formatter)

        self.root.setLevel(logging.INFO)
        self.root.handlers = []

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.root.addHandler(handler)

    def debug(self, message):
        self.root.debug(self.__color("debug", message))

    def info(self, message):
        self.root.info(self.__color("info", message))

    def warning(self, message):
        self.root.warning(self.__color("warning", message))

    def error(self, message):
        self.root.error(self.__color("error", message))

    def critical(self, message):
        self.root.critical(self.__color("critical", message))

# Files utilities
class UtilsFiles():

    @staticmethod
    def get_checksum(file):
        '''
        This function returns the MD5 checksum of the given file.
        '''
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
        '''
        This function converts a glob pattern into a case-insensitive
        glob pattern
        '''
        ext = string.split('.')[1]
        globlist = ["[%s%s]" % (c.lower(), c.upper()) for c in ext]
        return '*.%s' % ''.join(globlist)
    
    @staticmethod
    def get_human_size(size:float) -> str:
        '''
        This function returns a human readable size from a given float size.
        '''
        for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
            if abs(size) < 1024.0:
                return "%3.1f%s%s" % (size, unit, 'B')
            size /= 1024.0

        return "%.1f%s%s" % (size, 'Yi', 'B')
    

    def get_path_size(self, path:str, human:bool=True) -> Union[str, float]:
        '''
        This function returns the size of a given path in human readable
        format or in bytes. Default is human readable, set human to False
        to get bytes.
        '''
        path = Path(path)
        size = sum(f.stat().st_size for f in path.glob('**/*') if f.is_file())

        if human: return self.get_human_size(size)

        return size

    def get_disk_size(self, human:bool=True) -> dict:
        '''
        This function returns the size of the disk in human readable format
        or in bytes. Default is human readable, set human to False to get
        bytes.
        '''
        disk_total, disk_used, disk_free = shutil.disk_usage('/')

        if human:
            disk_total = self().get_human_size(disk_total)
            disk_used = self().get_human_size(disk_used)
            disk_free = self().get_human_size(disk_free)

        return {
            "total": disk_total,
            "used": disk_used,
            "free": disk_free,
        }


def write_log(data:list):
    '''
    This function writes a crash.log file.
    It takes care of the location of the log whether Bottles is running 
    under Flatpak or not. It also find and replace the user's home directory
    with "USER" as a proposed standard for crash reports.
    '''
    log_path = f"{Path.home()}/.local/share/bottles/crash.log"
    if "FLATPAK_ID" in os.environ:
        log_path = f"{Path.home()}/.var/app/{os.environ['FLATPAK_ID']}/data/crash.log"

    with open(log_path, "w") as crash_log:
        for d in data:
            # replace username with "USER" as standard
            if "/home/" in d:
                d = re.sub(r"/home/([^/]*)/", r"/home/USER/", d)
                
            crash_log.write(d)


class RunAsync(threading.Thread):

    '''
    This class is used to execute a function asynchronously.
    It take a function, a callback and a list of arguments as input.
    '''
    def __init__(self, task_func, callback, *args, **kwargs):
        self.source_id = None
        self.stop_request = threading.Event()

        super(RunAsync, self).__init__(target=self.__target, args=args, kwargs=kwargs)

        self.task_func = task_func

        self.callback = callback if callback else lambda r, e: None
        self.daemon = kwargs.pop("daemon", True)

        self.start()

    def __target(self, *args, **kwargs):
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


class CabExtract():

    '''
    This class is used to extract a Windows cabinet file.
    It takes the cabinet file path and the destination name as input. Then it
    extracts the file in a new directory with the input name under the Bottles'
    temp directory.
    '''
    requirements = False
    
    def run(self, path: str, name: str="", files: list = []):
        self.path = path
        self.name = name
        self.files = files

        if not self.__checks():
            return False
        return self.__extract()

    def __checks(self):
        if not os.path.exists(self.path) and "*" not in self.path:
            logging.error(f"Cab file {self.path} not found")
            write_log(f"Cab file {self.path} not found")
            return False

        if not self.path.lower().endswith((".exe", ".msi", ".cab")):
            logging.error(f"{self.path} is not a cab file")
            write_log(f"{self.path} is not a cab file")
            return False
        
        if not shutil.which("cabextract"):
            logging.fatal("cabextract utility not found, please install to use dependencies wich need this feature")
            write_log("cabextract utility not found, please install to use dependencies wich need this feature")
            return False
        
        return True

    def __extract(self) -> bool:
        temp_path = f"{Path.home()}/.local/share/bottles/temp"
        if "FLATPAK_ID" in os.environ:
            temp_path = f"{Path.home()}/.var/app/{os.environ['FLATPAK_ID']}/data/bottles/temp"

        try:
            if len(self.files) > 0:
                for file in self.files:
                    subprocess.Popen(
                        f"cabextract -F '*{file}*' -d {temp_path}/{self.name} -q {self.path}",
                        shell=True
                    ).communicate()
            else:
                subprocess.Popen(
                    f"cabextract -d {temp_path}/{self.name} -q {self.path}",
                    shell=True
                ).communicate()

            return True
        except Exception as exception:
            logging.error(f"Error while extracting cab file {self.path}:\n{exception}")

        return False


        
def validate_url(url: str):
    '''
    This function validates a given URL.
    It returns True if the URL is valid, False otherwise.
    '''
    regex = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return re.match(regex, url) is not None
