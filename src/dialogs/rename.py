# rename.py
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
# pylint: disable=import-error,missing-docstring

from gi.repository import Gtk, Adw


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-rename.ui')
class RenameDialog(Adw.Window):
    __gtype_name__ = 'RenameDialog'

    # region Widgets
    entry_name = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    ev_controller = Gtk.EventControllerKey.new()

    # endregion

    def __init__(self, window, name, on_save, **kwargs):
        super().__init__(**kwargs)

        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.on_save = on_save

        # set widget defaults
        self.entry_name.set_text(name)
        self.entry_name.add_controller(self.ev_controller)

        # connect signals
        self.ev_controller.connect("key-released", self.on_change)
        self.btn_cancel.connect("clicked", self.__close_window)
        self.btn_save.connect("clicked", self.__on_save)

    def __on_save(self, *_args):
        text = self.entry_name.get_text()
        self.on_save(new_name=text)
        self.destroy()

    def __close_window(self, *_args):
        self.destroy()

    def on_change(self, *_args):
        self.btn_save.set_sensitive(len(self.entry_name.get_text()) > 0)
