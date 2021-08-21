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

from gi.repository import Gtk, Gio, Notify, Handy
from pathlib import Path

from .params import *
from .backend.manager import Manager
from .backend.runner import Runner

from .views.new import NewView
from .views.onboard import OnboardDialog
from .views.details import DetailsView
from .views.list import ListView
from .views.preferences import PreferencesWindow
from .views.taskmanager import TaskManagerView
from .views.importer import ImporterView
from .views.dialog import AboutDialog, CrashReportDialog

from .utils import UtilsConnection, UtilsLogger

logging = UtilsLogger()

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
    btn_downloads = Gtk.Template.Child()
    btn_menu = Gtk.Template.Child()
    btn_more = Gtk.Template.Child()
    btn_docs = Gtk.Template.Child()
    btn_taskmanager = Gtk.Template.Child()
    btn_importer = Gtk.Template.Child()
    btn_noconnection = Gtk.Template.Child()
    box_downloads = Gtk.Template.Child()
    pop_downloads = Gtk.Template.Child()
    # endregion

    # Common variables
    previous_page = ""
    default_settings = Gtk.Settings.get_default()
    settings = Gio.Settings.new(APP_ID)
    argument_executed = False

    # Notify instance
    Notify.init(APP_ID)

    def __init__(self, arg_exe, arg_lnk, arg_bottle, **kwargs):
        super().__init__(**kwargs)

        self.default_settings.set_property(
            "gtk-application-prefer-dark-theme",
            self.settings.get_boolean("dark-theme"))

        # Validate arg_exe extension
        if arg_exe and not arg_exe.endswith(('.exe', '.msi', '.bat')):
            arg_exe = False

        # Validate arg_lnk extension
        if arg_lnk and not arg_lnk.endswith('.lnk'):
            arg_lnk = False

        self.utils_conn = UtilsConnection(self)

        # Runner instance
        self.runner = Manager(self)
        self.runner.check_runners_dir()

        # Run executable in a bottle
        if arg_exe and arg_bottle:
            if arg_bottle in self.runner.local_bottles.keys():
                bottle_configuration = self.runner.local_bottles[arg_bottle]
                Runner().run_executable(bottle_configuration,
                                           arg_exe)
                self.proper_close()

        # Run lnk in a bottle
        if arg_lnk and arg_bottle:
            if arg_bottle in self.runner.local_bottles.keys():
                bottle_configuration = self.runner.local_bottles[arg_bottle]
                Runner().run_lnk(bottle_configuration,
                                    arg_lnk)
                self.proper_close()

        # Pages
        page_details = DetailsView(self)
        page_list = ListView(self, arg_exe)
        page_taskmanager = TaskManagerView(self)
        page_importer = ImporterView(self)

        # Reusable variables
        self.page_list = page_list
        self.page_details = page_details
        self.page_taskmanager = page_taskmanager
        self.page_importer = page_importer

        # Populate stack
        self.stack_main.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack_main.set_transition_duration(ANIM_DURATION)
        self.stack_main.add_titled(page_details, "page_details", _("Bottle details"))
        self.stack_main.add_titled(page_list, "page_list", _("Bottles"))
        self.stack_main.add_titled(page_taskmanager, "page_taskmanager", _("Task manager"))
        self.stack_main.add_titled(page_importer, "page_importer", _("Importer"))

        # Populate grid
        self.grid_main.attach(self.stack_main, 0, 1, 1, 1)

        # Signal connections
        self.btn_back.connect('pressed', self.go_back)
        self.btn_back.connect('activate', self.go_back)
        self.btn_add.connect('pressed', self.show_add_view, arg_exe)
        self.btn_about.connect('pressed', self.show_about_dialog)
        self.btn_docs.connect('pressed', self.open_docs_url)
        self.btn_preferences.connect('pressed', self.show_preferences_view)
        self.btn_taskmanager.connect('pressed', self.show_taskmanager_view)
        self.btn_importer.connect('pressed', self.show_importer_view)
        self.btn_noconnection.connect('pressed', self.check_for_connection)
        # self.squeezer.connect('notify::visible-child', self.on_squeezer_notify)

        # If there is at least one page, show the bottles list
        self.stack_main.set_visible_child_name("page_list")

        # Executed on last
        self.on_start()

        if arg_exe:
            self.show_list_view()

        arg_exe = False
        logging.info(_("Bottles Started!"))

    def on_squeezer_notify(self, widget, event=False):
        # TODO: this is used for responsive and doesn't work at this time
        child = widget.get_visible_child()

    def check_for_connection(self, status):
        if self.utils_conn.check_connection():
            self.runner.checks()

    # Toggle btn_noconnection visibility
    def toggle_btn_noconnection(self, status):
        self.btn_noconnection.set_visible(status)

    # Execute before window shown
    def on_start(self):
        # Search for at least one local runner
        tmp_runners = [x for x in self.runner.runners_available if not x.startswith('sys-')]
        if len(tmp_runners) == 0:
            # Check for flatpak migration
            self.show_onboard_view()

        self.check_crash_log()

    # Send new notification
    def send_notification(self, title, text, image="", user_settings=True):
        if user_settings and self.settings.get_boolean("notifications") or not user_settings:
            notification = Notify.Notification.new(title, text, image)
            notification.show()

    # Save pevious page for back button
    def set_previous_page_status(self):
        self.previous_page = self.stack_main.get_visible_child_name()
        self.btn_add.set_visible(False)
        self.btn_menu.set_visible(False)
        self.btn_back.set_visible(True)

    # Open URLs
    @staticmethod
    def open_docs_url(widget):
        webbrowser.open_new_tab("https://docs.usebottles.com")

    # Go back to previous page
    def go_back(self, widget=False):

        for w in [self.btn_add, self.btn_menu]:
            w.set_visible(True)

        for w in [self.btn_back, self.btn_more]:
            w.set_visible(False)

        self.stack_main.set_visible_child_name(self.previous_page)

    def show_details_view(self, widget=False, configuration=dict):
        self.set_previous_page_status()

        if True in [w.get_visible() for w in self.box_more.get_children()]:
            self.btn_more.set_visible(True)
        self.page_details.set_configuration(configuration)
        self.stack_main.set_visible_child_name("page_details")
        self.page_details.set_visible_child_name("bottle")

    def show_onboard_view(self, widget=False):
        onboard_window = OnboardDialog(self)
        onboard_window.present()

    def show_add_view(self, widget=False, arg_exe=None, arg_lnk=None):
        if not self.argument_executed:
            self.argument_executed = True
            new_window = NewView(self, arg_exe, arg_lnk)
        else:
            new_window = NewView(self)
        new_window.present()

    def show_list_view(self, widget=False):
        self.stack_main.set_visible_child_name("page_list")

    def show_taskmanager_view(self, widget=False):
        self.set_previous_page_status()
        self.stack_main.set_visible_child_name("page_taskmanager")

    def show_importer_view(self, widget=False):
        self.set_previous_page_status()
        self.stack_main.set_visible_child_name("page_importer")

    def show_preferences_view(self, widget=False, view=0):
        preferences_window = PreferencesWindow(self)
        preferences_window.present()

    def show_download_preferences_view(self, widget=False):
        self.show_preferences_view(widget, view=1)

    def show_runners_preferences_view(self, widget=False):
        self.show_preferences_view(widget, view=2)

    def check_crash_log(self):
        log_path = f"{Path.home()}/.local/share/bottles/crash.log"
        if "FLATPAK_ID" in os.environ:
            log_path = f"{Path.home()}/.var/app/{os.environ['FLATPAK_ID']}/data/crash.log"
        crash_log = False

        try:
            with open(log_path, "r") as log_file:
                crash_log = log_file.readlines()
                os.remove(log_path)

            if crash_log:
                CrashReportDialog(self, crash_log)
        except FileNotFoundError:
            pass

    # Properly close Bottles
    @staticmethod
    def proper_close():
        time.sleep(1)
        quit()

    # Show about dialog
    @staticmethod
    def show_about_dialog(widget):
        AboutDialog().show_all()
