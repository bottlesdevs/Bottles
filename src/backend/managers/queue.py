# queue.py
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


from gi.repository import GLib


class QueueManager:
    __queue = 0

    def __init__(self, end_fn, add_fn=None):
        self.__add_fn = add_fn
        self.__end_fn = end_fn

    def add_task(self):
        self.__queue += 1
        if self.__add_fn and self.__queue == 1:
            GLib.idle_add(self.__add_fn)

    def end_task(self):
        self.__queue -= 1
        if self.__queue <= 0:
            GLib.idle_add(self.__end_fn)
