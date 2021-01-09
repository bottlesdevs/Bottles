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

import gi

gi.require_version('Handy', '1')
gi.require_version('Notify', '0.7')

from gi.repository import Gtk, Gio, Notify, Handy

import webbrowser

from .params import *
from .runner import BottlesRunner

from .pages.add import BottlesAdd, BottlesAddDetails
from .pages.create import BottlesCreate
from .pages.details import BottlesDetails
from .pages.list import BottlesList
from .pages.preferences import BottlesPreferences
from .pages.taskmanager import BottlesTaskManager
from .pages.importer import BottlesImporter
from .pages.dialog import BottlesMessageDialog, BottlesAboutDialog

from .utils import UtilsConnection, UtilsLogger

logging = UtilsLogger()

@Gtk.Template(resource_path='/com/usebottles/bottles/window.ui')
class BottlesWindow(Handy.ApplicationWindow):
    __gtype_name__ = 'BottlesWindow'

    '''Get widgets from template'''
    grid_main = Gtk.Template.Child()
    stack_main = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    btn_add = Gtk.Template.Child()
    btn_list = Gtk.Template.Child()
    btn_preferences = Gtk.Template.Child()
    btn_download_preferences = Gtk.Template.Child()
    btn_about = Gtk.Template.Child()
    btn_downloads = Gtk.Template.Child()
    btn_menu = Gtk.Template.Child()
    btn_docs = Gtk.Template.Child()
    btn_translate = Gtk.Template.Child()
    btn_support = Gtk.Template.Child()
    btn_report = Gtk.Template.Child()
    btn_taskmanager = Gtk.Template.Child()
    btn_importer = Gtk.Template.Child()
    btn_noconnection = Gtk.Template.Child()
    switch_dark = Gtk.Template.Child()
    box_downloads = Gtk.Template.Child()
    pop_downloads = Gtk.Template.Child()

    '''Define environments and set first'''
    envs = [
        'Gaming',
        'Software',
        'Custom'
    ]
    env_active = envs[0]

    '''Common variables'''
    previous_page = ""
    default_settings = Gtk.Settings.get_default()
    settings = Gio.Settings.new(APP_ID)

    '''Notify instance'''
    Notify.init(APP_ID)

    def __init__(self, arg_executable, **kwargs):
        super().__init__(**kwargs)

        '''Custom title for branch'''
        #self.set_title("Bottles:feature-bottles-versioning")

        '''Init template'''
        self.init_template()
        self.default_settings.set_property("gtk-application-prefer-dark-theme",
                                           THEME_DARK)

        '''UtilsConnection instance'''
        self.utils_conn = UtilsConnection(self)

        '''Runner instance'''
        self.runner = BottlesRunner(self)

        '''Pages'''
        page_add = BottlesAdd(self)
        page_add_details = BottlesAddDetails(self)
        page_details = BottlesDetails(self)
        page_list = BottlesList(self, arg_executable)
        page_create = BottlesCreate(self)
        page_preferences = BottlesPreferences(self)
        page_taskmanager = BottlesTaskManager(self)
        page_importer = BottlesImporter(self)

        '''Reusable variables'''
        self.page_add_details = page_add_details
        self.page_create = page_create
        self.page_preferences = page_preferences
        self.page_list = page_list
        self.page_details = page_details
        self.page_taskmanager = page_taskmanager
        self.page_importer = page_importer

        '''Populate stack'''
        self.stack_main.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack_main.set_transition_duration(ANIM_DURATION)
        self.stack_main.add_titled(page_add, "page_add", _("New Bottle"))
        self.stack_main.add_titled(page_create, "page_create", _("Create Bottle"))
        self.stack_main.add_titled(page_add_details, "page_add_details", _("New Bottle details"))
        self.stack_main.add_titled(page_details, "page_details", _("Bottle details"))
        self.stack_main.add_titled(page_list, "page_list", _("Bottles"))
        self.stack_main.add_titled(page_preferences, "page_preferences", _("Preferences"))
        self.stack_main.add_titled(page_taskmanager, "page_taskmanager", _("Task manager"))
        self.stack_main.add_titled(page_importer, "page_importer", _("Importer"))

        '''Populate grid'''
        self.grid_main.attach(self.stack_main, 0, 1, 1, 1)

        '''Signal connections'''
        self.btn_back.connect('pressed', self.go_back)
        self.btn_back.connect('activate', self.go_back)
        self.btn_add.connect('pressed', self.show_add_view)
        self.btn_list.connect('pressed', self.show_list_view)
        self.btn_about.connect('pressed', self.show_about_dialog)
        self.btn_support.connect('pressed', self.open_support_url)
        self.btn_report.connect('pressed', self.open_report_url)
        self.btn_translate.connect('pressed', self.open_translate_url)
        self.btn_docs.connect('pressed', self.open_docs_url)
        self.btn_preferences.connect('pressed', self.show_preferences_view)
        self.btn_taskmanager.connect('pressed', self.show_taskmanager_view)
        self.btn_importer.connect('pressed', self.show_importer_view)
        self.btn_download_preferences.connect('pressed', self.show_download_preferences_view)
        self.btn_noconnection.connect('pressed', self.check_for_connection)
        self.switch_dark.connect('state-set', self.toggle_dark)

        '''Set widgets status from user settings'''
        self.switch_dark.set_active(self.settings.get_boolean("dark-theme"))

        '''Load startup view from user settings'''
        self.stack_main.set_visible_child_name(self.settings.get_string("startup-view"))

        '''Executed on last'''
        self.on_start()

        if arg_executable:
            self.show_list_view()

        arg_executable = False
        logging.info(_("Bottles Started!"))

    def check_for_connection(self, status):
        if self.utils_conn.check_connection():
            self.runner.checks()

    '''Toggle btn_noconnection visibility'''
    def toggle_btn_noconnection(self, status):
        self.btn_noconnection.set_visible(status)

    '''Execute before window shown'''
    def on_start(self):
        '''Search for at least one local runner'''
        if len(self.runner.runners_available) == 0:
            message = "There are no Runners in the system. "

            if self.utils_conn.check_connection():
                message += _("Proceed with the installation of the latest version?")
            else:
                message += _("But you don't seem to be connected to the internet and you won't be able to download a runner. Connect to the internet and confirm this message to begin the download.")

            dialog_checks = BottlesMessageDialog(parent=self,
                                          title=_("No runners found"),
                                          message=message)
            response = dialog_checks.run()

            if response == Gtk.ResponseType.OK:
                logging.info(_("OK status received"))

                '''Runner checks'''
                self.runner.checks()
                # TODO: do not install RC
            else:
                logging.info(_("Cancel status received"))

            dialog_checks.destroy()

    '''Toggle UI usability preventing user clicks'''
    def set_usable_ui(self, status):
        for widget in [self.btn_back,
                       self.btn_add,
                       self.btn_list,
                       self.btn_download_preferences,
                       self.btn_menu]:
            widget.set_sensitive(status)

    '''Send new notification'''
    def send_notification(self, title, text, image="", user_settings=True):
        if user_settings and self.settings.get_boolean("notifications") or not user_settings:
            notification = Notify.Notification.new(title, text, image)
            notification.show()

    '''Save pevious page for back button'''
    def set_previous_page_status(self):
        if self.previous_page != "page_preferences":
            current_page = self.stack_main.get_visible_child_name()
            if current_page in ["page_add_details", "page_create"]:
                current_page = "page_add"

            self.previous_page = current_page
            self.btn_add.set_visible(False)
            self.btn_list.set_visible(False)
            self.btn_menu.set_visible(False)
            self.btn_download_preferences.set_visible(False)
            self.btn_back.set_visible(True)

    '''Open URLs'''
    @staticmethod
    def open_translate_url(widget):
        webbrowser.open_new_tab("https://hosted.weblate.org/engage/bottles/")

    @staticmethod
    def open_docs_url(widget):
        webbrowser.open_new_tab("https://docs.usebottles.com")

    @staticmethod
    def open_support_url(widget):
        webbrowser.open_new_tab("https://liberapay.com/bottles")

    @staticmethod
    def open_report_url(widget):
        webbrowser.open_new_tab("https://github.com/bottlesdevs/Bottles/issues")

    '''Go back to previous page'''
    def go_back(self, widget):
        self.btn_add.set_visible(True)
        self.btn_list.set_visible(True)
        self.btn_menu.set_visible(True)
        self.btn_download_preferences.set_visible(True)
        self.btn_back.set_visible(False)
        self.stack_main.set_visible_child_name(self.previous_page)

    def show_add_view(self, widget=False):
        self.stack_main.set_visible_child_name("page_add")

    def show_list_view(self, widget=False):
        self.stack_main.set_visible_child_name("page_list")

    def show_taskmanager_view(self, widget=False):
        self.set_previous_page_status()
        self.stack_main.set_visible_child_name("page_taskmanager")

    def show_importer_view(self, widget=False):
        self.set_previous_page_status()
        self.stack_main.set_visible_child_name("page_importer")

    def show_preferences_view(self, widget=False, view=0):
        self.set_previous_page_status()
        self.page_preferences.notebook_preferences.set_current_page(view)
        self.stack_main.set_visible_child_name("page_preferences")

    def show_download_preferences_view(self, widget=False):
        self.show_preferences_view(widget, view=1)

    def show_runners_preferences_view(self, widget=False):
        self.show_preferences_view(widget, view=2)

    '''Show about dialog'''
    @staticmethod
    def show_about_dialog(widget):
        BottlesAboutDialog().show_all()

    '''Toggle dark mode and store in user settings'''
    def toggle_dark(self, widget, state):
        self.settings.set_boolean("dark-theme", state)
        self.default_settings.set_property("gtk-application-prefer-dark-theme",
                                            state)
