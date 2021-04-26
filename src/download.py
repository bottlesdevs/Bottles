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

from gi.repository import Gtk, GLib

import time

from .utils import RunAsync

@Gtk.Template(resource_path='/com/usebottles/bottles/download-entry.ui')
class BottlesDownloadEntry(Gtk.Box):
    __gtype_name__ = 'BottlesDownloadEntry'

    '''Get widgets from template'''
    label_filename = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    progressbar_download = Gtk.Template.Child()
    label_download_status = Gtk.Template.Child()

    def __init__(self, file_name, stoppable=True, **kwargs):
        super().__init__(**kwargs)

        '''Init template'''
        try:
            self.init_template()
        except TypeError:
            self.init_template("")

        '''Populate widgets data'''
        self.label_filename.set_text(file_name)
        if not stoppable: self.btn_cancel.hide()

        '''Start pulsing'''
        RunAsync(self.pulse, None)

    '''Progressbar pulse every 1s'''
    def pulse(self):
        while True:
            time.sleep(1)
            self.progressbar_download.pulse()

    def idle_update_status(self, count=False, block_size=False, total_size=False, completed=False):
        if not self.label_download_status.get_visible():
            self.label_download_status.set_visible(True)

        if not completed:
            percent = int(count * block_size * 100 / total_size)
            self.label_download_status.set_text(f'{str(percent)}%')
        else:
            percent = 100

        if percent == 100:
            self.remove()

    def update_status(self, count=False, block_size=False, total_size=False, completed=False):
        GLib.idle_add(self.idle_update_status, count, block_size, total_size, completed)

    def remove(self):
        self.destroy()

class DownloadManager():

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.window = window
        self.box_downloads = window.box_downloads
        self.pop_downloads = window.pop_downloads

    def new_download(self, file_name, stoppable=True):
        download_entry = BottlesDownloadEntry(file_name, stoppable)
        self.window.box_downloads.add(download_entry)

        GLib.idle_add(self.pop_downloads.popup)

        return download_entry
