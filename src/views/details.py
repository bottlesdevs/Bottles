# details.py
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

import re
from gettext import gettext as _
from gi.repository import Gtk, Handy

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.utils.common import open_doc_url
from bottles.widgets.page import PageRow

from bottles.views.bottle_details import BottleView
from bottles.views.bottle_installers import InstallersView
from bottles.views.bottle_dependencies import DependenciesView
from bottles.views.bottle_preferences import PreferencesView
from bottles.views.bottle_programs import ProgramsView
from bottles.views.bottle_versioning import VersioningView
from bottles.views.bottle_taskmanager import TaskManagerView

pages = {}


@Gtk.Template(resource_path='/com/usebottles/bottles/details.ui')
class DetailsView(Handy.Leaflet):
    __gtype_name__ = 'Details'

    # region Widgets
    list_pages = Gtk.Template.Child()
    stack_bottle = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config=None, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        if config is None:
            config = {}
        self.window = window
        self.manager = window.manager
        self.versioning_manager = window.manager.versioning_manager
        self.config = config

        self.view_bottle = BottleView(window, config)
        self.view_installers = InstallersView(window, config)
        self.view_dependencies = DependenciesView(window, config)
        self.view_preferences = PreferencesView(window, config)
        self.view_programs = ProgramsView(self, config)
        self.view_versioning = VersioningView(window, config)
        self.view_taskmanager = TaskManagerView(window, config)

        # region signals
        self.list_pages.connect('row-selected', self.__change_page)
        self.stack_bottle.connect('notify::visible-child', self.__on_page_change)
        # endregion

        # self.build_pages()

    def __on_page_change(self, *args):
        """
        Update headerbar title according to the current page.
        """
        global pages
        self.window.toggle_selection_mode(False)

        page = self.stack_bottle.get_visible_child_name()
        if page is None:
            page = "bottle"

        self.window.set_title(pages[page]['title'], pages[page]['description'])
        if page == "programs":
            self.window.set_actions(self.view_programs.actions)
        elif page == "dependencies":
            self.window.set_actions(self.view_dependencies.actions)
        elif page == "versioning":
            self.window.set_actions(self.view_versioning.actions)
        elif page == "installers":
            self.window.set_actions(self.view_installers.actions)
        elif page == "taskmanager":
            self.window.set_actions(self.view_taskmanager.actions)
        else:
            self.window.set_actions(None)

    def build_pages(self):
        """
        This function build the pages list according to the
        user settings (some pages are shown only if experimental
        features are enabled).
        """
        global pages
        pages = {
            "bottle": {
                "title": _("Details & Utilities"),
                "description": "",
            },
            "preferences": {
                "title": _("Preferences"),
                "description": "",
            },
            "dependencies": {
                "title": _("Dependencies"),
                "description": "",
            },
            "programs": {
                "title": _("Programs"),
                "description": _("Found in your bottle's Start menu.")
            },
            "versioning": {
                "title": _("Versioning"),
                "description": "",
            },
            "installers": {
                "title": _("Installers"),
                "description": "",
            },
            "taskmanager": {
                "title": _("Task manager"),
                "description": "",
            }
        }

        if self.config.get("Environment") == "Layered":
            del pages["dependencies"]
            del pages["preferences"]
            del pages["versioning"]
        elif self.config.get("Environment") == "Steam":
            del pages["programs"]
            del pages["versioning"]

        for w in self.list_pages.get_children():
            w.destroy()

        for p in pages:
            self.list_pages.add(PageRow(p, pages[p]))

        self.stack_bottle.add_named(self.view_bottle, "bottle")
        self.stack_bottle.add_named(self.view_preferences, "preferences")
        self.stack_bottle.add_named(self.view_dependencies, "dependencies")
        self.stack_bottle.add_named(self.view_programs, "programs")
        self.stack_bottle.add_named(self.view_versioning, "versioning")
        self.stack_bottle.add_named(self.view_installers, "installers")
        self.stack_bottle.add_named(self.view_taskmanager, "taskmanager")

    def __change_page(self, widget, row):
        """
        This function try to change the page based on user choice, if
        the page is not available, it will show the "bottle" page.
        """
        try:
            self.stack_bottle.set_visible_child_name(row.page_name)
        except AttributeError:
            self.stack_bottle.set_visible_child_name("bottle")

    def set_config(self, config):
        """
        This function update widgets according to the bottle
        configuration. It also temporarily disable the functions
        connected to the widgets to avoid the bottle configuration
        to be updated during this process.
        """
        self.config = config

        # update widgets data with bottle configuration        
        self.view_bottle.set_config(config=config)
        self.view_preferences.set_config(config=config)
        self.view_taskmanager.set_config(config=config)
        self.view_dependencies.update(config=config)
        self.view_installers.update(config=config)
        self.view_versioning.update(config=config)
        self.view_programs.update(config=config)
        self.view_bottle.update_programs()

        self.build_pages()

    def update_programs(self, widget=None, config=None):
        if config:
            self.config = config
        self.view_bottle.update_programs(config=self.config)
        self.view_programs.update(config=self.config)
