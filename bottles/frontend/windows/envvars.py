# envvars.py
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

from gi.repository import Gtk, GLib, Adw

from bottles.frontend.utils.gtk import GtkUtils


@Gtk.Template(resource_path='/com/usebottles/bottles/env-var-entry.ui')
class EnvVarEntry(Adw.EntryRow):
    __gtype_name__ = 'EnvVarEntry'

    # region Widgets
    btn_remove = Gtk.Template.Child()
    # endregion

    def __init__(self, parent, env, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.parent = parent
        self.manager = parent.window.manager
        self.config = parent.config
        self.env = env

        self.set_title(self.env[0])
        self.set_text(self.env[1])

        # connect signals
        self.connect("apply", self.__save)
        self.btn_remove.connect("clicked", self.__remove)

    def __save(self, *_args):
        """
        Change the env var value according to the
        user input and update the bottle configuration
        """
        self.manager.update_config(
            config=self.config,
            key=self.env[0],
            value=self.get_text(),
            scope="Environment_Variables"
        )

    def __remove(self, *_args):
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
        self.parent.group_vars.remove(self)


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-env-vars.ui')
class EnvVarsDialog(Adw.Window):
    __gtype_name__ = 'EnvVarsDialog'

    # region Widgets
    entry_name = Gtk.Template.Child()
    group_vars = Gtk.Template.Child()
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
        self.entry_name.connect("changed", self.__validate)
        self.entry_name.connect("apply", self.__save_var)

    def __validate(self, *_args):
        self.__valid_name = GtkUtils.validate_entry(self.entry_name, lambda envvar : envvar.startswith("WINEDLLOVERRIDES"))

    def __save_var(self, *_args):
        """
        This function save the new env var to the
        bottle configuration
        """
        if not self.__valid_name:
            self.entry_name.set_text("")
            self.entry_name.remove_css_class("error")
            self.__valid_name = True
            return

        env_name = self.entry_name.get_text()
        env_value = "value"
        split_value = env_name.split('=', 1)
        if len(split_value) == 2:
            env_name = split_value[0]
            env_value = split_value[1]
        self.manager.update_config(
            config=self.config,
            key=env_name,
            value=env_value,
            scope="Environment_Variables"
        )
        _entry = EnvVarEntry(parent=self, env=[env_name, env_value])
        GLib.idle_add(self.group_vars.add, _entry)
        self.entry_name.set_text("")

    def __populate_vars_list(self):
        """
        This function populate the list of env vars
        with the existing ones from the bottle configuration
        """
        envs = self.config.Environment_Variables.items()
        if len(envs) == 0:
            self.group_vars.set_description(_("No environment variables defined."))
            return

        self.group_vars.set_description("")
        for env in envs:
            _entry = EnvVarEntry(parent=self, env=env)
            GLib.idle_add(self.group_vars.add, _entry)
