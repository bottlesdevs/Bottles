# onboard.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import time
import sys

from gi.repository import Gtk, Adw

from bottles.backend.models.result import Result
from bottles.frontend.utils.threading import RunAsync


@Gtk.Template(resource_path="/com/usebottles/bottles/onboard.ui")
class OnboardDialog(Adw.Window):
    __gtype_name__ = "OnboardDialog"
    __settings = Gtk.Settings.get_default()

    # region Widgets
    carousel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    btn_next = Gtk.Template.Child()
    btn_skip = Gtk.Template.Child()
    btn_install = Gtk.Template.Child()
    progressbar = Gtk.Template.Child()
    img_welcome = Gtk.Template.Child()
    # endregion

    images = [
        "/com/usebottles/bottles/images/images/bottles-welcome.svg",
        "/com/usebottles/bottles/images/images/bottles-welcome-night.svg",
    ]

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.manager = window.manager

        # connect signals
        self.connect("close-request", self.__quit)
        self.carousel.connect("page-changed", self.__page_changed)
        self.btn_close.connect("clicked", self.__close_window)
        self.btn_back.connect("clicked", self.__previous_page)
        self.btn_next.connect("clicked", self.__next_page)
        self.btn_install.connect("clicked", self.__install_runner)
        self.btn_skip.connect("clicked", self.__skip_tutorial)
        self.__settings.connect("notify::gtk-application-prefer-dark-theme", self.__theme_changed)

        if self.__settings.get_property("gtk-application-prefer-dark-theme"):
            self.img_welcome.set_from_resource(self.images[1])

        self.__page_changed()

    def __theme_changed(self, settings, _key):
        self.img_welcome.set_from_resource(self.images[settings.get_property("gtk-application-prefer-dark-theme")])

    def __page_changed(self, *_args):
        """
        This function is called on first load and when the user require
        to change the page. It sets the widgets' status according to
        the step of the onboard progress.
        """
        if self.carousel.get_position() == 0:
            self.btn_back.set_visible(False)
            self.btn_next.set_visible(True)
        elif self.carousel.get_position() == self.carousel.get_n_pages() - 2:
            self.btn_back.set_visible(True)
            self.btn_next.set_visible(False)
        elif self.carousel.get_position() == self.carousel.get_n_pages() - 1:
            self.btn_back.set_visible(False)
            self.btn_next.set_visible(False)
        else:
            self.btn_back.set_visible(True)
            self.btn_next.set_visible(True)

    @staticmethod
    def __quit(_widget):
        sys.exit()

    def __install_runner(self, _widget):
        def set_completed(_result: Result, _error=False):
            self.__next_page()

        self.btn_back.set_visible(False)
        self.btn_next.set_visible(False)
        self.btn_install.set_visible(False)
        self.progressbar.set_visible(True)
        self.set_deletable(False)

        RunAsync(self.pulse)
        RunAsync(
            task_func=self.manager.checks,
            callback=set_completed,
            install_latest=True,
            first_run=True
        )

    def __previous_page(self, _widget):
        index = self.carousel.get_position()
        previous_page = self.carousel.get_nth_page(index - 1)
        self.carousel.scroll_to(previous_page, True)

    def __next_page(self, _widget=None):
        index = self.carousel.get_position()
        next_page = self.carousel.get_nth_page(index + 1)
        self.carousel.scroll_to(next_page, True)

    def pulse(self):
        # This function update the progress bar every 1s.
        while True:
            time.sleep(.5)
            self.progressbar.pulse()

    def __skip_tutorial(self, _widget):
        self.carousel.scroll_to(self.carousel.get_nth_page(self.carousel.get_n_pages() - 2), True)

    def __close_window(self, _widget):
        self.destroy()
