# onboard.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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

from gettext import gettext as _

from gi.repository import Adw, Gtk

from bottles.backend.models.result import Result
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.utils.gtk import GtkUtils


@Gtk.Template(resource_path="/com/usebottles/bottles/onboard.ui")
class OnboardDialog(Adw.Dialog):
    __gtype_name__ = "OnboardDialog"
    __installing = False
    __progress_total = 0
    __settings = Gtk.Settings.get_default()

    # region Widgets
    carousel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    btn_next = Gtk.Template.Child()
    btn_install = Gtk.Template.Child()
    progressbar = Gtk.Template.Child()
    label_progress = Gtk.Template.Child()
    label_status = Gtk.Template.Child()
    page_welcome = Gtk.Template.Child()
    page_bottles = Gtk.Template.Child()
    page_download = Gtk.Template.Child()
    page_finish = Gtk.Template.Child()
    img_welcome = Gtk.Template.Child()
    label_skip = Gtk.Template.Child()
    # endregion

    carousel_pages = ["welcome", "bottles", "download", "finish"]
    images = [
        "/com/usebottles/bottles/images/images/bottles-welcome.svg",
        "/com/usebottles/bottles/images/images/bottles-welcome-night.svg",
    ]

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager

        # connect signals
        self.carousel.connect("page-changed", self.__page_changed)
        self.btn_close.connect("clicked", self.__close_dialog)
        self.btn_back.connect("clicked", self.__previous_page)
        self.btn_next.connect("clicked", self.__next_page)
        self.btn_install.connect("clicked", self.__install_runner)
        self.__settings.connect(
            "notify::gtk-application-prefer-dark-theme", self.__theme_changed
        )

        self.btn_close.set_sensitive(False)

        if self.__settings.get_property("gtk-application-prefer-dark-theme"):
            self.img_welcome.set_from_resource(self.images[1])

        self.__page_changed()

    def __theme_changed(self, settings, key):
        self.img_welcome.set_from_resource(
            self.images[settings.get_property("gtk-application-prefer-dark-theme")]
        )

    def __get_page(self, index):
        return self.carousel_pages[index]

    def __page_changed(self, widget=False, index=0, *_args):
        """
        This function is called on first load and when the user require
        to change the page. It sets the widgets' status according to
        the step of the onboard progress.
        """
        page = self.__get_page(index)

        if page == "finish":
            self.btn_back.set_visible(False)
            self.btn_next.set_visible(False)
        elif page == "download":
            self.btn_back.set_visible(True)
            self.btn_next.set_visible(False)
            self.btn_install.set_visible(True)
        elif page == "welcome":
            self.btn_back.set_visible(False)
            self.btn_next.set_visible(True)
        else:
            self.btn_back.set_visible(True)
            self.btn_next.set_visible(True)

    @staticmethod
    def __quit(widget=False):
        quit()

    def __install_runner(self, widget):
        @GtkUtils.run_in_main_loop
        def set_completed(result: Result, error=False):
            if result.ok:
                self.label_skip.set_visible(False)
                self.btn_close.set_sensitive(True)
                self.__next_page()
            else:
                self.__installing = False
                self.btn_install.set_visible(True)
                self.progressbar.set_visible(False)

        self.__installing = True
        self.btn_back.set_visible(False)
        self.btn_next.set_visible(False)
        self.btn_install.set_visible(False)
        self.progressbar.set_visible(True)
        self.progressbar.set_fraction(0)
        self.label_progress.set_visible(False)
        self.label_status.set_visible(False)
        self.__progress_total = 0
        self.carousel.set_allow_long_swipes(False)
        self.carousel.set_allow_mouse_drag(False)
        self.carousel.set_allow_scroll_wheel(False)

        RunAsync(
            task_func=self.manager.checks,
            callback=set_completed,
            install_latest=True,
            first_run=True,
            progress_callback=self.__handle_progress,
        )

    def __previous_page(self, widget=False):
        index = int(self.carousel.get_position())
        previous_page = self.carousel.get_nth_page(index - 1)
        self.carousel.scroll_to(previous_page, True)

    def __next_page(self, widget=False):
        index = int(self.carousel.get_position())
        next_page = self.carousel.get_nth_page(index + 1)
        self.carousel.scroll_to(next_page, True)

    def __handle_progress(self, **kwargs):
        self.__update_progress(**kwargs)

    @GtkUtils.run_in_main_loop
    def __update_progress(
        self,
        description: str,
        current_step: int,
        total_steps: int,
        completed: bool,
    ):
        if total_steps:
            self.__progress_total = total_steps

        displayed_step = current_step
        completed_steps = current_step if completed else max(0, current_step - 1)

        if self.__progress_total:
            self.progressbar.set_fraction(completed_steps / self.__progress_total)
            self.progressbar.set_visible(True)
            self.label_progress.set_visible(True)
            self.label_progress.set_label(
                _("Step {current} of {total}").format(
                    current=displayed_step, total=self.__progress_total
                )
            )

        if not completed:
            self.label_status.set_visible(True)
            self.label_status.set_label(description)

    @GtkUtils.run_in_main_loop
    def __update_progress(
        self,
        description: str,
        current_step: int,
        total_steps: int,
        completed: bool,
    ):
        if total_steps:
            self.__progress_total = total_steps

        displayed_step = current_step
        completed_steps = current_step if completed else max(0, current_step - 1)

        if self.__progress_total:
            self.progressbar.set_fraction(completed_steps / self.__progress_total)
            self.progressbar.set_visible(True)
            self.label_progress.set_visible(True)
            self.label_progress.set_label(
                _("Step {current} of {total}").format(
                    current=displayed_step, total=self.__progress_total
                )
            )

        if not completed:
            self.label_status.set_visible(True)
            self.label_status.set_label(description)

    def __close_dialog(self, widget):
        self.force_close()
