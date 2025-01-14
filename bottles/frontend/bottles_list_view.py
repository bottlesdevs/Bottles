# bottles_list_view.py
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

from datetime import datetime
from gettext import gettext as _

from gi.repository import Gtk, GLib, Adw, Xdp

from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.state import Signals, SignalManager
from bottles.backend.utils.threading import RunAsync
from bottles.backend.wine.executor import WineExecutor
from bottles.frontend.filters import add_executable_filters, add_all_filters
from bottles.frontend.params import APP_ID


@Gtk.Template(resource_path="/com/usebottles/bottles/bottle-row.ui")
class BottleRow(Adw.ActionRow):
    __gtype_name__ = "BottleRow"

    Adw.init()

    # region Widgets
    button_run = Gtk.Template.Child()
    wrap_box = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config: BottleConfig, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        # Format update date
        update_date = _("N/A")
        if self.config.Update_Date:
            try:
                temp_date = datetime.strptime(
                    self.config.Update_Date, "%Y-%m-%d %H:%M:%S.%f"
                )
                update_date = temp_date.strftime("%d %B, %Y %H:%M:%S")
            except ValueError:
                update_date = _("N/A")

        # Check runner type by name
        if self.config.Runner.startswith("lutris"):
            self.runner_type = "wine"
        else:
            self.runner_type = "proton"

        # connect signals
        self.connect("activated", self.show_details)
        self.button_run.connect("clicked", self.run_executable)

        # populate widgets
        self.set_title(self.config.Name)
        if self.window.settings.get_boolean("update-date"):
            self.set_subtitle(update_date)

        self.wrap_box.append(Gtk.Label.new(self.config.Environment))

        # Set tooltip text
        self.button_run.set_tooltip_text(_(f"Run executable in “{self.config.Name}”"))

    def run_executable(self, *_args):
        """Display file dialog for executable"""
        if not Xdp.Portal.running_under_sandbox():
            return

        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            self.window.show_toast(
                _("Launching “{0}” in “{1}”…").format(
                    dialog.get_file().get_basename(), self.config.Name
                )
            )

            path = dialog.get_file().get_path()
            _executor = WineExecutor(self.config, exec_path=path)
            RunAsync(_executor.run)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Executable"),
            action=Gtk.FileChooserAction.OPEN,
            parent=self.window,
            accept_label=_("Run"),
        )

        add_executable_filters(dialog)
        add_all_filters(dialog)
        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def show_details(self, widget=None, config=None):
        if config is None:
            config = self.config
        self.window.page_details.details_view_subpage.view_preferences.update_combo_components()
        self.window.show_details_view(config=config)

    def disable(self):
        self.window.go_back()
        self.set_visible(False)


@Gtk.Template(resource_path="/com/usebottles/bottles/bottles-list-view.ui")
class BottlesListView(Gtk.Stack):
    __gtype_name__ = "BottlesListView"
    __bottles = {}

    # region Widgets
    list_bottles = Gtk.Template.Child()
    list_steam = Gtk.Template.Child()
    group_bottles = Gtk.Template.Child()
    group_steam = Gtk.Template.Child()
    create_button = Gtk.Template.Child()

    # endregion

    def __init__(self, window, arg_bottle=None, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.arg_bottle = arg_bottle

        # connect signals
        self.create_button.connect("clicked", self.window.show_add_view)

        # backend signals
        SignalManager.connect(
            Signals.ManagerLocalBottlesLoaded, self.update_bottles_list
        )

        status_page = self.get_child_by_name("empty-page")
        status_page.set_icon_name(APP_ID)

        self.update_bottles_list()

    def update_bottles_list(self, *args) -> None:
        self.__bottles = {}
        while self.list_bottles.get_first_child():
            self.list_bottles.remove(self.list_bottles.get_first_child())

        while self.list_steam.get_first_child():
            self.list_steam.remove(self.list_steam.get_first_child())

        local_bottles = self.window.manager.local_bottles
        is_empty_local_bottles = len(local_bottles) == 0

        if is_empty_local_bottles:
            self.set_visible_child_name("empty-page")
            return

        self.set_visible_child_name("bottles-list-page")

        for name, config in local_bottles.items():
            _entry = BottleRow(self.window, config)
            self.__bottles[config.Path] = _entry

            if config.Environment != "Steam":
                self.list_bottles.append(_entry)
            else:
                self.list_steam.append(_entry)

            if self.list_steam.get_first_child() is None:
                self.group_steam.set_visible(False)
                self.group_bottles.set_title("")
            else:
                self.group_steam.set_visible(True)
                self.group_bottles.set_title(_("Your Bottles"))

    def show_page(self, page: str) -> None:
        if config := self.window.manager.local_bottles.get(page):
            self.window.show_details_view(config=config)

    def disable_bottle(self, config):
        self.__bottles[config.Path].disable()
