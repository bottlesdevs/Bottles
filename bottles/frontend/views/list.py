# list.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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
from gettext import ngettext

from gi.repository import Adw, GLib, Gtk, Xdp

from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.state import EventManager, Events, SignalManager, Signals
from bottles.backend.utils.threading import RunAsync
from bottles.backend.wine.executor import WineExecutor
from bottles.frontend.params import APP_ID
from bottles.frontend.utils.filters import add_all_filters, add_executable_filters
from bottles.frontend.utils.sandbox_guard import guard_sandbox_launch
from bottles.frontend.utils.umu import UmuFrontendProvider
from bottles.frontend.widgets.umu import UmuPrefixRow


def _bottle_order_id(config: BottleConfig) -> str:
    group = "steam" if config.Environment == "Steam" else "bottle"
    return f"{group}:{config.Path}"


def _ordered_bottles(configs, configured_order):
    positions = {bottle_id: index for index, bottle_id in enumerate(configured_order)}
    fallback = len(positions)
    return sorted(
        configs, key=lambda config: positions.get(_bottle_order_id(config), fallback)
    )


def _replace_group_order(configured_order, previous_order, new_order):
    replacements = iter(new_order)
    previous = set(previous_order)
    result = [
        next(replacements) if item in previous else item for item in configured_order
    ]
    result.extend(replacements)
    return result


@Gtk.Template(resource_path="/com/usebottles/bottles/bottle-row.ui")
class BottlesBottleRow(Adw.ActionRow):
    __gtype_name__ = "BottlesBottleRow"

    Adw.init()

    # region Widgets
    button_run = Gtk.Template.Child()
    button_order = Gtk.Template.Child()
    button_move_top = Gtk.Template.Child()
    button_move_up = Gtk.Template.Child()
    button_move_down = Gtk.Template.Child()
    button_move_bottom = Gtk.Template.Child()
    wrap_box = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config: BottleConfig, reorder_callback=None, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.reorder_callback = reorder_callback

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
        self.button_move_top.connect("clicked", self.__reorder, "top")
        self.button_move_up.connect("clicked", self.__reorder, "up")
        self.button_move_down.connect("clicked", self.__reorder, "down")
        self.button_move_bottom.connect("clicked", self.__reorder, "bottom")

        # populate widgets
        self.set_title(self.config.Name)
        if self.window.settings.get_boolean("update-date"):
            self.set_subtitle(update_date)

        self.wrap_box.append(Gtk.Label.new(self.config.Environment))

        # Set tooltip text
        self.button_run.set_tooltip_text(_(f"Run executable in “{self.config.Name}”"))

    def __reorder(self, _button, position):
        self.reorder_callback(self, position)

    def set_reorder_state(self, can_move_up, can_move_down, visible):
        self.button_order.set_visible(visible)
        self.button_move_top.set_sensitive(can_move_up)
        self.button_move_up.set_sensitive(can_move_up)
        self.button_move_down.set_sensitive(can_move_down)
        self.button_move_bottom.set_sensitive(can_move_down)

    def run_executable(self, *_args):
        """Display file dialog for executable"""
        if not Xdp.Portal.running_under_sandbox():
            return

        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            path = dialog.get_file().get_path()

            def proceed(sandbox_override, run_path):
                self.window.show_toast(
                    _("Launching “{0}” in “{1}”…").format(
                        dialog.get_file().get_basename(), self.config.Name
                    )
                )
                _executor = WineExecutor(
                    self.config, exec_path=run_path, sandbox_override=sandbox_override
                )
                RunAsync(_executor.run)

            guard_sandbox_launch(self.window, self.config, path, proceed)

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
        self.window.page_details.view_preferences.update_combo_components()
        self.window.show_details_view(config=config)

    def disable(self):
        self.window.go_back()
        self.set_visible(False)


