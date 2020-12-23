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

import logging, socket, subprocess

'''
Set the default logging level
'''
logging.basicConfig(level=logging.DEBUG)

class UtilsConnection():

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        self.window = window

    def check_connection(self, show_notification=False):
        try:
            socket.create_connection(("1.1.1.1", 53))
            logging.info("Connection status: online …")
            self.window.toggle_btn_noconnection(False)
            return True
        except OSError:
            logging.info("Connection status: offline …")
            self.window.toggle_btn_noconnection(True)

            if show_notification:
                self.window.send_notification("Bottles",
                                              "You are offline, unable to download.",
                                              "network-wireless-disabled-symbolic")
            pass
        return False

class UtilsTerminal():

    terminals = [
        'gnome-terminal -- %s',
        'xterm -e %s',
        'konsole -e %s',
        'xfce4-terminal --command %s',
    ]

    def __init__(self, command, **kwargs):
        super().__init__(**kwargs)

        for terminal in self.terminals:
            command = terminal % 'bash -c "%s"' % command
            try:
                subprocess.Popen(command,
                                 shell=True,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
                return True
            except:
                pass

class UtilsLogger(logging.getLoggerClass()):
    color_map = {
        "debug": 37,
        "info": 36,
        "warning": 33,
        "error": 31,
        "critical": 41
    }
    def color(self, level, message):
        color_id = self.color_map[level]
        return "\033[%dm%s\033[0m" % (color_id, message)

    def __init__(self):

        self.root.setLevel(logging.INFO)
        self.root.handlers = []

        handler = logging.StreamHandler()
        self.root.addHandler(handler)

    def debug(self, message):
        self.root.info(self.color("debug", message))

    def info(self, message):
        self.root.info(self.color("info", message))

    def warning(self, message):
        self.root.info(self.color("warning", message))

    def error(self, message):
        self.root.info(self.color("error", message))

    def critical(self, message):
        self.root.info(self.color("critical", message))

