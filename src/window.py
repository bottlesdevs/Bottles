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
from gi.repository import Gtk, Gio, Handy
from pathlib import Path

from bottles.params import *  # pyright: reportMissingImports=false
from bottles.widgets.message import MessageEntry
from bottles.utils import UtilsConnection, Logger, RunAsync

from bottles.backend.health import HealthChecker
from bottles.backend.managers.manager import Manager
from bottles.backend.managers.notifications import NotificationsManager
from bottles.backend.wine.executor import WineExecutor

from bottles.views.new import NewView
from bottles.views.details import DetailsView
from bottles.views.list import ListView
from bottles.views.preferences import PreferencesWindow
from bottles.views.importer import ImporterView

from bottles.dialogs.crash import CrashReportDialog
from bottles.dialogs.generic import AboutDialog, SourceDialog
from bottles.dialogs.onboard import OnboardDialog

logging = Logger()


@Gtk.Template(resource_path='/com/usebottles/bottles/window.ui')
class MainWindow(Handy.ApplicationWindow):
    __gtype_name__ = 'MainWindow'

    # region Widgets
    grid_main = Gtk.Template.Child()
    stack_main = Gtk.Template.Child()
    box_more = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    btn_add = Gtk.Template.Child()
    btn_preferences = Gtk.Template.Child()
    btn_about = Gtk.Template.Child()
    btn_operations = Gtk.Template.Child()
    btn_notifications = Gtk.Template.Child()
    btn_menu = Gtk.Template.Child()
    btn_more = Gtk.Template.Child()
    btn_support = Gtk.Template.Child()
    btn_docs = Gtk.Template.Child()
    btn_forum = Gtk.Template.Child()
    btn_importer = Gtk.Template.Child()
    btn_noconnection = Gtk.Template.Child()
    btn_health = Gtk.Template.Child()
    box_actions = Gtk.Template.Child()
    list_tasks = Gtk.Template.Child()
    pop_tasks = Gtk.Template.Child()
    pop_notifications = Gtk.Template.Child()
    headerbar = Gtk.Template.Child()
    list_notifications = Gtk.Template.Child()
    # endregion

    # Common variables
    previous_page = ""
    default_settings = Gtk.Settings.get_default()
    settings = Gio.Settings.new(APP_ID)
    argument_executed = False

    def __init__(self, arg_exe, arg_bottle, arg_passed, **kwargs):
        super().__init__(**kwargs)

        self.utils_conn = UtilsConnection(self)
        self.manager = Manager(self)

        # Set night theme according to user settings
        self.default_settings.set_property(
            "gtk-application-prefer-dark-theme",
            self.settings.get_boolean("night-theme")
        )

        # Validate arg_exe extension
        if not str(arg_exe).endswith(EXECUTABLE_EXTS):
            arg_exe = False

        if arg_bottle and arg_bottle in self.manager.local_bottles.keys():
            '''
            If Bottles was started with a bottle and an executable as
            arguments, then the executable will be run in the bottle.
            '''
            bottle_config = self.manager.local_bottles[arg_bottle]
            arg_passed = arg_passed or ""
            if arg_exe:
                executor = WineExecutor(
                    bottle_config,
                    exec_path=arg_exe,
                    args=arg_passed
                )
                executor.run_cli()
                self.proper_close()

        # Pages
        page_details = DetailsView(self)
        page_list = ListView(self, arg_exe)
        page_importer = ImporterView(self)

        # Reusable variables
        self.page_list = page_list
        self.page_details = page_details
        self.page_importer = page_importer

        # Populate stack
        self.stack_main.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack_main.set_transition_duration(ANIM_DURATION)
        self.stack_main.add_titled(
            child=page_details,
            name="page_details",
            title=_("Bottle details")
        )
        self.stack_main.add_titled(
            child=page_list,
            name="page_list",
            title=_("Bottles")
        )
        self.stack_main.add_titled(
            child=page_importer,
            name="page_importer",
            title=_("Importer")
        )

        # Add the main stack to the main grid
        self.grid_main.attach(self.stack_main, 0, 1, 1, 1)

        # Signal connections
        self.btn_back.connect("clicked", self.go_back)
        self.btn_add.connect("clicked", self.show_add_view, arg_exe)
        self.btn_about.connect("clicked", self.show_about_dialog)
        self.btn_support.connect("clicked", self.open_url, FUNDING_URL)
        self.btn_docs.connect("clicked", self.open_url, DOC_URL)
        self.btn_forum.connect("clicked", self.open_url, FORUMS_URL)
        self.btn_preferences.connect("clicked", self.show_prefs_view)
        self.btn_importer.connect("clicked", self.show_importer_view)
        self.btn_noconnection.connect("clicked", self.check_for_connection)
        self.btn_health.connect("clicked", self.show_health_view)
        self.stack_main.connect('notify::visible-child', self.on_page_changed)
        self.btn_operations.connect('toggled', self.on_operations_toggled)

        # Set the bottles list page as the default page
        self.stack_main.set_visible_child_name("page_list")

        self.__on_start()

        if arg_exe:
            '''
            If Bottles was started with an executable as argument, without
            a bottle, the user will be prompted to select a bottle from the
            bottles list.
            '''
            self.show_list_view()

        arg_exe = False
        logging.info("Bottles Started!", )

    def on_page_changed(self, stack, param):
        '''
        When the user changes the page, update the window title
        according to the page.
        '''
        self.set_actions(None)
        page = self.stack_main.get_visible_child_name()
        if page == "page_details":
            self.set_title(_("Bottle details"))
        elif page == "page_list":
            self.set_title(_("Bottles"))
        elif page == "page_importer":
            self.set_title(_("Import & export"))

    def on_operations_toggled(self, widget):
        if len(self.list_tasks.get_children()) == 0:
            widget.set_visible(False)

    def set_title(self, title, subtitle: str = ""):
        self.headerbar.set_title(title)
        self.headerbar.set_subtitle(subtitle)

    def set_actions(self, widget: Gtk.Widget = False):
        '''
        This function is used to set the actions buttons in the headerbar.
        '''
        for w in self.box_actions.get_children():
            self.box_actions.remove(w)

        if widget:
            self.box_actions.add(widget)

    def check_for_connection(self, status):
        '''
        This method checks if the client has an internet connection.
        If true, the manager checks will be performed, unlocking all the
        features locked for no internet connection.
        '''
        if self.utils_conn.check_connection():
            self.manager.checks(install_latest=False, first_run=True)

    def toggle_btn_noconnection(self, status):
        self.btn_noconnection.set_visible(status)

    def __on_start(self):
        '''
        This method is called before the window is shown. This check if there
        is at least one local runner installed. If not, the user will be
        prompted with the onboard dialog.
        '''
        tmp_runners = [
            x for x in self.manager.runners_available if not x.startswith('sys-')
        ]
        if len(tmp_runners) == 0:
            self.show_onboard_view()

        self.check_crash_log()
        self.check_notifications()

    def send_notification(self, title, text, image="", ignore_user=True):
        '''
        This method is used to send a notification to the user using
        Gio.Notification. The notification is sent only if the
        user has enabled it in the settings. It is possibile to ignore the
        user settings by passing the argument ignore_user=False.
        '''
        if ignore_user or self.settings.get_boolean("notifications"):
            notification = Gio.Notification.new(title)
            notification.set_body(text)
            if image:
                icon = Gio.ThemedIcon.new(image)
                notification.set_icon(icon)

            self.props.application.send_notification(None, notification)

    def set_previous_page_status(self):
        '''
        This method set the previous page status according to the
        current page, so that the previous page is correctly
        selected when the user goes back to the previous page.
        '''
        self.previous_page = self.stack_main.get_visible_child_name()
        self.btn_add.set_visible(False)
        self.btn_menu.set_visible(False)
        self.btn_back.set_visible(True)

    def go_back(self, widget=False):
        '''
        This method is called when the user presses the back button.
        It will toggle some widget visibility and show the previous
        page (previous_page).
        '''
        self.toggle_selection_mode(False)

        for w in [self.btn_add, self.btn_menu]:
            w.set_visible(True)

        for w in [self.btn_back, self.btn_more]:
            w.set_visible(False)

        self.stack_main.set_visible_child_name(self.previous_page)

    def show_health_view(self, widget):
        '''
        This method is called when the user presses the health button.
        It will show the health view.
        '''
        ht = HealthChecker().get_results(plain=True)
        SourceDialog(
            parent=self,
            title=_("Health check"),
            message=ht,
        )

    def show_details_view(self, widget=False, config=dict):
        self.set_previous_page_status()

        if True in [w.get_visible() for w in self.box_more.get_children()]:
            self.btn_more.set_visible(True)
        self.page_details.set_config(config)
        self.stack_main.set_visible_child_name("page_details")
        self.page_details.set_visible_child_name("bottle")

    def show_onboard_view(self, widget=False):
        onboard_window = OnboardDialog(self)
        onboard_window.present()

    def show_add_view(self, widget=False, arg_exe=None):
        if not self.argument_executed:
            self.argument_executed = True
            new_window = NewView(self, arg_exe)
        else:
            new_window = NewView(self)
        new_window.present()

    def show_list_view(self, widget=False):
        self.stack_main.set_visible_child_name("page_list")

    def show_importer_view(self, widget=False):
        self.set_previous_page_status()
        self.stack_main.set_visible_child_name("page_importer")

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
                self.list_notifications.add(entry)

            self.btn_notifications.set_visible(True)

    def toggle_selection_mode(self, status: bool = True):
        context = self.headerbar.get_style_context()
        if status:
            context.add_class("selection-mode")
        else:
            context.remove_class("selection-mode")

    @staticmethod
    def proper_close():
        '''
	Properly close Bottles
        '''
        quit()

    @staticmethod
    def show_about_dialog(widget):
        AboutDialog().run()

    @staticmethod
    def open_url(widget, url):
        webbrowser.open_new_tab(url)
