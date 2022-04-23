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

import os
from gi.repository import Gtk, GLib, Handy


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-launch-options.ui')
class LaunchOptionsDialog(Handy.Window):
    __gtype_name__ = 'LaunchOptionsDialog'

    # region Widgets
    entry_arguments = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    btn_script = Gtk.Template.Child()
    btn_script_reset = Gtk.Template.Child()
    flatpak_warn = Gtk.Template.Child()
    action_script = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, program, **kwargs):
        super().__init__(**kwargs)

        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.program = program

        # set widget defaults
        self.entry_arguments.set_text(program.get("arguments", ""))
        if "FLATPAK_ID" in os.environ:
            self.flatpak_warn.set_visible(True)

        # connect signals
        self.btn_cancel.connect("clicked", self.__close_window)
        self.btn_save.connect("clicked", self.__save_options)
        self.btn_script.connect("clicked", self.__choose_script)
        self.btn_script_reset.connect("clicked", self.__choose_script, True)
        self.entry_arguments.connect("activate", self.__save_options)

    def __close_window(self, widget=None):
        self.destroy()

    def __save_options(self, widget):
        """
        This function save the launch options in the bottle
        configuration. It also close the window and update the
        programs list.
        """
        self.program["arguments"] = self.entry_arguments.get_text()
        self.config = self.manager.update_config(
            config=self.config,
            key=self.program["executable"],
            value=self.program,
            scope="External_Programs"
        )
        GLib.idle_add(self.__close_window)

    def __choose_script(self, widget, reset=False):
        """
        This function open a file chooser dialog to choose the
        script which will be executed before the program.
        """
        path = ""
        if not reset:
            file_dialog = Gtk.FileChooserNative.new(
                _("Choose the script"),
                self.window,
                Gtk.FileChooserAction.OPEN,
                _("Run"),
                _("Cancel")
            )
            response = file_dialog.run()
            if response == -3:
                path = file_dialog.get_filename()
                self.program["script"] = path

            file_dialog.destroy()

        if path != "":
            self.action_script.set_subtitle(path)
        else:
            self.action_script.set_subtitle(_("Choose a script which should be executed after run."))
