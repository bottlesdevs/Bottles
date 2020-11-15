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

from gi.repository import Gtk
from .constants import *
from .pages.add import BottlesAdd

@Gtk.Template(resource_path='/pm/mirko/bottles/window.ui')
class BottlesWindow(Gtk.ApplicationWindow):
    __gtype_name__ = 'BottlesWindow'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    main_stack = Gtk.Template.Child()
    btn_add = Gtk.Template.Child()
    btn_list = Gtk.Template.Child()
    btn_preferences = Gtk.Template.Child()

    '''
    Get and assign pages to variable
    '''
    page_add = BottlesAdd()

    '''
    Common variables
    '''
    settings = Gtk.Settings.get_default()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()
        self.settings.set_property("gtk-application-prefer-dark-theme", True)

        '''
        Add pages to stack and set options
        '''
        self.main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.main_stack.set_transition_duration(ANIM_DURATION)
        self.main_stack.add_titled(self.page_add, "page_add", "New Bottle")
        self.add(self.main_stack)

        '''
        Connect signals to widgets
        '''
        self.btn_add.connect('pressed', self.show_add_view)
        self.btn_list.connect('pressed', self.show_list_view)
        self.btn_preferences.connect('pressed', self.show_preferences_view)

    def show_add_view(self, widget):
        self.main_stack.set_visible_child_name("page_add")

    def show_list_view(self, widget):
        self.main_stack.set_visible_child_name("page_list")

    def show_preferences_view(self, widget):
        self.main_stack.set_visible_child_name("page_preferences")
