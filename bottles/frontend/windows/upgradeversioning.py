# duplicate.py
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

import time
from gi.repository import Gtk, Adw

from bottles.backend.utils.threading import RunAsync


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-upgrade-versioning.ui")
class UpgradeVersioningDialog(Adw.Window):
    __gtype_name__ = "UpgradeVersioningDialog"

    # region Widgets
    btn_cancel = Gtk.Template.Child()
    btn_proceed = Gtk.Template.Child()
    btn_upgrade = Gtk.Template.Child()
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
        self.btn_upgrade.connect("clicked", self.__upgrade)
        self.btn_proceed.connect("clicked", self.__proceed)

    def __upgrade(self, widget):
        """
        This function take the new bottle name from the entry
        and create a new duplicate of the bottle. It also change the
        stack_switcher page when the process is finished.
        """
        self.stack_switcher.set_visible_child_name("page_upgrading")
        self.btn_upgrade.set_visible(False)
        self.btn_cancel.set_visible(False)
        self.btn_cancel.set_label("Close")

        RunAsync(self.pulse)
        RunAsync(
            self.parent.manager.versioning_manager.update_system,
            self.finish,
            self.config,
        )

    def __proceed(self, widget):
        self.stack_switcher.set_visible_child_name("page_info")
        self.btn_proceed.set_visible(False)
        self.btn_upgrade.set_visible(True)

    def finish(self, result, error=False):
        self.btn_cancel.set_visible(True)
        self.parent.manager.update_bottles()
        self.stack_switcher.set_visible_child_name("page_finish")

    def pulse(self):
        # This function update the progress bar every half second.
        while True:
            time.sleep(0.5)
            self.progressbar.pulse()
