# preferences.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
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

import os
import subprocess
import webbrowser
from gettext import gettext as _

from gi.repository import Gtk, Adw, Gio, GLib

from bottles.backend.managers.data import DataManager, UserDataKeys
from bottles.backend.state import EventManager, Events
from bottles.backend.utils.threading import RunAsync
from bottles.backend.utils.generic import sort_by_version
from bottles.frontend.widgets.component import ComponentEntry, ComponentExpander


@Gtk.Template(resource_path='/com/usebottles/bottles/preferences.ui')
class PreferencesWindow(Adw.PreferencesWindow):
    __gtype_name__ = 'PreferencesWindow'
    __registry = []

    # region Widgets
    installers_stack = Gtk.Template.Child()
    installers_spinner = Gtk.Template.Child()
    dlls_stack = Gtk.Template.Child()
    dlls_spinner = Gtk.Template.Child()

    row_theme = Gtk.Template.Child()
    switch_theme = Gtk.Template.Child()
    switch_notifications = Gtk.Template.Child()
    switch_temp = Gtk.Template.Child()
    switch_release_candidate = Gtk.Template.Child()
    switch_steam = Gtk.Template.Child()
    switch_sandbox = Gtk.Template.Child()
    switch_auto_close = Gtk.Template.Child()
    switch_update_date = Gtk.Template.Child()
    switch_steam_programs = Gtk.Template.Child()
    switch_epic_games = Gtk.Template.Child()
    switch_ubisoft_connect = Gtk.Template.Child()
    list_winebridge = Gtk.Template.Child()
    list_runtimes = Gtk.Template.Child()
    list_runners = Gtk.Template.Child()
    list_dxvk = Gtk.Template.Child()
    list_vkd3d = Gtk.Template.Child()
    list_nvapi = Gtk.Template.Child()
    list_latencyflex = Gtk.Template.Child()
    action_prerelease = Gtk.Template.Child()
    btn_bottles_path = Gtk.Template.Child()
    action_steam_proton = Gtk.Template.Child()
    btn_bottles_path_reset = Gtk.Template.Child()
    label_bottles_path = Gtk.Template.Child()
    btn_steam_proton_doc = Gtk.Template.Child()
    pref_core = Gtk.Template.Child()

    # endregion

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        # common variables and references
        self.window = window
        self.settings = window.settings
        self.manager = window.manager
        self.data = DataManager()
        self.style_manager = Adw.StyleManager.get_default()

        if "FLATPAK_ID" in os.environ:
            self.remove(self.pref_core)

        self.current_bottles_path = self.data.get(UserDataKeys.CustomBottlesPath)
        if self.current_bottles_path:
            self.label_bottles_path.set_label(os.path.basename(self.current_bottles_path))
            self.btn_bottles_path_reset.set_visible(True)

        # bind widgets
        self.settings.bind("dark-theme", self.switch_theme, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("notifications", self.switch_notifications, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("temp", self.switch_temp, "active", Gio.SettingsBindFlags.DEFAULT)
        # Connect RC signal to another func
        self.settings.bind("release-candidate", self.switch_release_candidate, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("steam-proton-support", self.switch_steam, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("experiments-sandbox", self.switch_sandbox, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("auto-close-bottles", self.switch_auto_close, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("update-date", self.switch_update_date, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("steam-programs", self.switch_steam_programs, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("epic-games", self.switch_epic_games, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("ubisoft-connect", self.switch_ubisoft_connect, "active", Gio.SettingsBindFlags.DEFAULT)

        # setup loading screens
        self.installers_stack.set_visible_child_name("installers_loading")
        self.installers_spinner.start()
        self.dlls_stack.set_visible_child_name("dlls_loading")
        self.dlls_spinner.start()

        if not self.manager.utils_conn.status:
            self.installers_stack.set_visible_child_name("installers_offline")
            self.dlls_stack.set_visible_child_name("dlls_offline")

        # populate components lists
        self.populate_runtimes_list()
        self.populate_winebridge_list()

        RunAsync(self.ui_update)

        # connect signals
        self.settings.connect('changed::dark-theme', self.__toggle_night)
        self.settings.connect('changed::release-candidate', self.__toggle_rc)
        self.settings.connect('changed::update-date', self.__toggle_update_date)
        self.btn_bottles_path.connect('clicked', self.__choose_bottles_path)
        self.btn_bottles_path_reset.connect('clicked', self.__reset_bottles_path)
        self.btn_steam_proton_doc.connect('clicked', self.__open_steam_proton_doc)

        if not self.manager.steam_manager.is_steam_supported:
            self.switch_steam.set_sensitive(False)
            self.action_steam_proton.set_tooltip_text(
                _("Steam was not found or Bottles does not have enough permissions."))
            self.btn_steam_proton_doc.set_visible(True)

        if not self.style_manager.get_system_supports_color_schemes():
            self.row_theme.set_visible(True)

    def empty_list(self):
        for w in self.__registry:
            parent = w.get_parent()
            if parent:
                parent.remove(w)
        self.__registry = []

    def ui_update(self):
        if self.manager.utils_conn.status:
            EventManager.wait(Events.ComponentsOrganizing)
            GLib.idle_add(self.empty_list)
            GLib.idle_add(self.populate_runners_list)
            GLib.idle_add(self.populate_dxvk_list)
            GLib.idle_add(self.populate_vkd3d_list)
            GLib.idle_add(self.populate_nvapi_list)
            GLib.idle_add(self.populate_latencyflex_list)

            GLib.idle_add(self.dlls_stack.set_visible_child_name, "dlls_list")

    def __toggle_night(self, widget, state):
        if self.settings.get_boolean("dark-theme"):
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.DEFAULT)

    def __toggle_update_date(self, widget, state):
        self.window.page_list.update_bottles()

    def __toggle_rc(self, widget, state):
        self.ui_update()

    def __open_steam_proton_doc(self, widget):
        webbrowser.open("https://docs.usebottles.com/flatpak/cant-enable-steam-proton-manager")

    def __choose_bottles_path(self, widget):
        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            path = dialog.get_file().get_path()

            self.data.set(UserDataKeys.CustomBottlesPath, path)
            self.label_bottles_path.set_label(os.path.basename(path))
            self.btn_bottles_path_reset.set_visible(True)
            self.prompt_restart()

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Bottles Path"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            parent=self.window
        )

        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def handle_restart(self, widget, response_id):
        if response_id == "restart":
            subprocess.Popen(
                "sleep 1 && bottles & disown",
                shell=True
            )
            self.window.proper_close()
        widget.destroy()

    def prompt_restart(self):
        if self.current_bottles_path != self.data.get(UserDataKeys.CustomBottlesPath):
            dialog = Adw.MessageDialog.new(
                self.window,
                _("Relaunch Bottles?"),
                _("Bottles will need to be relaunched to use this directory.\n\nBe sure to close every program launched from Bottles before relaunching Bottles, as not doing so can cause data loss, corruption and programs to malfunction.")
            )
            dialog.add_response("dismiss", _("_Cancel"))
            dialog.add_response("restart", _("_Relaunch"))
            dialog.set_response_appearance("restart", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.connect("response", self.handle_restart)
            dialog.present()

    def __reset_bottles_path(self, widget):
        self.data.remove(UserDataKeys.CustomBottlesPath)
        self.btn_bottles_path_reset.set_visible(False)
        self.label_bottles_path.set_label(_("(Default)"))
        self.prompt_restart()

    def __check_release_candidate(self, component):
        return (not self.window.settings.get_boolean("release-candidate")
                    and component[1]["Channel"] in ["rc", "unstable"])

    def __populate_component_list(self, component_type, supported_components, list_component):
        offline_components = self.manager.get_offline_components(component_type)
        supported_component_items = list(supported_components.items())
        i, j = 0, 0
        while i <= len(supported_component_items):
            while j < len(offline_components) and \
                    (i == len(supported_component_items) or \
                    sort_by_version([offline_components[j], supported_component_items[i][0]])[0] == offline_components[j]):
                offline_entry = [ offline_components[j], { "Installed": True} ]
                supported_component_items.insert(i, offline_entry)
                j += 1
            i += 1
        for component in supported_component_items:
            if self.__check_release_candidate(component):
                continue
            _entry = ComponentEntry(self.window, component, component_type)
            list_component.add(_entry)
            self.__registry.append(_entry)

    def populate_runtimes_list(self):
        for runtime in self.manager.supported_runtimes.items():
            self.list_runtimes.add(ComponentEntry(self.window, runtime, "runtime", is_upgradable=True))

    def populate_winebridge_list(self):
        for bridge in self.manager.supported_winebridge.items():
            self.list_winebridge.add(ComponentEntry(self.window, bridge, "winebridge", is_upgradable=True))

    def populate_dxvk_list(self):
        self.__populate_component_list("dxvk", self.manager.supported_dxvk, self.list_dxvk)

    def populate_vkd3d_list(self):
        self.__populate_component_list("vkd3d", self.manager.supported_vkd3d, self.list_vkd3d)

    def populate_nvapi_list(self):
        self.__populate_component_list("nvapi", self.manager.supported_nvapi, self.list_nvapi)

    def populate_latencyflex_list(self):
        self.__populate_component_list("latencyflex", self.manager.supported_latencyflex, self.list_latencyflex)

    def __populate_runners_helper(self, runner_type, supported_runners_dict, identifiable_runners_struct):
        offline_runners_list = self.manager.get_offline_components(runner_type)
        for offline_runner in offline_runners_list:
            _runner_name = offline_runner.lower()
            for identifiable_runner in identifiable_runners_struct:
                if _runner_name.startswith(identifiable_runner["prefix"]):
                    identifiable_runner["offline_runners"].append(offline_runner)
                    break

        for supported_runner in supported_runners_dict.items():
            _runner_name = supported_runner[0].lower()
            if self.__check_release_candidate(supported_runner):
                continue

            _entry = ComponentEntry(self.window, supported_runner, runner_type)
            for identifiable_runner in identifiable_runners_struct:
                if _runner_name.startswith(identifiable_runner["prefix"]):
                    while identifiable_runner["offline_runners"] and \
                            sort_by_version([identifiable_runner["offline_runners"][0], supported_runner[0]])[0] == identifiable_runner["offline_runners"][0]:
                        offline_runner = [ identifiable_runner["offline_runners"][0], { "Installed": True} ]
                        _offline_entry = ComponentEntry(self.window, offline_runner, runner_type)
                        identifiable_runner["expander"].add_row(_offline_entry)
                        identifiable_runner["count"] += 1
                        identifiable_runner["offline_runners"].pop(0)
                    identifiable_runner["expander"].add_row(_entry)
                    identifiable_runner["count"] += 1
                    break

        # Don't forget left over offline runners
        for identifiable_runner in identifiable_runners_struct:
            while identifiable_runner["offline_runners"]:
                offline_runner = [ identifiable_runner["offline_runners"][0], { "Installed": True} ]
                _offline_entry = ComponentEntry(self.window, offline_runner, runner_type)
                identifiable_runner["expander"].add_row(_offline_entry)
                identifiable_runner["count"] += 1
                identifiable_runner["offline_runners"].pop(0)

    def populate_runners_list(self):
        exp_soda = ComponentExpander("Soda", _("Based on Valve's Wine, includes Staging and Proton patches."))
        exp_caffe = ComponentExpander("Caffe", _("Based on Wine upstream, includes Staging and Proton patches."))
        exp_wine_ge = ComponentExpander("Wine GE", _("Based on the most recent bleeding-edge Valve's Proton Experimental Wine, "
                                                     "includes Staging and custom patches. "
                                                     "This is meant to be used with non-steam games outside of Steam."))
        exp_kron4ek = ComponentExpander("Kron4ek", _("Based on Wine upstream, Staging, Staging-TkG and Proton patchset optionally available."))
        exp_lutris = ComponentExpander("Lutris")
        exp_vaniglia = ComponentExpander("Vaniglia", _("Based on Wine upstream, includes Staging patches."))
        exp_proton_ge = ComponentExpander("Proton GE", _("Based on most recent bleeding-edge Valve's Proton Experimental, "
                                                      "includes Staging and custom patches. "
                                                      "Requires the Steam Runtime turned on."))
        exp_other_wine = ComponentExpander(_("Other Wine runners"))
        exp_other_proton = ComponentExpander(_("Other Proton runners"))

        identifiable_wine_runners = [
            { "prefix": "soda", "count": 0, "expander": exp_soda, "offline_runners": [] },
            { "prefix": "caffe", "count": 0, "expander": exp_caffe, "offline_runners": [] },
            { "prefix": "vaniglia", "count": 0, "expander": exp_vaniglia, "offline_runners": [] },
            { "prefix": "wine-ge", "count": 0, "expander": exp_wine_ge, "offline_runners": [] },
            { "prefix": "kron4ek", "count": 0, "expander": exp_kron4ek, "offline_runners": [] },
            { "prefix": "lutris", "count": 0, "expander": exp_lutris, "offline_runners": [] },
        ]
        identifiable_proton_runners = [
            { "prefix": "ge-proton", "count": 0, "expander": exp_proton_ge, "offline_runners": [] }
        ]
        other_wine_runners = [
            { "prefix": "", "count": 0, "expander": exp_other_wine, "offline_runners": [] },
        ]
        other_proton_runners = [
            { "prefix": "", "count": 0, "expander": exp_other_proton, "offline_runners": [] },
        ]

        self.__populate_runners_helper("runner", \
            self.manager.supported_wine_runners, identifiable_wine_runners + other_wine_runners)
        self.__populate_runners_helper("runner:proton", \
            self.manager.supported_proton_runners, identifiable_proton_runners + other_proton_runners)

        for runner in identifiable_wine_runners + identifiable_proton_runners + other_wine_runners + other_proton_runners:
            if runner["count"] > 0:
                self.list_runners.add(runner["expander"])
                self.__registry.append(runner["expander"])

        self.installers_stack.set_visible_child_name("installers_list")
