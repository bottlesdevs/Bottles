# connection.py
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

import urllib.request

from datetime import datetime
from gettext import gettext as _

from bottles.backend.logger import Logger  # pyright: reportMissingImports=false

logging = Logger()


class ConnectionUtils:
    """
    This class is used to check the connection, pinging the official
    Bottles's website. If the connection is offline, the user will be
    notified and False will be returned, otherwise True.
    """
    status = None
    last_check = None

    def __init__(self, window=None, **kwargs):
        super().__init__(**kwargs)
        self.window = window

    def check_connection(self, show_notification=False):
        # check connection using gethostbyname, check if it hangs, then raise
        try:
            urllib.request.urlopen('https://usebottles.com/', timeout=5)
            if self.window is not None:
                self.window.toggle_btn_noconnection(False)

            self.last_check = datetime.now()
            self.status = True

            return True
        except urllib.error.URLError:
            logging.warning("Connection status: offline …", )
            if self.window is not None:
                self.window.toggle_btn_noconnection(True)

            if show_notification and self.window is not None:
                self.window.send_notification(
                    title="Bottles",
                    text=_("You are offline, unable to download."),
                    image="network-wireless-disabled-symbolic"
                )
            self.last_check = datetime.now()
            self.status = False

        return False