@Gtk.Template(resource_path="/com/usebottles/bottles/list.ui")
class BottleView(Adw.Bin):
    __gtype_name__ = "BottleView"
    __bottles = {}

    # region Widgets
    list_bottles = Gtk.Template.Child()
    list_umu = Gtk.Template.Child()
    list_steam = Gtk.Template.Child()
    group_bottles = Gtk.Template.Child()
    group_umu = Gtk.Template.Child()
    group_steam = Gtk.Template.Child()
    pref_page = Gtk.Template.Child()
    bottle_status = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()
    entry_search = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    no_bottles_found = Gtk.Template.Child()
    update_banner = Gtk.Template.Child()

    # endregion

    def __init__(self, window, arg_bottle=None, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.arg_bottle = arg_bottle
        self.umu_provider = UmuFrontendProvider.from_backend(window.manager)

        # connect signals
        self.btn_create.connect("clicked", self.window.show_add_view)
        self.entry_search.connect("changed", self.__search_bottles)
        self.update_banner.connect("button-clicked", self.__show_bulk_update)

        # backend signals
        SignalManager.connect(
            Signals.ManagerLocalBottlesLoaded, self.update_bottles_list
        )

        self.bottle_status.set_icon_name(APP_ID)

        self.update_bottles_list()

    def __search_bottles(self, widget, event=None, data=None):
        """
        This function search in the list of bottles the
        text written in the search entry.
        """
        terms = widget.get_text()
        self.list_bottles.set_filter_func(self.__filter_bottles, terms)
        self.list_umu.set_filter_func(self.__filter_bottles, terms)
        self.list_steam.set_filter_func(self.__filter_bottles, terms)
        self.__update_empty_state(terms)

    @staticmethod
    def __filter_bottles(row, terms=None):
        text = row.get_title().lower()
        return terms.lower() in text

    def __update_empty_state(self, terms):
        has_bottles = bool(self.__bottles)
        has_matches = any(
            self.__filter_bottles(row, terms) for row in self.__bottles.values()
        )
        show_umu_actions = self.umu_provider.available and not terms
        self.pref_page.set_visible(has_matches or show_umu_actions)
        self.bottle_status.set_visible(not has_bottles and not show_umu_actions)
        self.no_bottles_found.set_visible(bool(terms) and not has_matches)

    def update_bottles_list(self, *args, refresh_updates=True) -> None:
        self.__bottles = {}
        while self.list_bottles.get_first_child():
            self.list_bottles.remove(self.list_bottles.get_first_child())

        while self.list_steam.get_first_child():
            self.list_steam.remove(self.list_steam.get_first_child())

        while self.list_umu.get_first_child():
            self.list_umu.remove(self.list_umu.get_first_child())

        local_bottles = self.window.manager.local_bottles

        configured_order = self.window.settings.get_strv("bottle-order")
        configs = _ordered_bottles(list(local_bottles.values()), configured_order)

        for config in configs:
            _entry = BottlesBottleRow(self.window, config, self.__reorder_bottle)
            self.__bottles[config.Path] = _entry

            if config.Environment != "Steam":
                self.list_bottles.append(_entry)
            else:
                self.list_steam.append(_entry)

        for entry in self.umu_provider.list_prefixes():
            callback = (
                self.window.show_umu_detected_prefix
                if entry.get("detected")
                else self.window.show_umu_game_settings
            )
            row = UmuPrefixRow(entry, callback)
            self.__bottles[entry["id"]] = row
            self.list_umu.append(row)

        has_umu_prefixes = self.list_umu.get_first_child() is not None
        if self.umu_provider.available and not has_umu_prefixes:
            self.list_umu.append(self.__build_umu_empty_row())

        has_local_bottles = self.list_bottles.get_first_child() is not None
        has_steam_prefixes = self.list_steam.get_first_child() is not None
        self.group_bottles.set_visible(has_local_bottles)
        self.group_umu.set_visible(self.umu_provider.available)
        self.group_steam.set_visible(has_steam_prefixes)
        self.group_bottles.set_title(
            _("Your Bottles") if has_umu_prefixes or has_steam_prefixes else ""
        )

        self.__update_empty_state(self.entry_search.get_text())
        self.__update_reorder_states(configs)

        if refresh_updates:
            self.update_component_updates_banner()

    def __build_umu_empty_row(self):
        launcher_available = self.window.manager.get_umu_installation() is not None
        row = Adw.ActionRow(
            title=_("No UMU Prefixes Yet"),
            subtitle=(
                _("Install a Windows game to create one.")
                if launcher_available
                else _("Configure the UMU launcher in Preferences first.")
            ),
        )
        actions = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)

        install = Gtk.Button()
        install.set_child(
            Adw.ButtonContent(
                icon_name="system-software-install-symbolic",
                label=_("Install Game"),
            )
        )
        install.add_css_class("suggested-action")
        install.connect("clicked", self.window.show_umu_search)
        actions.append(install)

        row.add_suffix(actions)
        return row

    def __reorder_bottle(self, row, position):
        configured_order = self.window.settings.get_strv("bottle-order")
        configs = _ordered_bottles(
            list(self.window.manager.local_bottles.values()), configured_order
        )
        group = [
            config
            for config in configs
            if (config.Environment == "Steam") == (row.config.Environment == "Steam")
        ]
        index = group.index(row.config)
        destinations = {
            "top": 0,
            "up": max(0, index - 1),
            "down": min(len(group) - 1, index + 1),
            "bottom": len(group) - 1,
        }
        destination = destinations[position]
        if destination == index:
            return

        previous_order = [_bottle_order_id(config) for config in group]
        group.insert(destination, group.pop(index))
        new_order = [_bottle_order_id(config) for config in group]
        self.window.settings.set_strv(
            "bottle-order",
            _replace_group_order(configured_order, previous_order, new_order),
        )
        self.update_bottles_list(refresh_updates=False)

    def __update_reorder_states(self, configs):
        for steam_group in (False, True):
            group = [
                config
                for config in configs
                if (config.Environment == "Steam") == steam_group
            ]
            for index, config in enumerate(group):
                self.__bottles[config.Path].set_reorder_state(
                    can_move_up=index > 0,
                    can_move_down=index < len(group) - 1,
                    visible=len(group) > 1,
                )

    def update_component_updates_banner(self) -> None:
        self.__update_banner_state(self.window.manager.local_bottles)

    def __update_banner_state(self, local_bottles) -> None:
        """Reveal the home banner when some bottles can update their components.

        The component catalog is fetched asynchronously, so wait for it to be
        organized in a worker thread before counting, then touch the banner
        back on the main loop.
        """
        configs = list(local_bottles.values())

        def count_updates():
            EventManager.wait(Events.ComponentsOrganizing)
            return sum(
                1
                for config in configs
                if self.window.manager.get_component_updates(config)
            )

        RunAsync(count_updates, callback=self.__apply_banner_state)

    def __apply_banner_state(self, count, error=False) -> None:
        if not count:
            self.update_banner.set_revealed(False)
            return

        self.update_banner.set_title(
            ngettext(
                "Component updates are available for {0} bottle.",
                "Component updates are available for {0} bottles.",
                count,
            ).format(count)
        )
        self.update_banner.set_revealed(True)

    def __show_bulk_update(self, *_args) -> None:
        from bottles.frontend.windows.bulkupdate import BottlesBulkUpdateDialog

        dialog = BottlesBulkUpdateDialog(self.window)
        dialog.present(self.window)

    def show_page(self, page: str) -> None:
        if config := self.window.manager.local_bottles.get(page):
            self.window.show_details_view(config=config)

    def disable_bottle(self, config):
        self.__bottles[config.Path].disable()
