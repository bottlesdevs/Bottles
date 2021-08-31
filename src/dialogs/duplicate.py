# duplicate.py
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

import re
import time
from gi.repository import Gtk, Handy

from ..utils import RunAsync
from ..backend.backup import RunnerBackup

@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-duplicate.ui')
class DuplicateDialog(Handy.Window):
    __gtype_name__ = 'DuplicateDialog'

    # region Widgets
    entry_name = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    btn_duplicate = Gtk.Template.Child()
    stack_switcher = Gtk.Template.Child()
    progressbar = Gtk.Template.Child()
    # endregion

    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent.window)

        # common variables and references
        self.parent = parent
        self.config = parent.config

        # connect signals
        self.btn_cancel.connect('pressed', self.close_window)
        self.btn_close.connect('pressed', self.close_window)
        self.btn_duplicate.connect('pressed', self.duplicate_bottle)
        self.entry_name.connect('key-release-event', self.check_entry_name)

    '''Validate entry_name input'''
    def check_entry_name(self, widget, event_key):
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:.;,"]')
        name = widget.get_text()

        if(regex.search(name) is None) and name != "":
            self.btn_duplicate.set_sensitive(True)
            widget.set_icon_from_icon_name(1, "")
        else:
            self.btn_duplicate.set_sensitive(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")

    '''Destroy the window'''
    def close_window(self, widget=None):
        self.destroy()

    '''Run executable with args'''
    def duplicate_bottle(self, widget):
        self.stack_switcher.set_visible_child_name("page_duplicating")

        widget.set_visible(False)
        RunAsync(self.pulse, None)
        name = self.entry_name.get_text()

        RunnerBackup().duplicate_bottle(self.config, name)
        self.parent.manager.update_bottles()

        self.stack_switcher.set_visible_child_name("page_duplicated")

        self.btn_close.set_sensitive(True)
        self.btn_close.set_visible(True)
        self.btn_cancel.set_visible(False)

    '''Progressbar pulse every 1s'''
    def pulse(self):
        while True:
            time.sleep(1)
            self.progressbar.pulse()