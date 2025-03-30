# window.py
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

import contextlib
import os
import webbrowser
from gettext import gettext as _

from gi.repository import Gtk, GLib, Gio, Adw, GObject, Gdk, Xdp

from bottles.backend.globals import Paths
from bottles.backend.health import HealthChecker
import logging
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.params import APP_ID, BASE_ID, PROFILE
from bottles.frontend.gtk import GtkUtils
from bottles.frontend.bottle_details_view import BottleDetailsView
from bottles.frontend.bottles_list_view import BottlesListView
from bottles.frontend.new_bottle_dialog import NewBottleDialog
from bottles.frontend.preferences import PreferencesWindow
from bottles.frontend.crash_report_dialog import CrashReportDialog
from bottles.frontend.dependencies_check_dialog import DependenciesCheckDialog
from bottles.frontend.onboard_dialog import OnboardDialog


@Gtk.Template(resource_path="/com/usebottles/bottles/window.ui")
class BottlesWindow(Adw.ApplicationWindow):
    __gtype_name__ = "BottlesWindow"

    # region Widgets
    stack_main = Gtk.Template.Child()
    btn_add = Gtk.Template.Child()
    btn_search = Gtk.Template.Child()
    btn_donate = Gtk.Template.Child()
    btn_noconnection = Gtk.Template.Child()
    box_actions = Gtk.Template.Child()
    headerbar = Gtk.Template.Child()
    view_switcher_title = Gtk.Template.Child()
    view_switcher_bar = Gtk.Template.Child()
    main_leaf = Gtk.Template.Child()
    toasts = Gtk.Template.Child()
    # endregion

    # Common variables
    previous_page = ""
    settings = Gio.Settings.new(BASE_ID)
    argument_executed = False

    def __init__(self, **kwargs):
        width = self.settings.get_int("window-width")
        height = self.settings.get_int("window-height")

        super().__init__(**kwargs, default_width=width, default_height=height)

        self.manager = None
        self.app = kwargs.get("application")
        self.set_icon_name(APP_ID)

        if PROFILE == "development":
            self.add_css_class("devel")
            logging.getLogger().setLevel(logging.DEBUG)

        self.btn_donate.add_css_class("donate")

        # Set night theme according to user settings
        if self.settings.get_boolean("dark-theme"):
            manager = Adw.StyleManager.get_default()
            manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

        # Be VERY explicit that non-sandboxed environments are unsupported
        if not Xdp.Portal.running_under_sandbox():

            def response(dialog, response, *args):
                if response == "close":
                    quit(1)

            body = _(
                "Bottles is only supported within a sandboxed environment. Official sources of Bottles are available at"
            )
            download_url = "usebottles.com/download"

            error_dialog = Adw.AlertDialog.new(
                _("Unsupported Environment"),
                f"{body} <a href='https://{download_url}' title='https://{download_url}'>{download_url}.</a>",
            )

            error_dialog.add_response("close", _("Close"))
            error_dialog.set_body_use_markup(True)
            error_dialog.connect("response", response)
            error_dialog.present(self)
            logging.error(
                _(
                    "Bottles is only supported within a sandboxed environment. Official sources of Bottles are available at"
                )
            )
            logging.error("https://usebottles.com/download/")
            return

        self.headerbar.add_css_class("flat")

        # Signal connections
        self.btn_donate.connect(
            "clicked",
            self.open_url,
            "https://usebottles.com/funding/",
        )
        self.btn_add.connect("clicked", self.show_add_view)
        self.stack_main.connect("notify::visible-child", self.__on_page_changed)

        # Pages
        self.page_details = BottleDetailsView(self)
        self.page_list = BottlesListView()

        self.main_leaf.append(self.page_details)

        self.main_leaf.get_page(self.page_details).set_navigatable(False)

        self.stack_main.add_titled(
            child=self.page_list, name="page_list", title=_("Bottles")
        ).set_icon_name(f"{APP_ID}-symbolic")

        self.page_list.search_bar.set_key_capture_widget(self)
        self.btn_search.bind_property(
            "active",
            self.page_list.search_bar,
            "search-mode-enabled",
            GObject.BindingFlags.BIDIRECTIONAL,
        )

        if (
            self.stack_main.get_child_by_name(self.settings.get_string("startup-view"))
            is None
        ):
            self.stack_main.set_visible_child_name("page_list")

        self.settings.bind(
            "startup-view",
            self.stack_main,
            "visible-child-name",
            Gio.SettingsBindFlags.DEFAULT,
        )

        self.lock_ui(False)
        self.headerbar.get_style_context().remove_class("flat")

    @Gtk.Template.Callback()
    def on_close_request(self, *args):
        self.settings.set_int("window-width", self.get_width())
        self.settings.set_int("window-height", self.get_height())

    # endregion

    def title(self, title, subtitle: str = ""):
        self.view_switcher_title.set_title(title)
        self.view_switcher_title.set_subtitle(subtitle)

    def send_notification(self, title, text, image="", ignore_user=False):
        """
        This method is used to send a notification to the user using
        Gio.Notification. The notification is sent only if the
        user has enabled it in the settings. It is possible to ignore the
        user settings by passing the argument ignore_user=False.
        """
        if ignore_user or self.settings.get_boolean("notifications"):
            notification = Gio.Notification.new(title)
            notification.set_body(text)
            if image:
                icon = Gio.ThemedIcon.new(image)
                notification.set_icon(icon)

            self.props.application.send_notification(None, notification)

    def go_back(self, *_args):
        self.main_leaf.navigate(direction=Adw.NavigationDirection.BACK)

    def show_details_view(self, widget=False, config: BottleConfig | None = None):
        self.main_leaf.set_visible_child(self.page_details)
        self.page_details.set_config(config or BottleConfig())

    def show_onboard_view(self, widget=False):
        onboard_window = OnboardDialog(self)
        onboard_window.present()

    def show_add_view(self, widget=False):
        new_bottle_dialog = NewBottleDialog()
        new_bottle_dialog.present(self)

    def show_list_view(self, widget=False):
        self.stack_main.set_visible_child_name("page_list")

    def show_prefs_view(self, widget=False, view=0):
        preferences_window = PreferencesWindow(self)
        preferences_window.present()

    def show_download_preferences_view(self, widget=False):
        self.show_prefs_view(widget, view=1)

    def show_runners_preferences_view(self, widget=False):
        self.show_prefs_view(widget, view=2)

    def check_crash_log(self):
        xdg_data_home = GLib.get_user_data_dir()
        log_path = f"{xdg_data_home}/bottles/crash.log"

        with contextlib.suppress(FileNotFoundError):
            with open(log_path) as log_file:
                crash_log = log_file.readlines()
                os.remove(log_path)

            if crash_log:
                CrashReportDialog(self, crash_log).present()

    def toggle_selection_mode(self, status: bool = True):
        context = self.headerbar.get_style_context()
        if status:
            context.add_class("selection-mode")
        else:
            context.remove_class("selection-mode")

    def lock_ui(self, status: bool = True):
        widgets = [
            self.btn_add,
            self.view_switcher_title,
        ]
        if self.btn_noconnection.get_visible():
            widgets.append(self.btn_noconnection)
        for w in widgets:
            w.set_visible(not status)

    def show_toast(
        self,
        message,
        timeout=3,
        action_label=None,
        action_callback=None,
        dismissed_callback=None,
    ) -> None:
        toast = Adw.Toast.new(message)
        toast.props.timeout = timeout

        if action_label and action_callback:
            toast.set_button_label(action_label)

            def wrapper_callback(*args):
                action_callback(toast)
                toast.handler_block_by_func(dismissed_callback)

            toast.connect("button-clicked", wrapper_callback)

        if dismissed_callback:
            toast.connect("dismissed", dismissed_callback)

        self.toasts.add_toast(toast)

    def __on_page_changed(self, stack, *args):
        is_bottles_list = stack.get_visible_child_name() == "page_list"
        self.btn_search.set_visible(is_bottles_list)

    @staticmethod
    def proper_close():
        """Properly close Bottles"""
        quit()

    @staticmethod
    def open_url(widget, url):
        webbrowser.open_new_tab(url)
