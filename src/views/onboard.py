# onboard.py
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

import time

from gi.repository import Gtk, Handy

from ..utils import RunAsync

@Gtk.Template(resource_path='/com/usebottles/bottles/onboard.ui')
class OnboardDialog(Handy.Window):
    __gtype_name__ = 'OnboardDialog'

    # region Widgets
    stack_onboard = Gtk.Template.Child()
    btn_stack_next = Gtk.Template.Child()
    btn_stack_back = Gtk.Template.Child()
    btn_quit = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    btn_next = Gtk.Template.Child()
    btn_install = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    progressbar_downloading = Gtk.Template.Child()
    # endregion

    stack_pages = [
        "page_welcome",
        "page_wine",
        "page_runners",
        "page_download",
        "page_finish"
    ]

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        '''Common variables'''
        self.window = window
        self.manager = window.manager

        '''Signal connections'''
        self.stack_onboard.connect('notify::visible-child', self.page_changed)
        self.btn_close.connect('pressed', self.close_window)
        self.btn_quit.connect('pressed', self.quit)
        self.btn_back.connect('pressed', self.previous_page)
        self.btn_next.connect('pressed', self.next_page)
        self.btn_install.connect('pressed', self.install_runner)

        self.page_changed()

    def page_changed(self, widget=False, event=False):
        page = self.stack_onboard.get_visible_child_name()

        if page == "page_welcome":
            self.btn_stack_next.set_visible(True)
            self.btn_stack_next.set_visible_child(self.btn_next)
            self.btn_stack_back.set_visible(True)
            self.btn_stack_back.set_visible_child(self.btn_quit)

        if page == "page_wine":
            self.btn_stack_next.set_visible(True)
            self.btn_stack_next.set_visible_child(self.btn_next)
            self.btn_stack_back.set_visible(True)
            self.btn_stack_back.set_visible_child(self.btn_back)

        if page == "page_runners":
            self.btn_stack_next.set_visible(True)
            self.btn_stack_next.set_visible_child(self.btn_install)
            self.btn_stack_back.set_visible(True)
            self.btn_stack_back.set_visible_child(self.btn_back)

        if page == "page_download":
            self.btn_stack_next.set_visible(False)
            self.btn_stack_next.set_visible_child(self.btn_install)
            self.btn_stack_back.set_visible(False)
            self.btn_stack_back.set_visible_child(self.btn_quit)

        if page == "page_finish":
            self.btn_stack_next.set_visible(True)
            self.btn_stack_next.set_visible_child(self.btn_close)
            self.btn_stack_back.set_visible(False)
            self.btn_stack_back.set_visible_child(self.btn_quit)

    def quit(self, widget=False):
        quit()

    def install_runner(self, widget):
        self.next_page()
        RunAsync(self.pulse, None)
        self.manager.checks(after=self.next_page)

    def previous_page(self, widget=False):
        visible_child = self.stack_onboard.get_visible_child_name()
        previous_page = self.stack_pages[self.stack_pages.index(visible_child) - 1]
        self.stack_onboard.set_visible_child_name(previous_page)

    def next_page(self, widget=False):
        visible_child = self.stack_onboard.get_visible_child_name()
        next_page = self.stack_pages[self.stack_pages.index(visible_child) + 1]
        self.stack_onboard.set_visible_child_name(next_page)

    '''Progressbar pulse every 1s'''
    def pulse(self):
        while True:
            time.sleep(1)
            self.progressbar_downloading.pulse()

    '''Destroy the window'''
    def close_window(self, widget):
        self.destroy()
