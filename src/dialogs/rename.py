# rename.py
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

from gi.repository import Gtk


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-rename.ui')
class RenameDialog(Gtk.Window):
    __gtype_name__ = 'RenameDialog'

    # region Widgets
    entry = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()

    # endregion

    def __init__(self, window, name, on_save, **kwargs):
        super().__init__(**kwargs)

        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.on_save = on_save

        # set widget defaults
        self.entry.set_text(name)

        # connect signals
        self.btn_cancel.connect("clicked", self.__close_window)
        self.btn_save.connect("clicked", self.__on_save)

    def __on_save(self, widget):
        text = self.entry.get_text()
        self.on_save(new_name=text)
        self.destroy()

    def __close_window(self, widget):
        self.destroy()
