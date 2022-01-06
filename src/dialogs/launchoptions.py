# launchoptions.py
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

from gi.repository import Gtk, GLib, Handy

@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-launch-options.ui')
class LaunchOptionsDialog(Handy.Window):
    __gtype_name__ = 'LaunchOptionsDialog'

    # region Widgets
    entry_arguments = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, program_executable, arguments, **kwargs):
        super().__init__(**kwargs)

        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.program_executable = program_executable
        self.arguments = arguments

        # set widget defaults
        self.entry_arguments.set_text(self.arguments)

        # connect signals
        self.btn_cancel.connect('pressed', self.__close_window)
        self.btn_save.connect('pressed', self.__save_options)

    def __close_window(self, widget=None):
        self.destroy()

    def __save_options(self, widget):
        '''
        This function save the launch options in the bottle
        configuration. It also close the window and update the
        programs list.
        '''
        self.arguments = self.entry_arguments.get_text()
        self.config = self.manager.update_config(
            config=self.config,
            key=self.program_executable,
            value=self.arguments,
            scope="Programs"
        )
        GLib.idle_add(self.__close_window)
