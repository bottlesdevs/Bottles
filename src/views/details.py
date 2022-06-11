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
from gi.repository import Gtk, GLib, Adw

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.utils.common import open_doc_url
from bottles.widgets.page import PageRow

from bottles.backend.models.result import Result
from bottles.backend.wine.wineserver import WineServer

from bottles.views.bottle_details import BottleView
from bottles.views.bottle_installers import InstallersView
from bottles.views.bottle_dependencies import DependenciesView
from bottles.views.bottle_preferences import PreferencesView
from bottles.views.bottle_programs import ProgramsView
from bottles.views.bottle_versioning import VersioningView
from bottles.views.bottle_taskmanager import TaskManagerView

from bottles.widgets.program import ProgramEntry

pages = {}


@Gtk.Template(resource_path='/com/usebottles/bottles/details.ui')
class DetailsView(Adw.Bin):
    __gtype_name__ = 'Details'

    # region Widgets
    leaflet = Gtk.Template.Child()
    list_pages = Gtk.Template.Child()
    stack_bottle = Gtk.Template.Child()
    sidebar_headerbar = Gtk.Template.Child()
    content_headerbar = Gtk.Template.Child()
    box_actions = Gtk.Template.Child()
    content_title = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    btn_back_sidebar = Gtk.Template.Child()
    btn_operations = Gtk.Template.Child()
    list_tasks = Gtk.Template.Child()
    pop_tasks = Gtk.Template.Child()
    spinner_tasks = Gtk.Template.Child()

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

        self.btn_back.connect("clicked", self.go_back)
        self.btn_back_sidebar.connect("clicked", self.go_back_sidebar)
        self.window.main_leaf.connect('notify::visible-child', self.unload_view)

        # region signals
        self.list_pages.connect('row-selected', self.__change_page)
        self.stack_bottle.connect('notify::visible-child', self.__on_page_change)
        self.btn_operations.connect('activate', self.__on_operations_toggled)
        self.btn_operations.connect('notify::visible', self.__spin_tasks_toggle)
        self.leaflet.connect('notify::folded', self.__on_leaflet_folded)
        # endregion

        # self.build_pages()

    def set_title(self, title, subtitle: str = ""):
        self.content_title.set_title(title)
        self.content_title.set_subtitle(subtitle)

    def __on_leaflet_folded(self, widget, *args):
        folded = widget.get_folded()
        self.sidebar_headerbar.set_show_end_title_buttons(folded)
        self.btn_back_sidebar.set_visible(folded)

    def __on_page_change(self, *args):
        """
        Update headerbar title according to the current page.
        """
        global pages
        self.window.toggle_selection_mode(False)
        page = self.stack_bottle.get_visible_child_name()

        if page is None:
            page = "bottle"

        self.set_title(pages[page]['title'], pages[page]['description'])
        if page in ["bottle", None]:
            self.set_actions(self.view_bottle.actions)
        elif page == "programs":
            self.set_actions(self.view_programs.actions)
        elif page == "dependencies":
            self.set_actions(self.view_dependencies.actions)
        elif page == "versioning":
            self.set_actions(self.view_versioning.actions)
        elif page == "installers":
            self.set_actions(self.view_installers.actions)
        elif page == "taskmanager":
            self.set_actions(self.view_taskmanager.actions)
        else:
            self.set_actions(None)

    def set_visible_child_name(self, name):
        self.stack_bottle.set_visible_child_name(name)

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

        while self.list_pages.get_first_child():
            self.list_pages.remove(self.list_pages.get_first_child())

        for p in pages:
            self.list_pages.append(PageRow(p, pages[p]))

        self.stack_bottle.add_named(self.view_bottle, "bottle")
        self.stack_bottle.add_named(self.view_preferences, "preferences")
        self.stack_bottle.add_named(self.view_dependencies, "dependencies")
        self.stack_bottle.add_named(self.view_programs, "programs")
        self.stack_bottle.add_named(self.view_versioning, "versioning")
        self.stack_bottle.add_named(self.view_installers, "installers")
        self.stack_bottle.add_named(self.view_taskmanager, "taskmanager")

        self.set_actions(self.view_bottle.actions)
        self.list_pages.select_row(self.list_pages.get_first_child())

    def __change_page(self, widget, row):
        """
        This function try to change the page based on user choice, if
        the page is not available, it will show the "bottle" page.
        """
        try:
            self.stack_bottle.set_visible_child_name(row.page_name)
            self.leaflet.navigate(Adw.NavigationDirection.FORWARD)
        except:
            pass

    def set_actions(self, widget: Gtk.Widget = None):
        """
            This function is used to set the actions buttons in the headerbar.
            """
        while self.box_actions.get_first_child():
            self.box_actions.remove(self.box_actions.get_first_child())

        if widget:
            self.box_actions.append(widget)

    def set_config(self, config, rebuild_pages=True):
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
        self.view_programs.set_config(config=config)
        self.view_dependencies.update(config=config)  # TODO: cause slow down
        self.view_installers.update(config=config)
        self.view_versioning.update(config=config)
        self.update_programs()

        if rebuild_pages:
            self.build_pages()

    def update_programs(self, config=None):
        """
        This function update the programs lists. The list in the
        details' page is limited to 5 items.
        """
        if config:
            self.config = config

        GLib.idle_add(self.view_bottle.empty_list)
        GLib.idle_add(self.view_programs.empty_list)

        self.view_bottle.group_programs.set_sensitive(False)
        self.view_programs.group_programs.set_sensitive(False)

        def new_program(_program, check_boot=None, is_steam=False, to_home=False, wineserver_status=False):
            if check_boot is None:
                check_boot = wineserver_status

            if to_home:
                self.view_bottle.add_program(ProgramEntry(
                    self.window,
                    self.config,
                    _program,
                    is_steam=is_steam,
                    check_boot=check_boot,
                ))
            self.view_programs.add_program(ProgramEntry(
                self.window,
                self.config,
                _program,
                is_steam=is_steam,
                check_boot=check_boot,
            ))

        def callback(result, error=False):
            row_no_programs = self.view_bottle.row_no_programs
            handled = result.data.get("handled")

            handled_h = handled[0] == 0
            handled_p = handled[1] == 0

            if handled_h:
                self.view_bottle.group_programs.add(row_no_programs)
            else:
                if row_no_programs.get_parent():
                    row_no_programs.get_parent().remove(row_no_programs)

            self.view_bottle.row_no_programs.set_visible(handled_h)
            self.view_bottle.group_programs.set_sensitive(not handled_h)
            self.view_programs.status_page.set_visible(handled_p)
            self.view_programs.group_programs.set_visible(not handled_p)
            self.view_programs.group_programs.set_sensitive(not handled_p)

        def process_programs():
            wineserver_status = WineServer(self.config).is_alive()
            programs = self.manager.get_programs(self.config)

            handled = [0, 0]  # home, programs

            if self.config.get("Environment") == "Steam":
                GLib.idle_add(new_program, {"name": self.config["Name"]}, None, True, True)
                handled[0] += 1
                handled[1] += 1

            for program in programs:
                if program.get("removed"):
                    if self.view_programs.show_removed:
                        GLib.idle_add(new_program, program, None, False, False, wineserver_status)
                        handled[1] += 1
                    continue
                GLib.idle_add(new_program, program, None, False, handled[0] < 5, wineserver_status)
                handled[0] += 1
                handled[1] += 1

            return Result(True, data={"handled": handled})

        RunAsync(process_programs, callback, )

    def __on_operations_toggled(self, widget):
        if not self.list_tasks.get_first_child():
            widget.set_visible(False)

    def __spin_tasks_toggle(self, widget, *args):
        if widget.get_visible():
            self.spinner_tasks.start()
            self.spinner_tasks.set_visible(True)
        else:
            self.spinner_tasks.stop()
            self.spinner_tasks.set_visible(False)

    def go_back(self, widget=False):
        self.window.main_leaf.navigate(Adw.NavigationDirection.BACK)

    def go_back_sidebar(self, *args):
        self.leaflet.navigate(Adw.NavigationDirection.BACK)

    def unload_view(self, *args):
        while self.stack_bottle.get_first_child():
            self.stack_bottle.remove(self.stack_bottle.get_first_child())
