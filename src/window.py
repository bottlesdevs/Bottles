# window.py
#
# Copyright 2020 mirkobrombin
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

from gi.repository import Gtk, Gio
from .params import *
from .pages.add import BottlesAdd, BottlesAddDetails
from .pages.details import BottlesDetails
from .pages.list import BottlesList

@Gtk.Template(resource_path='/pm/mirko/bottles/window.ui')
class BottlesWindow(Gtk.ApplicationWindow):
    __gtype_name__ = 'BottlesWindow'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    grid_main = Gtk.Template.Child()
    stack_main = Gtk.Template.Child()
    btn_add = Gtk.Template.Child()
    btn_list = Gtk.Template.Child()
    btn_preferences = Gtk.Template.Child()
    switch_dark = Gtk.Template.Child()

    '''
    Common variables
    '''
    default_settings = Gtk.Settings.get_default()
    settings = Gio.Settings.new("pm.mirko.bottles")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()
        self.default_settings.set_property("gtk-application-prefer-dark-theme", THEME_DARK)

        '''
        Get and assign pages to variable
        '''
        page_add = BottlesAdd(self)
        page_add_details = BottlesAddDetails(self)
        page_details = BottlesDetails()
        page_list = BottlesList(self)

        '''
        Add pages to stack and set options
        '''
        self.stack_main.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack_main.set_transition_duration(ANIM_DURATION)
        self.stack_main.add_titled(page_add, "page_add", "New Bottle")
        self.stack_main.add_titled(page_add_details, "page_add_details", "New Bottle details")
        self.stack_main.add_titled(page_details, "page_details", "Bottle details")
        self.stack_main.add_titled(page_list, "page_list", "Bottles")

        '''
        Add widgets to main grid
        '''
        self.grid_main.attach(self.stack_main, 0, 1, 1, 1)

        '''
        Connect signals to widgets
        '''
        self.btn_add.connect('pressed', self.show_add_view)
        self.btn_list.connect('pressed', self.show_list_view)
        self.btn_preferences.connect('pressed', self.show_preferences_view)
        self.switch_dark.connect('state-set', self.toggle_dark)

        '''
        Set widgets status from user settings
        '''
        self.switch_dark.set_active(self.settings.get_boolean("dark-theme"))

    def show_add_view(self, widget):
        self.stack_main.set_visible_child_name("page_add")

    def show_list_view(self, widget):
        self.stack_main.set_visible_child_name("page_list")

    def show_preferences_view(self):
        self.stack_main.set_visible_child_name("page_preferences")

    def toggle_dark(self, widget, state):
        self.settings.set_boolean("dark-theme", state)
        self.default_settings.set_property("gtk-application-prefer-dark-theme", state)
