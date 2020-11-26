# create.py
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

import time

@Gtk.Template(resource_path='/pm/mirko/bottles/create.ui')
class BottlesCreate(Gtk.Box):
    __gtype_name__ = 'BottlesCreate'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    progressbar_create = Gtk.Template.Child()
    textview_output = Gtk.Template.Child()
    buffer_output = Gtk.Template.Child()
    btn_open = Gtk.Template.Child()

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

        '''
        Connect signals to widgets
        '''
        self.btn_open.connect('pressed', self.show_details)

    def show_details(self, widget):
        self.window.stack_main.set_visible_child_name("page_details")

    '''
    Make the progressbar pulse every 1 second
    '''
    def pulse(self):
        while True:
            time.sleep(1)
            self.progressbar_create.pulse()

