# notifications.py
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

import yaml
import urllib.request
from functools import lru_cache
from datetime import datetime, timedelta

from bottles.params import VERSION  # pyright: reportMissingImports=false
from bottles.backend.globals import API
from bottles.backend.managers.data import DataManager


class NotificationsManager:
    """
    The NotificationsManager class is used to fetch and manage
    the notifications from the repository.
    """

    messages = []
    data = DataManager()

    def __init__(self):
        self.__get_messages()

    @lru_cache
    def __get_messages(self):
        _messages = []
        notifications = self.data.list().get("notifications")
        notifications = [notifications] if isinstance(notifications, int) else notifications

        try:
            with urllib.request.urlopen(API.notifications) as url:
                res = url.read().decode('utf-8')
                _messages = yaml.safe_load(res)
        except (urllib.error.HTTPError, urllib.error.URLError):
            _messages = []

        for message in _messages.items():
            message = message[1]
            _date = message.get("date")
            _date = datetime(_date.year, _date.month, _date.day)

            if _date < datetime.today() - timedelta(days=1) \
                    and not message.get("recurrent"):
                continue

            if message.get("id") in notifications:
                continue

            if message.get("before") and message.get("before") == VERSION:
                continue

            self.messages.append(message)

    def mark_as_read(self, nid):
        """Mark a notification as read."""
        for message in self.messages:
            if message.get("id") == nid:
                message["read"] = True
                self.data.set("notifications", nid, of_type=list)
                break
