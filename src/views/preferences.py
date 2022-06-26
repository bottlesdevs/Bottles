# preferences.py
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
from gettext import gettext as _
from gi.repository import Gtk, Adw

from bottles.widgets.component import ComponentEntry, ComponentExpander  # pyright: reportMissingImports=false
from bottles.dialogs.filechooser import FileChooser

from bottles.backend.managers.steam import SteamManager
from bottles.backend.managers.data import DataManager


@Gtk.Template(resource_path='/com/usebottles/bottles/preferences.ui')
class PreferencesWindow(Adw.PreferencesWindow):
    __gtype_name__ = 'PreferencesWindow'
    __registry = []

    # region Widgets
    switch_notifications = Gtk.Template.Child()
    switch_temp = Gtk.Template.Child()
    switch_release_candidate = Gtk.Template.Child()
    switch_steam = Gtk.Template.Child()
    switch_library = Gtk.Template.Child()
    switch_auto_close = Gtk.Template.Child()
    switch_update_date = Gtk.Template.Child()
    switch_steam_programs = Gtk.Template.Child()
    switch_epic_games = Gtk.Template.Child()
    list_winebridge = Gtk.Template.Child()
    list_runtimes = Gtk.Template.Child()
    list_runners = Gtk.Template.Child()
    list_dxvk = Gtk.Template.Child()
    list_vkd3d = Gtk.Template.Child()
    list_nvapi = Gtk.Template.Child()
    list_latencyflex = Gtk.Template.Child()
    action_prerelease = Gtk.Template.Child()
    action_bottles_path = Gtk.Template.Child()
    action_steam_proton = Gtk.Template.Child()
    btn_bottles_path = Gtk.Template.Child()
    btn_bottles_path_reset = Gtk.Template.Child()
    pref_core = Gtk.Template.Child()

    # endregion

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.settings = window.settings
        self.default_settings = window.default_settings
        self.manager = window.manager
        self.data = DataManager()

        if "FLATPAK_ID" in os.environ:
            self.remove(self.pref_core)

        bottles_path = self.data.get("custom_bottles_path")
        if bottles_path:
            self.action_bottles_path.set_subtitle(bottles_path)
            self.btn_bottles_path_reset.set_visible(True)

        # set widget defaults
        self.switch_notifications.set_active(self.settings.get_boolean("notifications"))
        self.switch_temp.set_active(self.settings.get_boolean("temp"))
        self.switch_release_candidate.set_active(self.settings.get_boolean("release-candidate"))
        self.switch_steam.set_active(self.settings.get_boolean("steam-proton-support"))
        self.switch_library.set_active(self.settings.get_boolean("experiments-library"))
        self.switch_auto_close.set_active(self.settings.get_boolean("auto-close-bottles"))
        self.switch_update_date.set_active(self.settings.get_boolean("update-date"))
        self.switch_steam_programs.set_active(self.settings.get_boolean("steam-programs"))
        self.switch_epic_games.set_active(self.settings.get_boolean("epic-games"))
        self.populate_runtimes_list()
        self.populate_winebridge_list()
        self.populate_runners_list()
        self.populate_dxvk_list()
        self.populate_vkd3d_list()
        self.populate_nvapi_list()
        self.populate_latencyflex_list()

        # connect signals
        self.switch_notifications.connect('state-set', self.__toggle_notify)
        self.switch_temp.connect('state-set', self.__toggle_temp)
        self.switch_release_candidate.connect('state-set', self.__toggle_rc)
        self.switch_steam.connect('state-set', self.__toggle_steam)
        self.switch_library.connect('state-set', self.__toggle_library)
        self.switch_auto_close.connect('state-set', self.__toggle_autoclose)
        self.switch_update_date.connect('state-set', self.__toggle_update_date)
        self.switch_steam_programs.connect('state-set', self.__toggle_steam_programs)
        self.switch_epic_games.connect('state-set', self.__toggle_epic_games)
        self.btn_bottles_path.connect('clicked', self.__choose_bottles_path)
        self.btn_bottles_path_reset.connect('clicked', self.__reset_bottles_path)

        if not SteamManager.is_steam_supported():
            self.switch_steam.set_sensitive(False)
            self.action_steam_proton.set_tooltip_text(
                _("Steam was not found or Bottles does not have enough permissions.\
Visit https://docs.usebottles.com/flatpak/cant-enable-steam-proton-manager"))

    def __toggle_update_date(self, widget, state):
        self.settings.set_boolean("update-date", state)
        self.window.page_list.update_bottles()

    def __toggle_steam_programs(self, widget, state):
        self.settings.set_boolean("steam-programs", state)

    def __toggle_epic_games(self, widget, state):
        self.settings.set_boolean("epic-games", state)

    def __toggle_notify(self, widget, state):
        self.settings.set_boolean("notifications", state)

    def __toggle_rc(self, widget, state):
        self.settings.set_boolean("release-candidate", state)
        self.populate_runners_list()

    def __toggle_temp(self, widget, state):
        self.settings.set_boolean("temp", state)

    def __toggle_steam(self, widget, state):
        self.settings.set_boolean("steam-proton-support", state)

    def __toggle_library(self, widget, state):
        self.settings.set_boolean("experiments-library", state)

    def __toggle_autoclose(self, widget, state):
        self.settings.set_boolean("auto-close-bottles", state)

    def __choose_bottles_path(self, widget):
        def set_path(_dialog, response, _file_dialog):
            self.btn_bottles_path_reset.set_visible(True)
            if response == Gtk.ResponseType.OK:
                _file = _file_dialog.get_file()
                self.data.set("custom_bottles_path", _file.get_path())
                self.action_bottles_path.set_subtitle(_file.get_path())
            else:
                self.action_bottles_path.set_subtitle(
                    _("Choose where to store the new bottles (this will not move the existing ones)"))
            _file_dialog.destroy()

        FileChooser(
            parent=self.window,
            title=_("Choose new bottles path"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=(_("Cancel"), _("Select")),
            native=False,
            callback=set_path
        )

    def __reset_bottles_path(self, widget):
        self.data.remove("custom_bottles_path")
        self.btn_bottles_path_reset.set_visible(False)
        self.action_bottles_path.set_subtitle(
            _("Choose where to store the new bottles (this will not move the existing ones)"))

    def populate_runtimes_list(self):
        for runtime in self.manager.supported_runtimes.items():
            self.list_runtimes.add(ComponentEntry(self.window, runtime, "runtime", is_upgradable=True))

    def populate_winebridge_list(self):
        for bridge in self.manager.supported_winebridge.items():
            self.list_winebridge.add(ComponentEntry(self.window, bridge, "winebridge", is_upgradable=True))

    def populate_dxvk_list(self):
        for dxvk in self.manager.supported_dxvk.items():
            self.list_dxvk.add(ComponentEntry(self.window, dxvk, "dxvk"))

    def populate_vkd3d_list(self):
        for vkd3d in self.manager.supported_vkd3d.items():
            self.list_vkd3d.add(ComponentEntry(self.window, vkd3d, "vkd3d"))

    def populate_nvapi_list(self):
        for nvapi in self.manager.supported_nvapi.items():
            self.list_nvapi.add(ComponentEntry(self.window, nvapi, "nvapi"))

    def populate_latencyflex_list(self):
        for latencyflex in self.manager.supported_latencyflex.items():
            self.list_latencyflex.add(ComponentEntry(self.window, latencyflex, "latencyflex"))

    def populate_runners_list(self):
        for w in self.__registry:
            parent = w.get_parent()
            if parent:
                parent.remove(w)

        exp_caffe = ComponentExpander("Caffe")
        exp_wine_ge = ComponentExpander("GE Wine")
        exp_lutris = ComponentExpander("Lutris")
        exp_proton = ComponentExpander("GE Proton")
        exp_other = ComponentExpander(_("Other"))

        for runner in self.manager.supported_wine_runners.items():
            _runner_name = runner[0].lower()
            if (not self.window.settings.get_boolean("release-candidate")
                    and runner[1]["Channel"] in ["rc", "unstable"]):
                continue

            _entry = ComponentEntry(self.window, runner, "runner")
            if _runner_name.startswith("caffe"):
                exp_caffe.add_row(_entry)
            elif _runner_name.startswith("wine-ge"):
                exp_wine_ge.add_row(_entry)
            elif _runner_name.startswith("lutris"):
                exp_lutris.add_row(_entry)
            else:
                exp_other.add_row(_entry)

        for runner in self.manager.supported_proton_runners.items():
            if (not self.window.settings.get_boolean("release-candidate")
                    and runner[1]["Channel"] in ["rc", "unstable"]):
                continue

            _entry = ComponentEntry(self.window, runner, "runner:proton")
            exp_proton.add_row(_entry)

        self.list_runners.add(exp_caffe)
        self.list_runners.add(exp_wine_ge)
        self.list_runners.add(exp_lutris)
        self.list_runners.add(exp_proton)
        self.list_runners.add(exp_other)

        self.__registry.append(exp_caffe)
        self.__registry.append(exp_wine_ge)
        self.__registry.append(exp_lutris)
        self.__registry.append(exp_proton)
        self.__registry.append(exp_other)
