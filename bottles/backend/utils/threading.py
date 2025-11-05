# threading.py
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

import os
import sys
import threading
import traceback
from typing import Any

from gi.repository import GLib

from bottles.backend.logger import Logger

logging = Logger()


class RunAsync(threading.Thread):
    """
    This class is used to execute a function asynchronously.
    It takes a function, a callback and a list of arguments as input.
    """

    def __init__(
        self,
        task_func,
        callback=None,
        daemon=True,
        *args: Any,
        **kwargs: Any,
    ):
        if "DEBUG_MODE" in os.environ:
            import faulthandler

            faulthandler.enable()

        logging.debug(
            f"Running async job [{task_func}] "
            f"(from main thread: {threading.current_thread() is threading.main_thread()})."
        )

        self._callback_in_main_loop = kwargs.pop("callback_in_main_loop", True)

        super(RunAsync, self).__init__(target=self.__target, args=args, kwargs=kwargs)

        self.task_func = task_func

        self.callback = callback if callback else lambda r, e: None
        self.daemon = daemon
        self.cancel_event = kwargs.get("cancel_event")
        self._cancel_requested = False

        self.start()

    def __target(self, *args, **kwargs):
        result = None
        error = None

        try:
            result = self.task_func(*args, **kwargs)
        except Exception as exception:
            logging.error(
                f"Error while running async job: {self.task_func}\n"
                f"Exception: {exception}"
            )

            error = exception
            _ex_type, _ex_value, trace = sys.exc_info()
            traceback.print_tb(trace)
            traceback_info = "\n".join(traceback.format_tb(trace))

            logging.write_log([str(exception), traceback_info])
        def _dispatch_callback():
            try:
                self.callback(result, error)
            except Exception as callback_exception:
                logging.error(
                    "Error while running async callback: "
                    f"{self.callback}\nException: {callback_exception}"
                )
                _ex_type, _ex_value, trace = sys.exc_info()
                traceback.print_tb(trace)
                traceback_info = "\n".join(traceback.format_tb(trace))
                logging.write_log([str(callback_exception), traceback_info])
            return GLib.SOURCE_REMOVE

        if self._callback_in_main_loop and threading.current_thread() is not threading.main_thread():
            GLib.idle_add(_dispatch_callback)
        else:
            _dispatch_callback()

    def cancel(self):
        self._cancel_requested = True
        if self.cancel_event and hasattr(self.cancel_event, "set"):
            self.cancel_event.set()

    @staticmethod
    def run_async(func):
        def inner(*args, **kwargs):
            # Here we add None in the arguments so that callback=None,
            # but we still pass all the required argument to the function called
            RunAsync(
                func,
                *(
                    (
                        None,
                        True,
                    )
                    + args
                ),
                **kwargs,
            )

        return inner
