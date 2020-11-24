# preferences.py
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

from gi.repository import Gtk


@Gtk.Template(resource_path='/pm/mirko/bottles/preferences.ui')
class BottlesPreferences(Gtk.Box):
    __gtype_name__ = 'BottlesPreferences'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    notebook_preferences = Gtk.Template.Child()
    switch_notifications = Gtk.Template.Child()
    combo_views = Gtk.Template.Child()

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        '''
        Common variables
        '''
        self.window = window
        self.settings = window.settings

        '''
        Connect signals to widgets
        '''
        self.switch_notifications.connect('state-set', self.toggle_notifications)
        self.combo_views.connect('changed', self.change_startup_view)

        '''
        Set widgets status from user settings
        '''
        self.switch_notifications.set_active(self.settings.get_boolean("download-notifications"))
        self.combo_views.set_active_id(self.settings.get_string("startup-view"))

    '''
    Toggle notifications and store status in settings
    '''
    def toggle_notifications(self, widget, state):
        self.settings.set_boolean("download-notifications", state)

    '''
    Change the startup view and save in user settings
    '''
    def change_startup_view(self, widget):
        option = widget.get_active_id()
        self.settings.set_string("startup-view", option)
        
