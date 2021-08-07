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
import time

from gi.repository import Gtk, GLib, Handy

class BottlesEnvironmentRow(Handy.ActionRow):
    def __init__(self, environment, **kwargs):
        super().__init__(**kwargs)

        self.environment = environment
        self.set_selectable(True)
        self.set_title(environment.get("name"))
        self.set_subtitle(self.environment.get('description'))
        self.set_icon_name(environment.get("icon"))
        self.set_visible(True)

    def get_environment_id(self):
        return self.environment.get("id")

@Gtk.Template(resource_path='/com/usebottles/bottles/new.ui')
class BottlesNew(Handy.Window):
    __gtype_name__ = 'BottlesNew'

    '''Get widgets from template'''
    stack_create = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    btn_pref_runners = Gtk.Template.Child()
    btn_pref_dxvk = Gtk.Template.Child()
    list_environments = Gtk.Template.Child()
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
    progressbar_creating = Gtk.Template.Child()

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

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.selected_environment = "gaming"

        '''Signal connections'''
        self.btn_cancel.connect('pressed', self.close_window)
        self.btn_close.connect('pressed', self.close_window)
        self.btn_create.connect('pressed', self.create_bottle)
        self.list_environments.connect('row-selected', self.set_active_environment)
        self.entry_name.connect('key-release-event', self.check_entry_name)
        self.btn_pref_runners.connect('pressed', self.window.show_preferences_view)
        self.btn_pref_dxvk.connect('pressed', self.window.show_preferences_view)

        for environment in self.environments:
            env_row = BottlesEnvironmentRow(environment)
            self.list_environments.add(env_row)

        '''Select the first environment in list'''
        self.list_environments.select_row(
            self.list_environments.get_children()[0])

        '''Populate combo_runner'''
        for runner in self.runner.runners_available:
            self.combo_runner.append(runner, runner)

        self.combo_runner.set_active(0)

        '''Populate combo_dxvk'''
        for dxvk in self.runner.dxvk_available:
            self.combo_dxvk.append(dxvk, dxvk)

        self.combo_dxvk.set_active(0)
        self.combo_arch.set_active_id("win64")

    def set_active_environment(self, widget, row):
        '''Set selected environment'''
        self.selected_environment = row.get_environment_id()

        '''Toggle advanced options'''
        status = row.get_environment_id() == "Custom"
        for w in [self.label_advanced, self.box_advanced]:
            w.set_visible(status)
            w.set_visible(status)

    '''Validate entry_name input'''
    def check_entry_name(self, widget, event_key):
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:.;,]')
        name = widget.get_text()

        if(regex.search(name) is None) and name != "":
            self.btn_create.set_visible(True)
            widget.set_icon_from_icon_name(1, "")
        else:
            self.btn_create.set_visible(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")

    '''Create the bottle'''
    def create_bottle(self, widget):
        '''Change buttons state'''
        self.btn_cancel.set_sensitive(False)
        self.btn_create.set_visible(False)
        self.page_create.set_visible(False)

        '''Show the creating page'''
        self.stack_create.set_visible_child_name("page_creating")

        '''Create bottle'''
        versioning_state = self.switch_versioning.get_state()
        if self.selected_environment == "Custom":
            runner = self.combo_runner.get_active_id()
        else:
            rv = [i for i in self.runner.runners_available if i.startswith('vaniglia')]
            rl = [i for i in self.runner.runners_available if i.startswith('lutris')]
            rs = [i for i in self.runner.runners_available if i.startswith('sys-')]

            if len(rv) > 0: # use the latest from vaniglia
                runner = rv[0]
            elif len(rl) > 0: # use the latest from lutris
                runner = rl[0]
            elif len(rs) > 0: # use the latest from system
                runner = rs[0]
            else: # use any other runner available
                runner = self.runner.runners_available[0]

        self.runner.create_bottle(name=self.entry_name.get_text(),
                                  path="",
                                  environment=self.selected_environment,
                                  runner=runner,
                                  dxvk=self.combo_dxvk.get_active_id(),
                                  versioning=versioning_state,
                                  dialog=self,
                                  arch=self.combo_arch.get_active_id())

    '''Concatenate label_output'''
    def idle_update_output(self, text):
        current_text = self.label_output.get_text()
        text = f"{current_text}{text}\n"
        self.label_output.set_text(text)

    def update_output(self, text):
        GLib.idle_add(self.idle_update_output, text)

    def finish(self):
        self.page_created.set_description(
            _("A bottle named “%s” was created successfully") % self.entry_name.get_text())

        self.btn_cancel.set_visible(False)
        self.btn_close.set_visible(True)

        self.stack_create.set_visible_child_name("page_created")

        '''Update bottles'''
        self.runner.check_bottles()
        self.window.page_list.update_bottles()

    '''Progressbar pulse every 1s'''
    def pulse(self):
        while True:
            time.sleep(1)
            self.progressbar_creating.pulse()

    '''Destroy the window'''
    def close_window(self, widget):
        self.destroy()
