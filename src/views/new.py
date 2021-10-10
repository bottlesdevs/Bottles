# new.py
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
from gettext import gettext as _
from gi.repository import Gtk, GLib, Handy
from ..backend.runner import Runner


class EnvironmentRow(Handy.ActionRow):
    def __init__(self, environment, **kwargs):
        super().__init__(**kwargs)

        self.environment = environment
        self.set_selectable(True)
        self.set_title(environment.get("name"))
        self.set_subtitle(self.environment.get('description'))
        self.set_icon_name(environment.get("icon"))
        self.set_visible(True)

    def get_env_id(self):
        return self.environment.get("id")


@Gtk.Template(resource_path='/com/usebottles/bottles/new.ui')
class NewView(Handy.Window):
    __gtype_name__ = 'NewView'

    # region Widgets
    stack_create = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    btn_pref_runners = Gtk.Template.Child()
    btn_pref_dxvk = Gtk.Template.Child()
    list_envs = Gtk.Template.Child()
    page_create = Gtk.Template.Child()
    page_creating = Gtk.Template.Child()
    page_created = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    switch_versioning = Gtk.Template.Child()
    label_advanced = Gtk.Template.Child()
    label_output = Gtk.Template.Child()
    box_advanced = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    combo_dxvk = Gtk.Template.Child()
    combo_arch = Gtk.Template.Child()
    revealer_advanced = Gtk.Template.Child()
    # endregion

    environments = [
        {
            "id": "Gaming",
            "name": _("Gaming"),
            "description": _("An environment improved for Windows games."),
            "icon": "applications-games-symbolic"
        },
        {
            "id": "Software",
            "name": _("Software"),
            "description": _("An environment improved for Windows software."),
            "icon": "applications-engineering-symbolic"
        },
        {
            "id": "Custom",
            "name": _("Custom"),
            "description": _("A clear environment for your experiments."),
            "icon": "applications-science-symbolic"
        }
    ]

    def __init__(self, window, arg_exe=None, arg_lnk=None, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.arg_exe = arg_exe
        self.arg_lnk = arg_lnk
        self.selected_env = "gaming"
        self.new_bottle_config = {}

        # connect signals
        self.btn_cancel.connect('pressed', self.__close_window)
        self.btn_close.connect('pressed', self.__close_window)
        self.btn_create.connect('pressed', self.create_bottle)
        self.list_envs.connect('row-selected', self.set_active_env)
        self.entry_name.connect('key-release-event', self.check_entry_name)
        self.btn_pref_runners.connect('pressed', self.window.show_prefs_view)
        self.btn_pref_dxvk.connect('pressed', self.window.show_prefs_view)

        for env in self.environments:
            env_row = EnvironmentRow(env)
            self.list_envs.add(env_row)

        # set the first environment as active
        self.list_envs.select_row(self.list_envs.get_children()[0])

        # populate combo_runner with runner versions from the manager
        for runner in self.manager.runners_available:
            self.combo_runner.append(runner, runner)

        self.combo_runner.set_active(0)

        # populate combo_dxvk with dxvk versions from the manager
        for dxvk in self.manager.dxvk_available:
            self.combo_dxvk.append(dxvk, dxvk)

        self.combo_dxvk.set_active(0)
        self.combo_arch.set_active_id("win64")

    def set_active_env(self, widget, row):
        '''
        This function set the active environment on row selection.
        If the environment is "Custom" it will display the advanced
        options.
        '''
        self.selected_env = row.get_env_id()

        status = row.get_env_id() == "Custom"
        if status:
            self.revealer_advanced.set_transition_type(
                Gtk.RevealerTransitionType.SLIDE_DOWN
            )
        else:
            self.revealer_advanced.set_transition_type(
                Gtk.RevealerTransitionType.SLIDE_UP
            )
        self.revealer_advanced.set_reveal_child(status)

    def check_entry_name(self, widget, event_key):
        '''
        This function checks if the name of the bottle is valid. So it
        checks if the name is not empty and if it contains special
        characters. Then it toggle the entry icon according to the result.
        '''
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:.;,\'"]')
        name = widget.get_text()

        if(regex.search(name) is None) and name != "":
            self.btn_create.set_visible(True)
            widget.set_icon_from_icon_name(1, "")
        else:
            self.btn_create.set_visible(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")

    '''Create the bottle'''

    def create_bottle(self, widget):
        # set widgets states
        self.btn_cancel.set_sensitive(False)
        self.btn_create.set_visible(False)
        self.page_create.set_visible(False)
        self.stack_create.set_visible_child_name("page_creating")

        '''
        Check if versioning is enabled and get the selected runner. If the
        selected environment is not "Custom", the runner is taken from the
        runners available list, else it is taken from the user selection.
        '''
        versioning_state = self.switch_versioning.get_state()
        if self.selected_env == "Custom":
            runner = self.combo_runner.get_active_id()
        else:
            rv = [
                i for i in self.manager.runners_available if i.startswith('vaniglia')
            ]
            rl = [
                i for i in self.manager.runners_available if i.startswith('lutris')
            ]
            rs = [
                i for i in self.manager.runners_available if i.startswith('sys-')
            ]

            if len(rv) > 0:  # use the latest from vaniglia
                runner = rv[0]
            elif len(rl) > 0:  # use the latest from lutris
                runner = rl[0]
            elif len(rs) > 0:  # use the latest from system
                runner = rs[0]
            else:  # use any other runner available
                runner = self.manager.runners_available[0]

        self.manager.create_bottle(
            name=self.entry_name.get_text(),
            path="",
            environment=self.selected_env,
            runner=runner,
            dxvk=self.combo_dxvk.get_active_id(),
            versioning=versioning_state,
            dialog=self,
            arch=self.combo_arch.get_active_id()
        )

    def idle_update_output(self, text):
        '''
        This function update the label_output with the givven text.
        It will be concatenated with the previous one.
        '''
        current_text = self.label_output.get_text()
        text = f"{current_text}{text}\n"
        self.label_output.set_text(text)

    def update_output(self, text):
        GLib.idle_add(self.idle_update_output, text)

    def finish(self, config):
        self.new_bottle_config = config
        self.page_created.set_description(
            _("A bottle named “{0}” was created successfully").format(
                self.entry_name.get_text()
            )
        )

        self.btn_cancel.set_visible(False)
        self.btn_close.set_visible(True)

        self.stack_create.set_visible_child_name("page_created")

        '''
        Ask the manager to check for new bottles, then update the
        user bottles list. 
        '''
        self.manager.check_bottles()
        self.window.page_list.update_bottles()

    def __close_window(self, widget):
        '''
        This function check if an executable was passed to Bottles as
        a command line argument. If so, it will be launched in the new
        bottles and will close the bottle creation dialog. If there is
        no arguments, it will simply close the dialog.
        '''
        if self.arg_exe:
            Runner().run_executable(
                config=self.new_bottle_config,
                file_path=self.arg_exe
            )

        if self.arg_lnk is not None:
            Runner().run_lnk(
                config=self.new_bottle_config,
                file_path=self.arg_lnk
            )

        self.destroy()
