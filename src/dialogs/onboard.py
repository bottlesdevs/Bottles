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

from gi.repository import Gtk, Adw

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false


@Gtk.Template(resource_path='/com/usebottles/bottles/onboard.ui')
class OnboardDialog(Adw.Window):
    __gtype_name__ = 'OnboardDialog'

    # region Widgets
    stack_onboard = Gtk.Template.Child()
    btn_quit = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    btn_next = Gtk.Template.Child()
    btn_install = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    progressbar_downloading = Gtk.Template.Child()
    # endregion

    stack_pages = [
        "page_welcome",
        "page_about",
        "page_runners",
        "page_download",
        "page_finish"
    ]

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager

        # connect signals
        self.stack_onboard.connect('notify::visible-child', self.__page_changed)
        self.btn_close.connect("clicked", self.__close_window)
        self.btn_quit.connect("clicked", self.__quit)
        self.btn_back.connect("clicked", self.__previous_page)
        self.btn_next.connect("clicked", self.__next_page)
        self.btn_install.connect("clicked", self.__install_runner)

        self.__page_changed()

    def __page_changed(self, widget=False, event=False):
        """
        This function is called on first load and when the user require
        to change the page. It sets the widgets status according to
        the step of the onboard progress.
        """
        page = self.stack_onboard.get_visible_child_name()

        if page == "page_welcome":
            self.btn_next.set_visible(True)
            self.btn_quit.set_visible(True)
            self.btn_back.set_visible(False)
            self.btn_install.set_visible(False)
            self.btn_close.set_visible(False)

        if page == "page_wine":
            self.btn_next.set_visible(True)
            self.btn_quit.set_visible(False)
            self.btn_back.set_visible(True)
            self.btn_install.set_visible(False)
            self.btn_close.set_visible(False)

        if page == "page_runners":
            self.btn_next.set_visible(False)
            self.btn_quit.set_visible(False)
            self.btn_back.set_visible(True)
            self.btn_install.set_visible(True)
            self.btn_close.set_visible(False)

        if page == "page_download":
            self.btn_next.set_visible(False)
            self.btn_quit.set_visible(False)
            self.btn_back.set_visible(False)
            self.btn_install.set_visible(False)
            self.btn_close.set_visible(False)

        if page == "page_finish":
            self.btn_next.set_visible(False)
            self.btn_quit.set_visible(False)
            self.btn_back.set_visible(False)
            self.btn_install.set_visible(False)
            self.btn_close.set_visible(True)

    @staticmethod
    def __quit(widget=False):
        quit()

    def __install_runner(self, widget):
        def set_completed(result, error=False):
            self.__next_page()

        '''
        This method ask the manager to performs its checks, then
        it will install the latest runner if there is no one installed.
        '''
        self.__next_page()
        RunAsync(self.pulse)
        RunAsync(
            task_func=self.manager.checks,
            callback=set_completed,
            install_latest=True,
            first_run=True
        )

    def __previous_page(self, widget=False):
        visible_child = self.stack_onboard.get_visible_child_name()
        previous_page = self.stack_pages[self.stack_pages.index(visible_child) - 1]
        self.stack_onboard.set_visible_child_name(previous_page)

    def __next_page(self, widget=False):
        visible_child = self.stack_onboard.get_visible_child_name()
        next_page = self.stack_pages[self.stack_pages.index(visible_child) + 1]
        self.stack_onboard.set_visible_child_name(next_page)

    def pulse(self):
        # This function update the progress bar every 1s.
        while True:
            time.sleep(.5)
            self.progressbar_downloading.pulse()

    def __close_window(self, widget):
        self.destroy()
