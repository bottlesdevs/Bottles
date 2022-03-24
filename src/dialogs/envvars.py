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
from gi.repository import Gtk, GLib, Handy


@Gtk.Template(resource_path='/com/usebottles/bottles/env-var-entry.ui')
class EnvVarEntry(Handy.ActionRow):
    __gtype_name__ = 'EnvVarEntry'

    # region Widgets
    btn_remove = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    entry_value = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, env, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.env = env

        '''
        Set the env var name as ActionRow title and set the
        entry_value to its value
        '''
        self.set_title(self.env[0])
        self.entry_value.set_text(self.env[1])

        # connect signals
        self.btn_remove.connect("clicked", self.__remove)
        self.btn_save.connect("clicked", self.__save)
        self.entry_value.connect('key-release-event', self.on_change)

    def on_change(self, widget, event):
        self.btn_save.set_visible(True)

    def __save(self, widget):
        """
        Change the env var value according to the
        user input and update the bottle configuration
        """
        env_value = self.entry_value.get_text()
        self.manager.update_config(
            config=self.config,
            key=self.env[0],
            value=env_value,
            scope="Environment_Variables"
        )

    def __remove(self, widget):
        """
        Remove the env var from the bottle configuration and
        destroy the widget
        """
        self.manager.update_config(
            config=self.config,
            key=self.env[0],
            value=False,
            remove=True,
            scope="Environment_Variables"
        )
        self.destroy()


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-env-vars.ui')
class EnvVarsDialog(Handy.Window):
    __gtype_name__ = 'EnvVarsDialog'

    # region Widgets
    entry_name = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    list_vars = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        self.__populate_vars_list()

        # connect signals
        self.btn_save.connect("clicked", self.__save_var)
        self.entry_name.connect('key-release-event', self.__validate)

    def __validate(self, widget, event_key):
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:.;,\'"]')
        name = widget.get_text()

        if (regex.search(name) is None) and name != "":
            self.btn_save.set_sensitive(True)
            widget.set_icon_from_icon_name(1, "")
        else:
            self.btn_save.set_sensitive(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")

    def __idle_save_var(self, widget=False):
        """
        This function save the new env var to the
        bottle configuration
        """
        env_name = self.entry_name.get_text()

        self.manager.update_config(
            config=self.config,
            key=env_name,
            value="",
            scope="Environment_Variables"
        )

        self.list_vars.add(
            EnvVarEntry(
                window=self.window,
                config=self.config,
                env=[env_name, ""]
            )
        )

        self.entry_name.set_text("")
        self.btn_save.set_sensitive(False)

    def __save_var(self, widget=False):
        GLib.idle_add(self.__idle_save_var)

    def __idle_populate_vars_list(self):
        """
        This function populate the list of env vars
        with the existing ones from the bottle configuration
        """
        for env in self.config.get("Environment_Variables").items():
            self.list_vars.add(
                EnvVarEntry(
                    window=self.window,
                    config=self.config,
                    env=env
                )
            )

    def __populate_vars_list(self):
        GLib.idle_add(self.__idle_populate_vars_list)
