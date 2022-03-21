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
import sys
import time
import threading
import traceback
import webbrowser
import urllib.request

from datetime import datetime
from gettext import gettext as _

from gi.repository import GLib

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false

logging = Logger()


class UtilsConnection:
    """
    This class is used to check the connection, pinging the official
    Bottles's website. If the connection is offline, the user will be
    notified and False will be returned, otherwise True.
    """

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        self.window = window

    def check_connection(self, show_notification=False):
        # check connection using gethostbyname, check if it hangs, then raise
        try:
            urllib.request.urlopen('https://usebottles.com/', timeout=5)
            self.window.toggle_btn_noconnection(False)

            self.last_check = datetime.now()
            self.status = True

            return True
        except urllib.error.URLError:
            logging.warning("Connection status: offline …", )
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


class RunAsync(threading.Thread):
    """
    This class is used to execute a function asynchronously.
    It take a function, a callback and a list of arguments as input.
    """

    def __init__(self, task_func, callback=None, *args, **kwargs):
        if "DEBUG_MODE" in os.environ:
            import faulthandler
            faulthandler.enable()

        self.source_id = None
        self.stop_request = threading.Event()
        assert threading.current_thread() is threading.main_thread()

        super(RunAsync, self).__init__(
            target=self.__target, args=args, kwargs=kwargs)

        self.task_func = task_func

        self.callback = callback if callback else lambda r, e: None
        self.daemon = kwargs.pop("daemon", True)

        self.start()

    def __target(self, *args, **kwargs):
        result = None
        error = None

        logging.debug(f"Running async job [{self.task_func}].", )

        try:
            result = self.task_func(*args, **kwargs)
        except Exception as exception:
            logging.error("Error while running async job: "
                          f"{self.task_func}\nException: {exception}", )

            error = exception
            _ex_type, _ex_value, trace = sys.exc_info()
            traceback.print_tb(trace)
            traceback_info = '\n'.join(traceback.format_tb(trace))

            logging.write_log([str(exception), traceback_info])
        self.source_id = GLib.idle_add(self.callback, result, error)
        return self.source_id


class GtkUtils:
    @staticmethod
    def open_doc_url(widget, page):
        webbrowser.open_new_tab(f"https://docs.usebottles.com/{page}")
