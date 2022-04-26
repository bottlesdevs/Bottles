# window.py
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

import os
import time
import webbrowser
from gettext import gettext as _
from gi.repository import Gtk, GLib, Gio, Adw
from pathlib import Path

from bottles.params import *  # pyright: reportMissingImports=false
from bottles.widgets.message import MessageEntry
from bottles.backend.logger import Logger
from bottles.utils.threading import RunAsync
from bottles.utils.connection import ConnectionUtils

from bottles.backend.globals import Paths
from bottles.backend.health import HealthChecker
from bottles.backend.managers.manager import Manager
from bottles.backend.wine.executor import WineExecutor

from bottles.views.new import NewView
from bottles.views.details import DetailsView
from bottles.views.list import ListView
from bottles.views.library import LibraryView
from bottles.views.preferences import PreferencesWindow
from bottles.views.importer import ImporterView
from bottles.views.loading import LoadingView

from bottles.dialogs.crash import CrashReportDialog
from bottles.dialogs.generic import AboutDialog, SourceDialog
from bottles.dialogs.onboard import OnboardDialog
from bottles.dialogs.journal import JournalDialog

logging = Logger()


@Gtk.Template(resource_path='/com/usebottles/bottles/window.ui')
class MainWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MainWindow'

    # region Widgets
    grid_main = Gtk.Template.Child()
    stack_main = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    btn_add = Gtk.Template.Child()
    btn_preferences = Gtk.Template.Child()
    btn_about = Gtk.Template.Child()
    btn_operations = Gtk.Template.Child()
    btn_menu = Gtk.Template.Child()
    btn_support = Gtk.Template.Child()
    btn_docs = Gtk.Template.Child()
    btn_forum = Gtk.Template.Child()
    btn_importer = Gtk.Template.Child()
    btn_noconnection = Gtk.Template.Child()
    btn_health = Gtk.Template.Child()
    btn_library = Gtk.Template.Child()
    box_actions = Gtk.Template.Child()
    list_tasks = Gtk.Template.Child()
    pop_tasks = Gtk.Template.Child()
    headerbar = Gtk.Template.Child()
    # endregion

    # Common variables
    previous_page = ""
    default_settings = Gtk.Settings.get_default()
    settings = Gio.Settings.new(APP_ID)
    argument_executed = False

    def __init__(self, arg_exe, arg_bottle, arg_passed, **kwargs):
        super().__init__(**kwargs)

        self.utils_conn = ConnectionUtils(self)
        self.manager = None
        self.arg_bottle = arg_bottle
        self.arg_exe = arg_exe

        # Set night theme according to user settings
        if self.settings.get_boolean("dark-theme"):
            manager = Adw.StyleManager.get_default()
            manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

        # Set Library view according to user settings
        if self.settings.get_boolean("experiments-library"):
            self.btn_library.set_visible(True)

        # Validate arg_exe extension
        if not str(arg_exe).endswith(EXECUTABLE_EXTS):
            self.arg_exe = None

        if arg_bottle:
            self.manager = Manager(self)
            if arg_bottle.lower() in self.manager.local_bottles.keys():
                '''
                If Bottles was started with a bottle and an executable as
                arguments, then the executable will be run in the bottle.
                '''
                bottle_config = self.manager.local_bottles[arg_bottle]
                arg_passed = arg_passed or ""
                if self.arg_exe:
                    executor = WineExecutor(
                        bottle_config,
                        exec_path=self.arg_exe,
                        args=arg_passed
                    )
                    executor.run_cli()
                    self.proper_close()

        # Loading view
        self.page_loading = LoadingView()

        # Populate stack
        self.stack_main.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack_main.set_transition_duration(ANIM_DURATION)
        self.stack_main.add_titled(
            child=self.page_loading,
            name="page_loading",
            title=_("Loading...")
        )

        # Add the main stack to the main grid
        self.grid_main.attach(self.stack_main, 0, 1, 1, 1)

        # Signal connections
        self.btn_back.connect("clicked", self.go_back)
        self.btn_add.connect("clicked", self.show_add_view, self.arg_exe)
        self.btn_about.connect("clicked", self.show_about_dialog)
        self.btn_support.connect("clicked", self.open_url, FUNDING_URL)
        self.btn_docs.connect("clicked", self.open_url, DOC_URL)
        self.btn_forum.connect("clicked", self.open_url, FORUMS_URL)
        self.btn_preferences.connect("clicked", self.show_prefs_view)
        self.btn_importer.connect("clicked", self.show_importer_view)
        self.btn_library.connect('clicked', self.show_library_view)
        self.btn_noconnection.connect("clicked", self.check_for_connection)
        self.btn_health.connect("clicked", self.show_health_view)
        self.stack_main.connect('notify::visible-child', self.on_page_changed)
        self.btn_operations.connect('activate', self.on_operations_toggled)

        self.__on_start()

    def on_page_changed(self, stack, param):
        """
        When the user changes the page, update the window title
        according to the page.
        """
        page = self.stack_main.get_visible_child_name()

        if page not in ["page_details", "page_importer"]:
            self.set_actions(None)

        if page == "page_details":
            self.set_title(_("Bottle Details"))
        elif page == "page_list":
            self.set_title(_("Bottles"))
        elif page == "page_importer":
            self.set_title(_("Importer"))
            self.set_actions(self.page_importer.actions)
        elif page == "page_library":
            self.set_title(_("Your Library"))
        elif page == "page_loading":
            self.set_title(_("Loading..."))

    def update_library(self):
        GLib.idle_add(self.page_library.update)

    def on_operations_toggled(self, widget):
        if not self.list_tasks.get_first_child():
            widget.set_visible(False)

    def set_title(self, title, subtitle: str = ""):
        self.headerbar.set_title_widget(Gtk.Label.new(title))
        # self.headerbar.set_subtitle(subtitle)  TODO: Implement subtitle

    def set_actions(self, widget: Gtk.Widget = None):
        """
        This function is used to set the actions buttons in the headerbar.
        """
        while self.box_actions.get_first_child():
            self.box_actions.remove(self.box_actions.get_first_child())

        if widget:
            self.box_actions.append(widget)

    def check_for_connection(self, status):
        """
        This method checks if the client has an internet connection.
        If true, the manager checks will be performed, unlocking all the
        features locked for no internet connection.
        """
        if self.utils_conn.check_connection():
            self.manager.checks(install_latest=False, first_run=True)

    def toggle_btn_noconnection(self, status):
        GLib.idle_add(self.btn_noconnection.set_visible, status)

    def __on_start(self):
        """
        This method is called before the window is shown. This check if there
        is at least one local runner installed. If not, the user will be
        prompted with the onboard dialog.
        """
        def set_manager(result, error=None):
            self.manager = result

            tmp_runners = [
                x for x in self.manager.runners_available if not x.startswith('sys-')
            ]
            if len(tmp_runners) == 0:
                self.show_onboard_view()

            # Pages
            self.page_details = DetailsView(self)
            self.page_list = ListView(self, arg_bottle=self.arg_bottle, arg_exe=self.arg_exe)
            self.page_importer = ImporterView(self)
            self.page_library = LibraryView(self)

            self.stack_main.add_titled(
                child=self.page_details,
                name="page_details",
                title=_("Bottle details")
            )
            self.stack_main.add_titled(
                child=self.page_list,
                name="page_list",
                title=_("Bottles")
            )
            self.stack_main.add_titled(
                child=self.page_importer,
                name="page_importer",
                title=_("Importer")
            )
            self.stack_main.add_titled(
                child=self.page_library,
                name="page_library",
                title=_("Your library")
            )
            self.stack_main.set_visible_child_name("page_list")
            self.lock_ui(False)
            if Paths.custom_bottles_path_err:
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text=_("The custom bottles path was not found. "
                      "Please, check the path in Preferences.\n"
                      "Fallbacking to the default path; "
                      "no bottles from that path will be listed!")
                )
                dialog.run()
                dialog.destroy()

            if self.arg_exe and not self.arg_bottle:
                '''
                If Bottles was started with an executable as argument, without
                a bottle, the user will be prompted to select a bottle from the
                bottles list.
                '''
                self.show_list_view()
            self.arg_exe = None

        def get_manager(window):
            mng = Manager(window)
            return mng

        self.show_loading_view()
        RunAsync(get_manager, callback=set_manager, window=self)

        self.check_crash_log()

    def set_previous_page_status(self):
        """
        This method set the previous page status according to the
        current page, so that the previous page is correctly
        selected when the user goes back to the previous page.
        """
        self.previous_page = self.stack_main.get_visible_child_name()
        self.btn_add.set_visible(False)
        self.btn_menu.set_visible(False)
        self.btn_back.set_visible(True)

    def go_back(self, widget=False):
        """
        This method is called when the user presses the back button.
        It will toggle some widget visibility and show the previous
        page (previous_page).
        """
        self.toggle_selection_mode(False)

        for w in [self.btn_add, self.btn_menu]:
            w.set_visible(True)

        self.stack_main.set_visible_child_name(self.previous_page)

    def show_health_view(self, _widget):
        """
        This method is called when the user presses the health button.
        It will show the health view.
        """
        def show_journal_view(_widget):
            JournalDialog()

        ht = HealthChecker().get_results(plain=True)
        SourceDialog(
            parent=self,
            title=_("Health check"),
            message=ht,
            buttons=[{
                "callback": show_journal_view,
                "icon": "document-open-recent-symbolic",
                "tooltip": _("Journal browser")
            }]
        )

    def show_details_view(self, widget=False, config=dict):
        self.set_previous_page_status()
        self.page_details.set_config(config)
        self.stack_main.set_visible_child_name("page_details")
        self.page_details.set_visible_child_name("bottle")

    def show_loading_view(self, widget=False):
        self.lock_ui()
        self.stack_main.set_visible_child_name("page_loading")

    def show_onboard_view(self, widget=False):
        onboard_window = OnboardDialog(self)
        onboard_window.present()

    def show_add_view(self, widget=False, arg_exe=None):
        if not self.argument_executed:
            self.argument_executed = True
            new_window = NewView(self, self.arg_exe)
        else:
            new_window = NewView(self)
        new_window.present()

    def show_list_view(self, widget=False):
        self.stack_main.set_visible_child_name("page_list")

    def show_importer_view(self, widget=False):
        self.set_previous_page_status()
        self.stack_main.set_visible_child_name("page_importer")

    def show_library_view(self, widget=False):
        self.set_previous_page_status()
        self.stack_main.set_visible_child_name("page_library")

    def show_prefs_view(self, widget=False, view=0):
        preferences_window = PreferencesWindow(self)
        preferences_window.present()

    def show_download_preferences_view(self, widget=False):
        self.show_prefs_view(widget, view=1)

    def show_runners_preferences_view(self, widget=False):
        self.show_prefs_view(widget, view=2)

    def check_crash_log(self):
        xdg_data_home = os.environ.get("XDG_DATA_HOME", f"{Path.home()}/.local/share")
        log_path = f"{xdg_data_home}/bottles/crash.log"
        crash_log = False

        try:
            with open(log_path, "r") as log_file:
                crash_log = log_file.readlines()
                os.remove(log_path)

            if crash_log:
                CrashReportDialog(self, crash_log)
        except FileNotFoundError:
            pass

    def check_notifications(self):
        if not self.utils_conn.check_connection():
            return

        messages = NotificationsManager().messages
        if len(messages) > 0:
            for message in messages:
                entry = MessageEntry(
                    nid=message["id"],
                    title=message["title"],
                    body=message["body"],
                    url=message["url"],
                    message_type=message["type"],
                )
                entry.set_visible(True)
                self.list_notifications.append(entry)

            self.btn_notifications.set_visible(True)

    def toggle_selection_mode(self, status: bool = True):
        context = self.headerbar.get_style_context()
        if status:
            context.add_class("selection-mode")
        else:
            context.remove_class("selection-mode")

    def lock_ui(self, status: bool = True):
        for w in [
            self.btn_add,
            self.btn_menu,
            self.btn_noconnection
        ]:
            w.set_sensitive(not status)

    @staticmethod
    def proper_close():
        """Properly close Bottles"""
        quit()

    @staticmethod
    def show_about_dialog(widget):
        AboutDialog().run()

    @staticmethod
    def open_url(widget, url):
        webbrowser.open_new_tab(url)
