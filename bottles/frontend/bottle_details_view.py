# bottle_details_view.py
#
# Copyright 2025 The Bottles Contributors
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

from gi.repository import Gtk, Adw, GLib

from bottles.backend.managers.queue import QueueManager
from bottles.backend.models.config import BottleConfig

from bottles.backend.utils.threading import RunAsync
from bottles.frontend.gtk import GtkUtils
from bottles.frontend.bottle_details_page import BottleDetailsPage
from bottles.frontend.details_installers_view import DetailsInstallersView
from bottles.frontend.details_dependencies_view import DetailsDependenciesView
from bottles.frontend.details_preferences_page import DetailsPreferencesPage
from bottles.frontend.details_versioning_page import DetailsVersioningPage
from bottles.frontend.details_task_manager_view import DetailsTaskManagerView


@Gtk.Template(resource_path="/com/usebottles/bottles/bottle-details-view-subpage.ui")
class BottleDetailsViewSubpage(Adw.NavigationPage):
    __gtype_name__ = "BottleDetailsViewSubpage"

    spinner_tasks = Gtk.Template.Child()
    pop_tasks = Gtk.Template.Child()
    list_tasks = Gtk.Template.Child()
    btn_operations = Gtk.Template.Child()
    content_title = Gtk.Template.Child()
    box_actions = Gtk.Template.Child()
    content_headerbar = Gtk.Template.Child()
    stack_bottle = Gtk.Template.Child()

    # endregion

    def __init__(
        self, details_view, window, config: BottleConfig | None = None, **kwargs
    ):
        super().__init__(**kwargs)

        self.details_view = details_view
        self.window = window
        self.config = config

        self.btn_operations.connect("activate", self.__on_operations_toggled)
        self.btn_operations.connect("notify::visible", self.__spin_tasks_toggle)
        self.stack_bottle.connect("notify::visible-child", self.__on_page_change)

        RunAsync(self.build_pages)

    def __spin_tasks_toggle(self, widget, *_args):
        if widget.get_visible():
            self.spinner_tasks.start()
            self.spinner_tasks.set_visible(True)
        else:
            self.spinner_tasks.stop()
            self.spinner_tasks.set_visible(False)

    def __on_operations_toggled(self, widget):
        if not self.list_tasks.get_first_child():
            widget.set_visible(False)

    def set_title(self, title, subtitle: str = ""):
        """
        This function is used to set the title of the BottleDetailsView
        headerbar.
        """
        self.content_title.set_title(title)
        self.content_title.set_subtitle(subtitle)

    def set_actions(self, widget: Gtk.Widget = None):
        """
        This function is used to set the actions buttons in the headerbar.
        """
        while self.box_actions.get_first_child():
            self.box_actions.remove(self.box_actions.get_first_child())

        if widget:
            self.box_actions.append(widget)

    def unload_view(self, *_args):
        while self.stack_bottle.get_first_child():
            self.stack_bottle.remove(self.stack_bottle.get_first_child())

    def __on_page_change(self, *_args):
        """
        Update headerbar title according to the current page.
        """
        page = self.stack_bottle.get_visible_child_name()

        self.set_title(self.__pages[page]["title"], self.__pages[page]["description"])
        if page == "dependencies":
            self.set_actions(self.view_dependencies.actions)
            self.view_dependencies.update(config=self.config)
        elif page == "versioning":
            self.set_actions(self.view_versioning.actions)
        elif page == "installers":
            self.set_actions(self.view_installers.actions)
        elif page == "taskmanager":
            self.set_actions(self.view_taskmanager.actions)
        else:
            self.set_actions(None)

    def build_pages(self):
        """
        This function build the pages list according to the
        user settings (some pages are shown only if experimental
        features are enabled).
        """
        self.__pages = {
            "preferences": {
                "title": _("Settings"),
                "description": "",
            },
            "dependencies": {
                "title": _("Dependencies"),
                "description": "",
            },
            "versioning": {
                "title": _("Snapshots"),
                "description": "",
            },
            "installers": {
                "title": _("Installers"),
                "description": "",
            },
            "taskmanager": {
                "title": _("Task Manager"),
                "description": "",
            },
        }

        if self.config.Environment == "Steam":
            del self.__pages["versioning"]

        def ui_update():
            if self.view_bottle.get_parent() is None:
                self.details_view.default_view.append(self.view_bottle)

            self.stack_bottle.add_named(self.view_preferences, "preferences")
            self.stack_bottle.add_named(self.view_dependencies, "dependencies")
            self.stack_bottle.add_named(self.view_versioning, "versioning")
            self.stack_bottle.add_named(self.view_installers, "installers")
            self.stack_bottle.add_named(self.view_taskmanager, "taskmanager")

            if self.view_bottle.actions.get_parent() is None:
                self.set_actions(self.view_bottle.actions)

        GLib.idle_add(ui_update)


@Gtk.Template(resource_path="/com/usebottles/bottles/bottle-details-view.ui")
class BottleDetailsView(Adw.NavigationPage):
    """
    This class is the starting point for all the pages concerning the
    bottle (details, preferences, dependencies ..).
    """

    __gtype_name__ = "BottleDetailsView"
    __pages = {}

    # region Widgets
    default_view = Gtk.Template.Child()
    default_actions = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config: BottleConfig | None = None, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        if config is None:
            config = BottleConfig()

        self.window = window
        self.manager = window.manager
        self.versioning_manager = window.manager.versioning_manager
        self.config = config
        self.queue = QueueManager(add_fn=self.lock_back, end_fn=self.unlock_back)

        self.details_view_subpage = BottleDetailsViewSubpage(self, window, config)
        self.details_view_subpage.view_bottle = BottleDetailsPage(self, config)
        self.details_view_subpage.view_installers = DetailsInstallersView(self, config)
        self.details_view_subpage.view_dependencies = DetailsDependenciesView(
            self, config
        )
        self.details_view_subpage.view_preferences = DetailsPreferencesPage(
            self, config
        )
        self.details_view_subpage.view_versioning = DetailsVersioningPage(self, config)
        self.details_view_subpage.view_taskmanager = DetailsTaskManagerView(
            self, config
        )

        self.default_actions.append(self.details_view_subpage.view_bottle.actions)

    def set_config(self, config: BottleConfig):
        """
        This function update widgets according to the bottle
        configuration. It also temporarily disable the functions
        connected to the widgets to avoid the bottle configuration
        to be updated during this process.
        """
        self.config = config

        # update widgets data with bottle configuration
        self.details_view_subpage.view_bottle.set_config(config=config)
        self.details_view_subpage.view_preferences.set_config(config=config)
        self.details_view_subpage.view_taskmanager.set_config(config=config)
        self.details_view_subpage.view_installers.update(config=config)
        self.details_view_subpage.view_versioning.update(config=config)

    @GtkUtils.run_in_main_loop
    def lock_back(self): ...

    @GtkUtils.run_in_main_loop
    def unlock_back(self): ...

    def update_runner_label(self, runner: str):
        self.details_view_subpage.view_bottle.label_runner.set_text(runner)
