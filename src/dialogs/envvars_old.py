# envvars.py
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
import shlex
from gi.repository import Gtk, Handy


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-environment-variables.ui')
class EnvVarsDialog(Handy.Window):
    __gtype_name__ = 'EnvVarsDialog'

    # region Widgets
    entry_variables = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        variables = config["Parameters"]["environment_variables"]

        # set the default values
        self.entry_variables.set_text(variables)

        # connect signals
        self.entry_variables.connect('key-release-event', self.__check_entries)
        self.btn_cancel.connect("clicked", self.__close_window)
        self.btn_save.connect("clicked", self.__save_variables)

    def __check_entries(self, widget, event_key):
        """
        This function checks if entries in entry_variables are valid, by
        splitting the content by space and "=". If it raises an exception,
        the warning symbolic icon will be shown and the save button will be
        disabled preventing the user to save the invalid entries.
        """
        entries = widget.get_text()
        try:
            entries = shlex.split(entries)

            for e in entries:
                kv = e.split("=")

                if len(kv) > 2:
                    kv[1] = "=".join(kv[1:])
                    kv = kv[:2]

                if len(kv) != 2:
                    raise Exception
        except:
            self.btn_save.set_sensitive(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")
            return

        self.btn_save.set_sensitive(True)
        widget.set_icon_from_icon_name(1, "")

    def __close_window(self, widget):
        self.destroy()

    def __save_variables(self, widget):
        """
        This function take the new variables from the entry
        and save them to the bottle configuration. It will also
        close the window.
        """
        variables = self.entry_variables.get_text()
        self.manager.update_config(
            config=self.config,
            key="environment_variables",
            value=variables,
            scope="Parameters"
        )
        self.__close_window(widget)
