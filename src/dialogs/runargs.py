# runargs.py
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

from gi.repository import Gtk, Adw


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-run-args.ui')
class RunArgsDialog(Adw.Window):
    __gtype_name__ = 'RunArgsDialog'

    # region Widgets
    entry_args = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_run = Gtk.Template.Child()

    # endregion

    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent.window)

        # common variables and references
        self.parent = parent

        # connect signals
        self.btn_cancel.connect("clicked", self.__close_window)
        self.btn_run.connect("clicked", self.__run_executable)

    def __run_executable(self, widget):
        """
        This function return the user to the executable selection with
        the new typed arguments, then close the window.
        """
        args = self.entry_args.get_text()
        self.parent.run_executable(False, args)
        self.__close_window()

    def __close_window(self, widget=None):
        self.window.remove(self)
