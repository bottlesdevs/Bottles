# logger.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import logging
import os
import re

from bottles.backend.globals import Paths
from bottles.backend.managers.journal import JournalManager, JournalSeverity

# Set default logging level
logging.basicConfig(level=logging.DEBUG)


class Logger(logging.getLoggerClass()):
    """
    This class is a wrapper for the logging module. It provides
    custom formats for the log messages.
    """
    __color_map = {
        "debug": 37,
        "info": 36,
        "warning": 33,
        "error": 31,
        "critical": 41
    }
    __format_log = {
        'fmt': '\033[80m%(asctime)s \033[1m(%(levelname)s)\033[0m %(message)s \033[0m',
        'datefmt': '%H:%M:%S',
    }

    def __color(self, level, message: str):
        if message and "\n" in message:
            message = message.replace("\n", "\n\t") + "\n"
        color_id = self.__color_map[level]
        return "\033[%dm%s\033[0m" % (color_id, message)

    def __init__(self, formatter=None):
        if formatter is None:
            formatter = self.__format_log
        formatter = logging.Formatter(**formatter)

        self.root.setLevel(os.environ.get("LOG_LEVEL") or logging.INFO)
        self.root.handlers = []

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.root.addHandler(handler)

    def debug(self, message, **kwargs):
        self.root.debug(self.__color("debug", message), )

    def info(self, message, jn=False, **kwargs):
        self.root.info(self.__color("info", message), )
        if jn:
            JournalManager.write(JournalSeverity.INFO, message)

    def warning(self, message, jn=True, **kwargs):
        self.root.warning(self.__color("warning", message), )
        if jn:
            JournalManager.write(JournalSeverity.WARNING, message)

    def error(self, message, jn=True, **kwargs):
        self.root.error(self.__color("error", message), )
        if jn:
            JournalManager.write(JournalSeverity.ERROR, message)

    def critical(self, message, jn=True, **kwargs):
        self.root.critical(self.__color("critical", message), )
        if jn:
            JournalManager.write(JournalSeverity.CRITICAL, message)

    @staticmethod
    def write_log(data: list):
        """
        Writes a crash.log file. It finds and replace the user's home directory
        with "USER" as a proposed standard for crash reports.
        """
        log_path = f"{Paths.xdg_data_home}/bottles/crash.log"

        with open(log_path, "w") as crash_log:
            for d in data:
                # replace username with "USER" as standard
                if "/home/" in d:
                    d = re.sub(r"/home/([^/]*)/", r"/home/USER/", d)

                crash_log.write(d)

        # we write the same to the journal for convenience
        JournalManager.write(
            severity=JournalSeverity.CRASH,
            message="A crash has been detected."
        )

    def set_silent(self):
        self.root.handlers = []
