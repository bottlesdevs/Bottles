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
import webbrowser

gi.require_version('Handy', '1')
gi.require_version('Notify', '0.7')

from gi.repository import Gtk, Gio, Notify, Handy

from .params import *
from .runner import BottlesRunner

from .pages.new import BottlesNew
from .pages.onboard import BottlesOnboard
from .pages.details import BottlesDetails
from .pages.list import BottlesList
from .pages.preferences import BottlesPreferences
from .pages.taskmanager import BottlesTaskManager
from .pages.importer import BottlesImporter
from .pages.dialog import BottlesAboutDialog

from .utils import UtilsConnection, UtilsLogger

logging = UtilsLogger()

@Gtk.Template(resource_path='/com/usebottles/bottles/window.ui')
class BottlesWindow(Handy.ApplicationWindow):
    __gtype_name__ = 'BottlesWindow'

    '''Get widgets from template'''
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
    btn_versioning = Gtk.Template.Child()
    btn_installers = Gtk.Template.Child()
    box_downloads = Gtk.Template.Child()
    pop_downloads = Gtk.Template.Child()
    squeezer = Gtk.Template.Child()
    view_switcher = Gtk.Template.Child()
    view_switcher_bar = Gtk.Template.Child()

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
        self.default_settings.set_property(
            "gtk-application-prefer-dark-theme",
            self.settings.get_boolean("dark-theme"))

        self.utils_conn = UtilsConnection(self)

        '''Runner instance'''
        self.runner = BottlesRunner(self)
        self.runner.check_runners_dir()

        '''Pages'''
        page_details = BottlesDetails(self)
        page_list = BottlesList(self, arg_executable)
        page_taskmanager = BottlesTaskManager(self)
        page_importer = BottlesImporter(self)

        '''Reusable variables'''
        self.page_list = page_list
        self.page_details = page_details
        self.page_taskmanager = page_taskmanager
        self.page_importer = page_importer

        '''Populate stack'''
        self.stack_main.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack_main.set_transition_duration(ANIM_DURATION)
        self.stack_main.add_titled(page_details, "page_details", _("Bottle details"))
        self.stack_main.add_titled(page_list, "page_list", _("Bottles"))
        self.stack_main.add_titled(page_taskmanager, "page_taskmanager", _("Task manager"))
        self.stack_main.add_titled(page_importer, "page_importer", _("Importer"))

        '''Populate grid'''
        self.grid_main.attach(self.stack_main, 0, 1, 1, 1)

        '''Signal connections'''
        self.btn_back.connect('pressed', self.go_back)
        self.btn_back.connect('activate', self.go_back)
        self.btn_add.connect('pressed', self.show_add_view)
        self.btn_about.connect('pressed', self.show_about_dialog)
        self.btn_docs.connect('pressed', self.open_docs_url)
        self.btn_preferences.connect('pressed', self.show_preferences_view)
        self.btn_taskmanager.connect('pressed', self.show_taskmanager_view)
        self.btn_importer.connect('pressed', self.show_importer_view)
        self.btn_noconnection.connect('pressed', self.check_for_connection)
        self.squeezer.connect('notify::visible-child', self.on_squeezer_notify)

        '''BottlesDetail signal connections'''
        self.btn_versioning.connect('pressed', self.page_details.show_versioning_view)
        self.btn_installers.connect('pressed', self.page_details.show_installers_view)

        '''If there is at least one page, show the bottles list'''
        self.stack_main.set_visible_child_name("page_list")

        '''Set widget status from settings'''
        self.btn_versioning.set_visible(self.settings.get_boolean("experiments-versioning"))
        self.btn_installers.set_visible(self.settings.get_boolean("experiments-installers"))

        '''Executed on last'''
        self.on_start()

        if arg_executable:
            if arg_executable.endswith(('.exe', '.msi', '.bat'))
                self.show_list_view()

        '''Toggle view_switcher_bar by window size'''
        self.on_squeezer_notify(widget=self.squeezer)

        arg_executable = False
        logging.info(_("Bottles Started!"))

    def on_squeezer_notify(self, widget, event=False):
        '''TODO: this is used for responsive and doesn't work at this time'''
        child = widget.get_visible_child()
        self.view_switcher_bar.set_reveal(child != self.view_switcher)

    def hide_view_switcher(self):
        self.view_switcher.set_visible(False)
        self.view_switcher_bar.set_visible(False)

    def show_view_switcher(self, stack):
        self.view_switcher.set_stack(stack)
        self.view_switcher.set_visible(True)
        self.view_switcher_bar.set_visible(True)
        self.view_switcher_bar.set_stack(stack)

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
            self.show_onboard_view()

    '''Toggle UI usability preventing user clicks'''
    def set_usable_ui(self, status):
        for widget in [self.btn_back,
                       self.btn_add,
                       self.btn_menu]:
            widget.set_sensitive(status)

    '''Send new notification'''
    def send_notification(self, title, text, image="", user_settings=True):
        if user_settings and self.settings.get_boolean("notifications") or not user_settings:
            notification = Notify.Notification.new(title, text, image)
            notification.show()

    '''Save pevious page for back button'''
    def set_previous_page_status(self):
        self.previous_page = self.stack_main.get_visible_child_name()
        self.btn_add.set_visible(False)
        self.btn_menu.set_visible(False)
        self.btn_back.set_visible(True)

    '''Open URLs'''
    @staticmethod
    def open_docs_url(widget):
        webbrowser.open_new_tab("https://docs.usebottles.com")

    '''Go back to previous page'''
    def go_back(self, widget=False):
        self.hide_view_switcher()

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
        self.show_view_switcher(self.page_details)
        self.stack_main.set_visible_child_name("page_details")
        self.page_details.set_visible_child_name("bottle")

    def show_onboard_view(self, widget=False):
        onboard_window = BottlesOnboard(self)
        onboard_window.present()

    def show_add_view(self, widget=False):
        new_window = BottlesNew(self)
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
        preferences_window = BottlesPreferences(self)
        preferences_window.present()

    def show_download_preferences_view(self, widget=False):
        self.show_preferences_view(widget, view=1)

    def show_runners_preferences_view(self, widget=False):
        self.show_preferences_view(widget, view=2)

    '''Show about dialog'''
    @staticmethod
    def show_about_dialog(widget):
        BottlesAboutDialog().show_all()
