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

import sys
import logging
import socket
import subprocess
import hashlib
import threading
import traceback

from datetime import datetime, timedelta

from gi.repository import GLib

'''Set default logging level'''
logging.basicConfig(level=logging.DEBUG)

'''Check online connection'''
class UtilsConnection():

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        self.window = window

    def check_connection(self, show_notification=False):
        try:
            socket.create_connection(("1.1.1.1", 80))
            logging.info(_("Connection status: online …"))
            self.window.toggle_btn_noconnection(False)

            self.last_check = datetime.now()
            self.status = True

            return True
        except OSError:
            logging.info(_("Connection status: offline …"))
            self.window.toggle_btn_noconnection(True)

            if show_notification:
                self.window.send_notification("Bottles",
                                              _("You are offline, unable to download."),
                                              "network-wireless-disabled-symbolic")
            self.last_check = datetime.now()
            self.status = False

        return False

'''Launch commands in system terminal'''
class UtilsTerminal():

    terminals = [
        ['xterm', '-e %s'],
        ['konsole', '-e %s'],
        ['gnome-terminal', '-- %s'],
        ['xfce4-terminal', '--command %s'],
        ['mate-terminal', '--command %s']
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

'''Custom formatted logger'''
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

    def __init__(self, formatter=format_log):
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

'''Files utilities'''
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

'''Execute synchronous tasks'''
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

        logging.debug('Running async job [{0}].'.format(self.task_func))

        try:
            result = self.task_func(*args, **kwargs)
        except Exception as exception:
            logging.error(
                "Error while running async job: {0}\nException: {1}".format(
                    self.task_func, exception))
            error = exception
            _ex_type, _ex_value, trace = sys.exc_info()
            traceback.print_tb(trace)

        self.source_id = GLib.idle_add(self.callback, result, error)
        return self.source_id
