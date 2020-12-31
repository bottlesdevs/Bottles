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

@Gtk.Template(resource_path='/com/usebottles/bottles/create.ui')
class BottlesCreate(Gtk.Box):
    __gtype_name__ = 'BottlesCreate'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    progressbar_create = Gtk.Template.Child()
    textview_output = Gtk.Template.Child()
    label_output = Gtk.Template.Child()
    btn_list = Gtk.Template.Child()
    box_created = Gtk.Template.Child()
    label_creating = Gtk.Template.Child()

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
        self.runner = window.runner

        '''
        Connect signals to widgets
        '''
        self.btn_list.connect('pressed', self.show_details)

    def update_output(self, text):
        current_text = self.label_output.get_text()
        text = "{0}{1}\n".format(current_text, text)
        self.label_output.set_text(text)

    '''
    Set widgets visibility status
    '''
    def set_status(self, status="initial"):
        if status == "initial":
            self.btn_list.set_visible(False)
            self.box_created.set_visible(False)
            self.label_creating.set_visible(True)
            self.label_output.set_text("")
        elif status == "created":
            self.btn_list.set_visible(True)
            self.box_created.set_visible(True)
            self.label_creating.set_visible(False)

    def show_details(self, widget):
        self.window.stack_main.set_visible_child_name("page_list")
        self.set_status("initial")

        '''
        Update bottles
        '''
        self.runner.update_bottles()

    '''
    Make the progressbar pulse every 1 second
    '''
    def pulse(self):
        while True:
            time.sleep(1)
            self.progressbar_create.pulse()

