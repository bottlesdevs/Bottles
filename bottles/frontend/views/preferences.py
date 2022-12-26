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

from bottles.backend.globals import wait_for_fetch

from bottles.frontend.utils.threading import RunAsync
from bottles.frontend.widgets.component import ComponentEntry, ComponentExpander
from bottles.frontend.windows.filechooser import FileChooser

from bottles.backend.managers.data import DataManager

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
        self.default_settings = window.default_settings
        self.manager = window.manager
        self.data = DataManager()
        self.style_manager = Adw.StyleManager.get_default()

        if "FLATPAK_ID" in os.environ:
            self.remove(self.pref_core)

        self.current_bottles_path = self.data.get("custom_bottles_path")
        if self.current_bottles_path:
            self.label_bottles_path.set_label(os.path.basename(self.current_bottles_path))
            self.btn_bottles_path_reset.set_visible(True)

        # bind widgets
        self.settings.bind("dark-theme", self.switch_theme, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("notifications", self.switch_notifications, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("temp", self.switch_temp, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("release-candidate", self.switch_release_candidate, "active", Gio.SettingsBindFlags.DEFAULT) #Connect RC signal to another func
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

        # populate components lists
        self.populate_runtimes_list()
        self.populate_winebridge_list()

        def ui_update():
            wait_for_fetch("components")
            GLib.idle_add(self.populate_runners_list)
            GLib.idle_add(self.populate_dxvk_list)
            GLib.idle_add(self.populate_vkd3d_list)
            GLib.idle_add(self.populate_nvapi_list)
            GLib.idle_add(self.populate_latencyflex_list)

            GLib.idle_add(self.dlls_stack.set_visible_child_name, "dlls_list")

        RunAsync(ui_update)

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

    def __toggle_night(self, widget, state):
        if self.settings.get_boolean("dark-theme"):
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.DEFAULT)


    def __toggle_update_date(self, widget, state):
        self.window.page_list.update_bottles()

    def __toggle_rc(self, widget, state):
        self.populate_runners_list()

    def __open_steam_proton_doc(self, widget):
        webbrowser.open("https://docs.usebottles.com/flatpak/cant-enable-steam-proton-manager")

    def __choose_bottles_path(self, widget):
        def set_path(_dialog, response, _file_dialog):
            if response == Gtk.ResponseType.ACCEPT:
                _file = _file_dialog.get_file()
                self.data.set("custom_bottles_path", _file.get_path())
                self.label_bottles_path.set_label(os.path.basename(_file.get_path()))
                self.btn_bottles_path_reset.set_visible(True)
                self.prompt_restart()
            _file_dialog.destroy()

        FileChooser(
            parent=self.window,
            title=_("Choose a new Bottles path"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=(_("Cancel"), _("Select")),
            callback=set_path,
            native=True
        )

    def handle_restart(self, widget, response_id):
        if response_id == "restart":
            subprocess.Popen(
                "sleep 1 && bottles & disown",
                shell=True
            )
            self.window.proper_close()
        widget.destroy()

    def prompt_restart(self):
        if self.current_bottles_path != self.data.get("custom_bottles_path"):
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
        self.data.remove("custom_bottles_path")
        self.btn_bottles_path_reset.set_visible(False)
        self.label_bottles_path.set_label(_("(Default)"))
        self.prompt_restart()

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

        exp_soda = ComponentExpander("Soda", _("Based on Valve's Wine, includes staging and Proton patches."))
        exp_caffe = ComponentExpander("Caffe", _("Based on Wine upstream, includes staging and Proton patches."))
        exp_wine_ge = ComponentExpander("GE Wine")
        exp_lutris = ComponentExpander("Lutris")
        exp_vaniglia = ComponentExpander("Vaniglia", _("Based on Wine upstream, includes staging patches."))
        exp_proton = ComponentExpander("GE Proton", _("Based on Valve's Wine, includes staging, Proton and "
                                                      "Steam-specific patches. Requires the Steam Runtime turned on."))
        exp_other = ComponentExpander(_("Other"))

        count = {"soda": 0, "caffe": 0, "wine-ge": 0, "lutris": 0, "vaniglia": 0, "proton": 0, "other": 0}

        for runner in self.manager.supported_wine_runners.items():
            _runner_name = runner[0].lower()
            if (not self.window.settings.get_boolean("release-candidate")
                    and runner[1]["Channel"] in ["rc", "unstable"]):
                continue

            _entry = ComponentEntry(self.window, runner, "runner")
            if _runner_name.startswith("soda"):
                exp_soda.add_row(_entry)
                count["soda"] += 1
            elif _runner_name.startswith("caffe"):
                exp_caffe.add_row(_entry)
                count["caffe"] += 1
            elif _runner_name.startswith("wine-ge"):
                exp_wine_ge.add_row(_entry)
                count["wine-ge"] += 1
            elif _runner_name.startswith("lutris"):
                exp_lutris.add_row(_entry)
                count["lutris"] += 1
            elif _runner_name.startswith("vaniglia"):
                exp_vaniglia.add_row(_entry)
                count["vaniglia"] += 1
            else:
                exp_other.add_row(_entry)
                count["other"] += 1

        for runner in self.manager.supported_proton_runners.items():
            if (not self.window.settings.get_boolean("release-candidate")
                    and runner[1]["Channel"] in ["rc", "unstable"]):
                continue

            _entry = ComponentEntry(self.window, runner, "runner:proton")
            exp_proton.add_row(_entry)
            count["proton"] += 1

        if count["soda"] > 0:
            self.list_runners.add(exp_soda)
            self.__registry.append(exp_soda)
        if count["caffe"] > 0:
            self.list_runners.add(exp_caffe)
            self.__registry.append(exp_caffe)
        if count["wine-ge"] > 0:
            self.list_runners.add(exp_wine_ge)
            self.__registry.append(exp_wine_ge)
        if count["lutris"] > 0:
            self.list_runners.add(exp_lutris)
            self.__registry.append(exp_lutris)
        if count["vaniglia"] > 0:
            self.list_runners.add(exp_vaniglia)
            self.__registry.append(exp_vaniglia)
        if count["proton"] > 0:
            self.list_runners.add(exp_proton)
            self.__registry.append(exp_proton)
        if count["other"] > 0:
            self.list_runners.add(exp_other)
            self.__registry.append(exp_other)

        self.installers_stack.set_visible_child_name("installers_list")