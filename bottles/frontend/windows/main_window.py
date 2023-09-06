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
from typing import Optional

from gi.repository import Gtk, GLib, Gio, Adw, GObject, Gdk

from bottles.backend.globals import Paths
from bottles.backend.health import HealthChecker
from bottles.backend.logger import Logger
from bottles.backend.managers.data import UserDataKeys
from bottles.backend.managers.manager import Manager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.state import SignalManager, Signals, Notification
from bottles.backend.utils.connection import ConnectionUtils
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.const import *
from bottles.frontend.operation import TaskSyncer
from bottles.frontend.params import *
from bottles.frontend.utils.gtk import GtkUtils
from bottles.frontend.views.details import DetailsView
from bottles.frontend.views.importer import ImporterView
from bottles.frontend.views.library import LibraryView
from bottles.frontend.views.list import BottleView
from bottles.frontend.views.loading import LoadingView
from bottles.frontend.views.new import NewView
from bottles.frontend.views.preferences import PreferencesWindow
from bottles.frontend.windows.crash import CrashReportDialog
from bottles.frontend.windows.depscheck import DependenciesCheckDialog
from bottles.frontend.windows.onboard import OnboardDialog

logging = Logger()


@Gtk.Template(resource_path='/com/usebottles/bottles/window.ui')
class MainWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MainWindow'

    # region Widgets
    stack_main = Gtk.Template.Child()
    btn_add = Gtk.Template.Child()
    btn_search = Gtk.Template.Child()
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
    settings = Gio.Settings.new(APP_ID)
    argument_executed = False

    def __init__(self, arg_bottle, **kwargs):

        width = self.settings.get_int("window-width")
        height = self.settings.get_int("window-height")

        super().__init__(**kwargs, default_width=width, default_height=height)

        self.disable_onboard = False
        self.utils_conn = ConnectionUtils(force_offline=self.settings.get_boolean("force-offline"))
        self.manager = None
        self.arg_bottle = arg_bottle
        self.app = kwargs.get("application")

        if BUILD_TYPE == "devel":
            self.add_css_class("devel")

        # Set night theme according to user settings
        if self.settings.get_boolean("dark-theme"):
            manager = Adw.StyleManager.get_default()
            manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

        # Loading view
        self.page_loading = LoadingView()

        # Populate stack
        self.stack_main.add_named(
            child=self.page_loading,
            name="page_loading"
        ).set_visible(False)
        self.headerbar.add_css_class("flat")

        # Signal connections
        self.btn_add.connect("clicked", self.show_add_view)
        self.btn_noconnection.connect("clicked", self.check_for_connection)
        self.stack_main.connect("notify::visible-child", self.__on_page_changed)

        # backend signal handlers
        self.task_syncer = TaskSyncer(self)
        SignalManager.connect(Signals.TaskAdded, self.task_syncer.task_added_handler)
        SignalManager.connect(Signals.TaskRemoved, self.task_syncer.task_removed_handler)
        SignalManager.connect(Signals.TaskUpdated, self.task_syncer.task_updated_handler)
        SignalManager.connect(Signals.NetworkStatusChanged, self.network_changed_handler)
        SignalManager.connect(Signals.GNotification, self.g_notification_handler)
        SignalManager.connect(Signals.GShowUri, self.g_show_uri_handler)

        self.__on_start()
        logging.info("Bottles Started!", )

    @Gtk.Template.Callback()
    def on_close_request(self, *args):
        self.settings.set_int("window-width", self.get_width())
        self.settings.set_int("window-height", self.get_height())

    # region Backend signal handlers
    def network_changed_handler(self, res: Result):
        GLib.idle_add(self.btn_noconnection.set_visible, not res.status)

    def g_notification_handler(self, res: Result):
        """handle backend notification request"""
        notify: Notification = res.data
        self.send_notification(title=notify.title, text=notify.text, image=notify.image)

    def g_show_uri_handler(self, res: Result):
        """handle backend show_uri request"""
        uri: str = res.data
        Gtk.show_uri(self, uri, Gdk.CURRENT_TIME)

    # endregion

    def update_library(self):
        GLib.idle_add(self.page_library.update)

    def set_title(self, title, subtitle: str = ""):
        self.view_switcher_title.set_title(title)
        self.view_switcher_title.set_subtitle(subtitle)

    def check_for_connection(self, status):
        """
        This method checks if the client has an internet connection.
        If true, the manager checks will be performed, unlocking all the
        features locked for no internet connection.
        """
        if self.utils_conn.check_connection():
            self.manager.checks(install_latest=False, first_run=True)

    def __on_start(self):
        """
        This method is called before the window is shown. This check if there
        is at least one local runner installed. If not, the user will be
        prompted with the onboard dialog.
        """

        @GtkUtils.run_in_main_loop
        def set_manager(result: Manager, error=None):
            self.manager = result

            tmp_runners = [x for x in self.manager.runners_available if not x.startswith('sys-')]
            if len(tmp_runners) == 0:
                self.show_onboard_view()

            # Pages
            self.page_details = DetailsView(self)
            self.page_list = BottleView(self, arg_bottle=self.arg_bottle)
            self.page_importer = ImporterView(self)
            self.page_library = LibraryView(self)

            self.main_leaf.append(self.page_details)
            self.main_leaf.append(self.page_importer)

            self.main_leaf.get_page(self.page_details).set_navigatable(False)
            self.main_leaf.get_page(self.page_importer).set_navigatable(False)

            self.stack_main.add_titled(
                child=self.page_list,
                name="page_list",
                title=_("Bottles")
            ).set_icon_name("com.usebottles.bottles-symbolic")
            self.stack_main.add_titled(
                child=self.page_library,
                name="page_library",
                title=_("Library")
            ).set_icon_name("library-symbolic")

            self.page_list.search_bar.set_key_capture_widget(self)
            self.btn_search.bind_property('active', self.page_list.search_bar, 'search-mode-enabled',
                                          GObject.BindingFlags.BIDIRECTIONAL)

            if self.stack_main.get_child_by_name(self.settings.get_string("startup-view")) is None:
                self.stack_main.set_visible_child_name("page_list")

            self.settings.bind(
                "startup-view",
                self.stack_main,
                "visible-child-name",
                Gio.SettingsBindFlags.DEFAULT
            )

            self.lock_ui(False)
            self.headerbar.get_style_context().remove_class("flat")

            user_defined_bottles_path = self.manager.data_mgr.get(UserDataKeys.CustomBottlesPath)
            if user_defined_bottles_path and Paths.bottles != user_defined_bottles_path:
                dialog = Adw.MessageDialog.new(
                    self,
                    _("Custom Bottles Path not Found"),
                    _("Falling back to default path. No bottles from the given path will be listed.")
                )
                dialog.add_response("cancel", _("_Dismiss"))
                dialog.present()

        def get_manager():
            if self.utils_conn.check_connection():
                SignalManager.connect(Signals.RepositoryFetched, self.page_loading.add_fetched)
            
            # do not redo connection if aborted connection 
            mng = Manager(g_settings=self.settings, check_connection=self.utils_conn.aborted_connections == 0) 
            return mng

        self.check_core_deps()
        self.show_loading_view()
        RunAsync(get_manager, callback=set_manager)

        self.check_crash_log()

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

    def show_details_view(self, widget=False, config: Optional[BottleConfig] = None):
        self.main_leaf.set_visible_child(self.page_details)
        self.page_details.set_config(config or BottleConfig())

    def show_loading_view(self, widget=False):
        self.lock_ui()
        self.stack_main.set_visible_child_name("page_loading")

    def show_onboard_view(self, widget=False):
        if self.disable_onboard:
            return

        onboard_window = OnboardDialog(self)
        onboard_window.present()

    def show_add_view(self, widget=False):
        new_window = NewView(self)
        new_window.present()

    def show_list_view(self, widget=False):
        self.stack_main.set_visible_child_name("page_list")

    def show_importer_view(self, widget=False):
        self.main_leaf.set_visible_child(self.page_importer)

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
            with open(log_path, "r") as log_file:
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

    def show_toast(self,
                   message,
                   timeout=3,
                   action_label=None,
                   action_callback=None,
                   dismissed_callback=None
                   ) -> Adw.Toast:

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

    def check_core_deps(self):
        if "FLATPAK_ID" not in os.environ and not HealthChecker().has_core_deps():
            self.disable_onboard = True
            DependenciesCheckDialog(self).present()

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
