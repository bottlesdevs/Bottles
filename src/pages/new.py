# add.py
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

from gi.repository import Gtk, Handy

@Gtk.Template(resource_path='/com/usebottles/bottles/environment-entry.ui')
class BottlesEnvironmentEntry(Handy.ActionRow):
    __gtype_name__ = 'BottlesEnvironmentEntry'

    def __init__(self, environment, **kwargs):
        super().__init__(**kwargs)

        '''Init template'''
        self.init_template()

        '''Common variables'''
        self.environment = environment

        '''Populate'''
        self.set_title(environment.get("name"))
        self.set_subtitle(environment.get("description"))
        self.set_icon_name(environment.get("icon"))
        self.set_visible(True)

    def get_environment_id(self):
        return self.environment.get("id")

@Gtk.Template(resource_path='/com/usebottles/bottles/new.ui')
class BottlesNew(Handy.Window):
    __gtype_name__ = 'BottlesNew'

    '''Get widgets from template'''
    btn_create = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    list_environments = Gtk.Template.Child()

    environments = [
        {
            "id": "gaming",
            "name": _("Gaming"),
            "description": _("An environment improved for Windows games."),
            "icon": "applications-games-symbolic"
        },
        {
            "id": "software",
            "name": _("Software"),
            "description": _("An environment for Windows software."),
            "icon": "applications-engineering-symbolic"
        },
        {
            "id": "custom",
            "name": _("Custom"),
            "description": _("A clear environment for your experiments."),
            "icon": "applications-science-symbolic"
        }
    ]

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        '''Init template'''
        self.init_template()

        '''Signal connections'''
        self.btn_cancel.connect('pressed', self.close_window)
        self.list_environments.connect('row-selected', self.set_active_environment)

        for environment in self.environments:
            env_row = BottlesEnvironmentEntry(environment)
            self.list_environments.add(env_row)

    def set_active_environment(self, widget, row):
        print(row.get_environment_id())

    def close_window(self, widget):
        self.destroy()
