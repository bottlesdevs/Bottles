# download.py
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

import time
from gettext import gettext as _
from gi.repository import Gtk, GLib

from .utils import RunAsync


@Gtk.Template(resource_path='/com/usebottles/bottles/download-entry.ui')
class DownloadEntry(Gtk.Box):
    __gtype_name__ = 'DownloadEntry'

    # region Widgets
    label_filename = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    progressbar_download = Gtk.Template.Child()
    label_download_status = Gtk.Template.Child()
    # endregion

    def __init__(self, window, file_name, cancellable=True, **kwargs):
        super().__init__(**kwargs)

        self.window = window
        self.box_downloads = window.box_downloads

        # Set btn_downloads visible
        self.window.btn_downloads.set_visible(True)

        # Populate widgets data
        self.label_filename.set_text(file_name)
        if not cancellable:
            self.btn_cancel.hide()

        # Start pulsing
        RunAsync(self.pulse, None)

    # Progressbar pulse every 1s
    def pulse(self):
        while True:
            time.sleep(1)
            self.progressbar_download.pulse()

    def idle_update_status(self,
                           count=False,
                           block_size=False,
                           total_size=False,
                           completed=False
                           ):
        if not self.label_download_status.get_visible():
            self.label_download_status.set_visible(True)

        if not completed:
            percent = int(count * block_size * 100 / total_size)
            self.label_download_status.set_text(f'{str(percent)}%')
        else:
            percent = 100

        if percent == 100:
            self.remove()

    def update_status(self,
                      count=False,
                      block_size=False,
                      total_size=False,
                      completed=False
                      ):
        GLib.idle_add(self.idle_update_status, count,
                      block_size, total_size, completed)

    def remove(self):
        downloads = self.box_downloads.get_children()
        if len(downloads) == 1:
            self.window.btn_downloads.set_visible(False)
        self.destroy()


class DownloadManager():

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        # Common variables
        self.window = window
        self.box_downloads = window.box_downloads

    def new_download(self, file_name, cancellable=True):
        download_entry = DownloadEntry(
            self.window, file_name, cancellable)
        self.window.box_downloads.add(download_entry)

        return download_entry
