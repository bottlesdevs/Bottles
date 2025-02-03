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

import logging


class RunAsync(threading.Thread):
    """
    This class is used to execute a function asynchronously.
    It takes a function, a callback and a list of arguments as input.
    """

    def __init__(
        self, task_func, callback=None, daemon=True, *args: Any, **kwargs: Any
    ):
        if "DEBUG_MODE" in os.environ:
            import faulthandler

            faulthandler.enable()

        logging.debug(
            f"Running async job [{task_func}] "
            f"(from main thread: {threading.current_thread() is threading.main_thread()})."
        )

        super().__init__(target=self.__target, args=args, kwargs=kwargs)

        self.task_func = task_func

        self.callback = callback if callback else lambda r, e: None
        self.daemon = daemon

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
        self.callback(result, error)

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
