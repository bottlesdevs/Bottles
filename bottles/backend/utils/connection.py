# connection.py
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
from datetime import datetime
from gettext import gettext as _
from typing import Optional

import pycurl

from bottles.backend.logger import Logger
from bottles.backend.models.result import Result
from bottles.backend.state import State, Signals, Notification

logging = Logger()


class ConnectionUtils:
    """
    This class is used to check the connection, pinging the official
    Bottle's website. If the connection is offline, the user will be
    notified and False will be returned, otherwise True.
    """
    _status: Optional[bool] = None
    last_check = None

    def __init__(self, force_offline=False, **kwargs):
        super().__init__(**kwargs)
        self.force_offline = force_offline

    @property
    def status(self) -> Optional[bool]:
        return self._status

    @status.setter
    def status(self, value: bool):
        if self._status is None:
            logging.error("Cannot set network status to None")
            return
        self._status = value
        State.send_signal(Signals.NetworkReady, Result(status=self.status))

    def check_connection(self, show_notification=False) -> bool:
        """check network status, send result through signal NetworkReady and return"""
        if self.force_offline or "FORCE_OFFLINE" in os.environ:
            logging.info("Forcing offline mode")
            self.status = False
            return False

        try:
            c = pycurl.Curl()
            c.setopt(c.URL, 'https://ping.usebottles.com')
            c.setopt(c.FOLLOWLOCATION, True)
            c.setopt(c.NOBODY, True)
            c.perform()

            if c.getinfo(pycurl.HTTP_CODE) != 200:
                raise Exception("Connection status: offline …")

            self.last_check = datetime.now()
            self.status = True
        except Exception:
            logging.warning("Connection status: offline …")
            if show_notification:
                State.send_signal(Signals.Notification, Result(True, Notification(
                    title="Bottles",
                    text=_("You are offline, unable to download."),
                    image="network-wireless-disabled-symbolic"
                )))
            self.last_check = datetime.now()
            self.status = False
        finally:
            return self.status
