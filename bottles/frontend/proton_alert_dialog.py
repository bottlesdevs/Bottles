# proton_alert_dialog.py
#
# Copyright 2025 The Bottles Contributors
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

from gi.repository import Gtk, Adw


@Gtk.Template(resource_path="/com/usebottles/bottles/proton-alert-dialog.ui")
class ProtonAlertDialog(Adw.Window):
    __gtype_name__ = "ProtonAlertDialog"
    __resources = {}

    # region Widgets
    btn_use = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    check_confirm = Gtk.Template.Child()

    # endregion

    def __init__(self, window, callback, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        self.callback = callback

        # connect signals
        self.btn_use.connect("clicked", self.__callback, True)
        self.btn_cancel.connect("clicked", self.__callback, False)
        self.check_confirm.connect("toggled", self.__toggle_btn_use)

    def __callback(self, _, status):
        self.destroy()
        self.callback(status)
        self.close()

    def __toggle_btn_use(self, widget, *_args):
        self.btn_use.set_sensitive(widget.get_active())
