# executesettings.py
#
# Copyright 2022 Bottles Developers
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


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-execute-settings.ui')
class ExecuteSettingsDialog(Adw.Window):
    __gtype_name__ = 'ExecuteSettingsDialog'

    # region Widgets
    btn_done = Gtk.Template.Child()
    entry_args = Gtk.Template.Child()
    switch_terminal = Gtk.Template.Child()
    # endregion

    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent.window)

        # common variables and references
        self.parent = parent

        # connect signals
        self.btn_done.connect("clicked", self.__done)

        # set the entry text to current session arguments
        if self.parent.config.get("session_arguments") != None:
            self.entry_args.set_text(self.parent.config.get("session_arguments"))

        if self.parent.config.get("run_in_terminal"):
            self.switch_terminal.activate()

    def __done(self, widget):
        args = self.entry_args.get_text()
        self.parent.config["session_arguments"] = args
        # self.parent.run_executable(False, args)
        self.parent.config["run_in_terminal"] = self.switch_terminal.get_state()
        self.close()
