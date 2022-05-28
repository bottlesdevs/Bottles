# bottle_preferences.py
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
import re
from gettext import gettext as _
from gi.repository import Gtk

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false

from bottles.backend.runner import Runner, gamemode_available, gamescope_available, mangohud_available, obs_vkc_available
from bottles.backend.managers.runtime import RuntimeManager
from bottles.backend.managers.steam import SteamManager
from bottles.backend.utils.manager import ManagerUtils

from bottles.dialogs.envvars import EnvVarsDialog
from bottles.dialogs.drives import DrivesDialog
from bottles.dialogs.dlloverrides import DLLOverridesDialog
from bottles.dialogs.gamescope import GamescopeDialog

from bottles.backend.wine.catalogs import win_versions
from bottles.backend.wine.reg import Reg
from bottles.backend.wine.regkeys import RegKeys


# noinspection PyUnusedLocal
@Gtk.Template(resource_path='/com/usebottles/bottles/details-preferences.ui')
class PreferencesView(Gtk.ScrolledWindow):
    __gtype_name__ = 'DetailsPreferences'

    # region Widgets
    btn_manage_runners = Gtk.Template.Child()
    btn_manage_dxvk = Gtk.Template.Child()
    btn_manage_vkd3d = Gtk.Template.Child()
    btn_manage_nvapi = Gtk.Template.Child()
    btn_manage_gamescope = Gtk.Template.Child()
    btn_cwd = Gtk.Template.Child()
    btn_environment_variables = Gtk.Template.Child()
    btn_drives = Gtk.Template.Child()
    btn_overrides = Gtk.Template.Child()
    btn_cwd_reset = Gtk.Template.Child()
    btn_rename = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    switch_dxvk = Gtk.Template.Child()
    switch_dxvk_hud = Gtk.Template.Child()
    switch_mangohud = Gtk.Template.Child()
    switch_obsvkc = Gtk.Template.Child()
    switch_vkbasalt = Gtk.Template.Child()
    switch_vkd3d = Gtk.Template.Child()
    switch_nvapi = Gtk.Template.Child()
    switch_latencyflex = Gtk.Template.Child()
    switch_gamemode = Gtk.Template.Child()
    switch_gamescope = Gtk.Template.Child()
    switch_fsr = Gtk.Template.Child()
    switch_discrete = Gtk.Template.Child()
    switch_virt_desktop = Gtk.Template.Child()
    switch_pulse_latency = Gtk.Template.Child()
    switch_fixme = Gtk.Template.Child()
    switch_runtime = Gtk.Template.Child()
    switch_steam_runtime = Gtk.Template.Child()
    switch_mouse_capture = Gtk.Template.Child()
    switch_take_focus = Gtk.Template.Child()
    toggle_sync = Gtk.Template.Child()
    toggle_esync = Gtk.Template.Child()
    toggle_fsync = Gtk.Template.Child()
    toggle_futex2 = Gtk.Template.Child()
    combo_fsr = Gtk.Template.Child()
    combo_virt_res = Gtk.Template.Child()
    combo_dpi = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    combo_dxvk = Gtk.Template.Child()
    combo_vkd3d = Gtk.Template.Child()
    combo_nvapi = Gtk.Template.Child()
    combo_latencyflex = Gtk.Template.Child()
    combo_windows = Gtk.Template.Child()
    combo_renderer = Gtk.Template.Child()
    action_dxvk = Gtk.Template.Child()
    action_vkd3d = Gtk.Template.Child()
    action_nvapi = Gtk.Template.Child()
    action_latencyflex = Gtk.Template.Child()
    action_cwd = Gtk.Template.Child()
    action_discrete = Gtk.Template.Child()
    action_runner = Gtk.Template.Child()
    action_runtime = Gtk.Template.Child()
    action_steam_runtime = Gtk.Template.Child()
    spinner_dxvk = Gtk.Template.Child()
    spinner_dxvkbool = Gtk.Template.Child()
    spinner_vkd3d = Gtk.Template.Child()
    spinner_vkd3dbool = Gtk.Template.Child()
    spinner_nvapi = Gtk.Template.Child()
    spinner_nvapibool = Gtk.Template.Child()
    spinner_latencyflex = Gtk.Template.Child()
    spinner_latencyflexbool = Gtk.Template.Child()
    spinner_runner = Gtk.Template.Child()
    spinner_win = Gtk.Template.Child()
    box_sync = Gtk.Template.Child()
    group_details = Gtk.Template.Child()
    exp_components = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        self.entry_name.connect('key-release-event', self.__check_entry_name)
        self.entry_name.connect('activate', self.__toggle_rename)
        self.btn_rename.connect('toggled', self.__toggle_rename)

        self.btn_overrides.connect("clicked", self.__show_dll_overrides_view)
        self.btn_manage_runners.connect("clicked", self.window.show_prefs_view)
        self.btn_manage_dxvk.connect("clicked", self.window.show_prefs_view)
        self.btn_manage_vkd3d.connect("clicked", self.window.show_prefs_view)
        self.btn_manage_nvapi.connect("clicked", self.window.show_prefs_view)
        self.btn_manage_gamescope.connect("clicked", self.__show_gamescope_settings)
        self.btn_cwd.connect("clicked", self.choose_cwd)
        self.btn_cwd_reset.connect("clicked", self.choose_cwd, True)
        self.btn_drives.connect("clicked", self.__show_drives)
        self.btn_environment_variables.connect("clicked", self.__show_environment_variables)
        self.toggle_sync.connect('toggled', self.__set_wine_sync)
        self.toggle_esync.connect('toggled', self.__set_esync)
        self.toggle_fsync.connect('toggled', self.__set_fsync)
        self.toggle_futex2.connect('toggled', self.__set_futex2)

        self.switch_dxvk.connect('state-set', self.__toggle_dxvk)
        self.switch_dxvk_hud.connect('state-set', self.__toggle_dxvk_hud)
        self.switch_mangohud.connect('state-set', self.__toggle_mangohud)
        self.switch_obsvkc.connect('state-set', self.__toggle_obsvkc)
        self.switch_vkbasalt.connect('state-set', self.__toggle_vkbasalt)
        self.switch_vkd3d.connect('state-set', self.__toggle_vkd3d)
        self.switch_nvapi.connect('state-set', self.__toggle_nvapi)
        self.switch_latencyflex.connect('state-set', self.__toggle_latencyflex)
        self.switch_gamemode.connect('state-set', self.__toggle_gamemode)
        self.switch_gamescope.connect('state-set', self.__toggle_gamescope)
        self.switch_fsr.connect('state-set', self.__toggle_fsr)
        self.switch_discrete.connect('state-set', self.__toggle_discrete_gpu)
        self.switch_virt_desktop.connect('state-set', self.__toggle_virt_desktop)
        self.switch_pulse_latency.connect('state-set', self.__toggle_pulse_latency)
        self.switch_fixme.connect('state-set', self.__toggle_fixme)
        self.switch_mouse_capture.connect('state-set', self.__toggle_x11_reg_key, "GrabFullscreen",
                                          "fullscreen_capture")
        self.switch_take_focus.connect('state-set', self.__toggle_x11_reg_key, "UseTakeFocus", "take_focus")
        self.combo_fsr.connect('changed', self.__set_fsr_level)
        self.combo_virt_res.connect('changed', self.__set_virtual_desktop_res)
        self.combo_dpi.connect('changed', self.__set_custom_dpi)
        self.combo_runner.connect('changed', self.__set_runner)
        self.combo_dxvk.connect('changed', self.__set_dxvk)
        self.combo_vkd3d.connect('changed', self.__set_vkd3d)
        self.combo_nvapi.connect('changed', self.__set_nvapi)
        self.combo_latencyflex.connect('changed', self.__set_latencyflex)
        self.combo_windows.connect('changed', self.__set_windows)
        self.combo_renderer.connect('changed', self.__set_renderer)

        self.__prevent_scroll()

        if RuntimeManager.get_runtimes("bottles"):
            self.action_runtime.set_visible(True)
            self.switch_runtime.connect('state-set', self.__toggle_runtime)

        if RuntimeManager.get_runtimes("steam"):
            self.action_steam_runtime.set_visible(True)
            self.switch_steam_runtime.connect('state-set', self.__toggle_steam_runtime)

        '''Toggle some utilites according to its availability'''
        self.switch_gamemode.set_sensitive(gamemode_available)
        self.switch_gamescope.set_sensitive(gamescope_available)
        self.switch_mangohud.set_sensitive(mangohud_available)
        self.switch_obsvkc.set_sensitive(obs_vkc_available)
        _not_available = _("This feature is not available on your system.")
        if not gamemode_available:
            self.switch_gamemode.set_tooltip_text(_not_available)
        if not gamescope_available:
            self.switch_gamescope.set_tooltip_text(_not_available)
        if not mangohud_available:
            self.switch_mangohud.set_tooltip_text(_not_available)
        if not obs_vkc_available:
            self.switch_obsvkc.set_tooltip_text(_not_available)

    def __toggle_rename(self, widget):
        """
        This function toggle the entry_name editability. It will
        also update the bottle configuration with the new bottle name
        if the entry_name status is False (not editable).
        """
        if not self.btn_rename.get_sensitive():
            return

        status = self.btn_rename.get_active()
        if widget == self.entry_name:
            status = not status

        self.entry_name.set_editable(status)
        self.entry_name.set_has_frame(status)
        self.entry_name.set_can_focus(status)

        if status:
            self.entry_name.grab_focus()
        else:
            name = self.entry_name.get_text()
            self.manager.update_config(
                config=self.config,
                key="Name",
                value=name
            )
            self.btn_rename.handler_block_by_func(self.__toggle_rename)
            self.btn_rename.set_active(False)
            self.btn_rename.handler_unblock_by_func(self.__toggle_rename)
            self.window.page_details.view_bottle.label_name.set_text(name)
            self.entry_name.select_region(0, 0)

    def __check_entry_name(self, widget, event_key):
        """
        This function check if the entry name is valid, looking
        for special characters. It also toggles the widget icon
        and the save button sensitivity according to the result.
        """
        regex = re.compile("[@!#$%^&*()<>?/|}{~:.;,'\"]")
        name = widget.get_text()

        if (regex.search(name) is None) and name != "" and not name.isspace():
            self.btn_rename.set_sensitive(True)
            widget.set_icon_from_icon_name(1, "")
        else:
            self.btn_rename.set_sensitive(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")

    def choose_cwd(self, widget, reset=False):
        """Change the default current working directory for the bottle"""
        path = ""
        if not reset:
            file_dialog = Gtk.FileChooserNative.new(
                _("Choose working directory for executables"),
                self.window,
                Gtk.FileChooserAction.SELECT_FOLDER,
                _("Done"),
                _("Cancel")
            )
            file_dialog.set_current_folder(
                ManagerUtils.get_bottle_path(self.config)
            )
            response = file_dialog.run()

            if response == -3:
                path = file_dialog.get_filename()

            file_dialog.destroy()

        self.manager.update_config(
            config=self.config,
            key="WorkingDir",
            value=path
        )

        if path != "":
            self.action_cwd.set_subtitle(path)
        else:
            self.action_cwd.set_subtitle(_("Default to the bottle path."))

    def update_combo_components(self):
        """
        This function update the components' combo boxes with the
        items in the manager catalogs. It also temporarily disable
        the functions connected to the combo boxes to avoid the
        bottle configuration to be updated during the process.
        """
        self.combo_runner.handler_block_by_func(self.__set_runner)
        self.combo_dxvk.handler_block_by_func(self.__set_dxvk)
        self.combo_vkd3d.handler_block_by_func(self.__set_vkd3d)
        self.combo_nvapi.handler_block_by_func(self.__set_nvapi)
        self.combo_latencyflex.handler_block_by_func(self.__set_latencyflex)

        self.combo_runner.remove_all()
        self.combo_dxvk.remove_all()
        self.combo_vkd3d.remove_all()
        self.combo_nvapi.remove_all()
        self.combo_latencyflex.remove_all()

        for runner in self.manager.runners_available:
            self.combo_runner.append(runner, runner)

        for dxvk in self.manager.dxvk_available:
            self.combo_dxvk.append(dxvk, dxvk)

        for vkd3d in self.manager.vkd3d_available:
            self.combo_vkd3d.append(vkd3d, vkd3d)

        for nvapi in self.manager.nvapi_available:
            self.combo_nvapi.append(nvapi, nvapi)

        for latencyflex in self.manager.latencyflex_available:
            self.combo_latencyflex.append(latencyflex, latencyflex)

        self.combo_runner.handler_unblock_by_func(self.__set_runner)
        self.combo_dxvk.handler_unblock_by_func(self.__set_dxvk)
        self.combo_vkd3d.handler_unblock_by_func(self.__set_vkd3d)
        self.combo_nvapi.handler_unblock_by_func(self.__set_nvapi)
        self.combo_latencyflex.handler_unblock_by_func(self.__set_latencyflex)

    def set_config(self, config):
        self.config = config
        parameters = self.config.get("Parameters")

        # temporary lock functions connected to the widgets
        self.switch_dxvk.handler_block_by_func(self.__toggle_dxvk)
        self.switch_vkd3d.handler_block_by_func(self.__toggle_vkd3d)
        self.switch_nvapi.handler_block_by_func(self.__toggle_nvapi)
        self.switch_latencyflex.handler_block_by_func(self.__toggle_latencyflex)
        self.switch_virt_desktop.handler_block_by_func(self.__toggle_virt_desktop)
        self.switch_mouse_capture.handler_block_by_func(self.__toggle_x11_reg_key)
        self.switch_take_focus.handler_block_by_func(self.__toggle_x11_reg_key)
        self.switch_vkbasalt.handler_block_by_func(self.__toggle_vkbasalt)
        self.switch_obsvkc.handler_block_by_func(self.__toggle_obsvkc)
        self.switch_gamemode.handler_block_by_func(self.__toggle_gamemode)
        self.switch_gamescope.handler_block_by_func(self.__toggle_gamescope)
        self.switch_discrete.handler_block_by_func(self.__toggle_discrete_gpu)
        self.switch_fsr.handler_block_by_func(self.__toggle_fsr)
        self.switch_pulse_latency.handler_block_by_func(self.__toggle_pulse_latency)
        self.switch_runtime.handler_block_by_func(self.__toggle_runtime)
        try:
            self.switch_steam_runtime.handler_block_by_func(self.__toggle_steam_runtime)
        except TypeError:
            pass  # already disconnected
        self.combo_fsr.handler_block_by_func(self.__set_fsr_level)
        self.combo_virt_res.handler_block_by_func(self.__set_virtual_desktop_res)
        self.combo_runner.handler_block_by_func(self.__set_runner)
        self.combo_dxvk.handler_block_by_func(self.__set_dxvk)
        self.combo_vkd3d.handler_block_by_func(self.__set_vkd3d)
        self.combo_nvapi.handler_block_by_func(self.__set_nvapi)
        self.combo_latencyflex.handler_block_by_func(self.__set_latencyflex)
        self.combo_windows.handler_block_by_func(self.__set_windows)
        self.combo_renderer.handler_block_by_func(self.__set_renderer)
        self.combo_dpi.handler_block_by_func(self.__set_custom_dpi)
        self.toggle_sync.handler_block_by_func(self.__set_wine_sync)
        self.toggle_esync.handler_block_by_func(self.__set_esync)
        self.toggle_fsync.handler_block_by_func(self.__set_fsync)
        self.toggle_futex2.handler_block_by_func(self.__set_futex2)
        self.entry_name.handler_block_by_func(self.__check_entry_name)

        self.switch_dxvk.set_active(parameters["dxvk"])
        self.switch_dxvk_hud.set_active(parameters["dxvk_hud"])
        self.switch_mangohud.set_active(parameters["mangohud"])
        self.switch_obsvkc.set_active(parameters["obsvkc"])
        self.switch_vkbasalt.set_active(parameters["vkbasalt"])
        self.switch_vkd3d.set_active(parameters["vkd3d"])
        self.switch_nvapi.set_active(parameters["dxvk_nvapi"])
        self.switch_latencyflex.set_active(parameters["latencyflex"])
        self.switch_gamemode.set_active(parameters["gamemode"])
        self.switch_gamescope.set_active(parameters["gamescope"])
        self.switch_fsr.set_active(parameters["fsr"])
        self.switch_runtime.set_active(parameters["use_runtime"])
        self.switch_steam_runtime.set_active(parameters["use_steam_runtime"])

        self.toggle_sync.set_active(parameters["sync"] == "wine")
        self.toggle_esync.set_active(parameters["sync"] == "esync")
        self.toggle_fsync.set_active(parameters["sync"] == "fsync")
        self.toggle_futex2.set_active(parameters["sync"] == "futex2")

        self.switch_discrete.set_active(parameters["discrete_gpu"])
        self.switch_virt_desktop.set_active(parameters["virtual_desktop"])
        self.switch_mouse_capture.set_active(parameters["fullscreen_capture"])
        self.switch_take_focus.set_active(parameters["take_focus"])
        self.switch_pulse_latency.set_active(parameters["pulseaudio_latency"])
        self.combo_virt_res.set_active_id(parameters["virtual_desktop_res"])
        self.combo_fsr.set_active_id(str(parameters["fsr_level"]))
        self.combo_runner.set_active_id(self.config.get("Runner"))
        self.combo_dxvk.set_active_id(self.config.get("DXVK"))
        self.combo_vkd3d.set_active_id(self.config.get("VKD3D"))
        self.combo_nvapi.set_active_id(self.config.get("NVAPI"))
        self.combo_renderer.set_active_id(parameters["renderer"])
        self.combo_dpi.set_active_id(str(parameters["custom_dpi"]))

        self.entry_name.set_text(config["Name"])

        if self.config.get("WorkingDir") != "":
            self.action_cwd.set_subtitle(self.config.get("WorkingDir"))
        else:
            self.action_cwd.set_subtitle(_("Default to the bottle path."))

        self.combo_windows.remove_all()
        self.combo_windows.append("win10", "Windows 10")
        self.combo_windows.append("win81", "Windows 8.1")
        self.combo_windows.append("win8", "Windows 8")
        self.combo_windows.append("win7", "Windows 7")
        self.combo_windows.append("vista", "Windows Vista")
        self.combo_windows.append("win2008r2", "Windows 2008 R2")
        self.combo_windows.append("win2008", "Windows 2008")
        self.combo_windows.append("winxp", "Windows XP")

        if self.config.get("Arch") == "win32":
            self.combo_windows.append("win98", "Windows 98")
            self.combo_windows.append("win95", "Windows 95")

        self.combo_windows.set_active_id(self.config.get("Windows"))

        # unlock functions connected to the widgets
        self.switch_dxvk.handler_unblock_by_func(self.__toggle_dxvk)
        self.switch_vkd3d.handler_unblock_by_func(self.__toggle_vkd3d)
        self.switch_nvapi.handler_unblock_by_func(self.__toggle_nvapi)
        self.switch_latencyflex.handler_unblock_by_func(self.__toggle_latencyflex)
        self.switch_virt_desktop.handler_unblock_by_func(self.__toggle_virt_desktop)
        self.switch_mouse_capture.handler_unblock_by_func(self.__toggle_x11_reg_key)
        self.switch_take_focus.handler_unblock_by_func(self.__toggle_x11_reg_key)
        self.switch_vkbasalt.handler_unblock_by_func(self.__toggle_vkbasalt)
        self.switch_obsvkc.handler_unblock_by_func(self.__toggle_obsvkc)
        self.switch_gamemode.handler_unblock_by_func(self.__toggle_gamemode)
        self.switch_gamescope.handler_unblock_by_func(self.__toggle_gamescope)
        self.switch_discrete.handler_unblock_by_func(self.__toggle_discrete_gpu)
        self.switch_fsr.handler_unblock_by_func(self.__toggle_fsr)
        self.switch_pulse_latency.handler_unblock_by_func(self.__toggle_pulse_latency)
        self.switch_runtime.handler_unblock_by_func(self.__toggle_runtime)
        try:
            self.switch_steam_runtime.handler_unblock_by_func(self.__toggle_steam_runtime)
        except TypeError:
            pass  # already connected
        self.combo_fsr.handler_unblock_by_func(self.__set_fsr_level)
        self.combo_virt_res.handler_unblock_by_func(self.__set_virtual_desktop_res)
        self.combo_runner.handler_unblock_by_func(self.__set_runner)
        self.combo_dxvk.handler_unblock_by_func(self.__set_dxvk)
        self.combo_vkd3d.handler_unblock_by_func(self.__set_vkd3d)
        self.combo_nvapi.handler_unblock_by_func(self.__set_nvapi)
        self.combo_latencyflex.handler_unblock_by_func(self.__set_latencyflex)
        self.combo_windows.handler_unblock_by_func(self.__set_windows)
        self.combo_renderer.handler_unblock_by_func(self.__set_renderer)
        self.combo_dpi.handler_unblock_by_func(self.__set_custom_dpi)
        self.toggle_sync.handler_unblock_by_func(self.__set_wine_sync)
        self.toggle_esync.handler_unblock_by_func(self.__set_esync)
        self.toggle_fsync.handler_unblock_by_func(self.__set_fsync)
        self.toggle_futex2.handler_unblock_by_func(self.__set_futex2)
        self.entry_name.handler_unblock_by_func(self.__check_entry_name)

        self.__set_steam_rules()

    def __show_gamescope_settings(self, widget):
        new_window = GamescopeDialog(
            window=self.window,
            config=self.config
        )
        new_window.present()

    def __show_drives(self, widget):
        new_window = DrivesDialog(
            window=self.window,
            config=self.config
        )
        new_window.present()

    def __show_environment_variables(self, widget=False):
        """Show the environment variables dialog"""
        new_window = EnvVarsDialog(
            window=self.window,
            config=self.config
        )
        new_window.present()

    def __set_sync_type(self, sync):
        """
        Set the sync type (wine, esync, fsync, futext2)
        Don't use this directly, use dedicated wrappers instead (e.g. __set_wine_sync)
        """
        def update(result, error=False):
            self.config = result.data["config"]
            toggles = [
                ("wine", self.toggle_sync, self.__set_wine_sync),
                ("esync", self.toggle_esync, self.__set_esync),
                ("fsync", self.toggle_fsync, self.__set_fsync),
                ("futex2", self.toggle_futex2, self.__set_futex2)
            ]
            for sync_type, toggle, func in toggles:
                toggle.handler_block_by_func(func)
                if sync_type == sync:
                    toggle.set_active(True)
                else:
                    toggle.set_active(False)
                toggle.handler_unblock_by_func(func)
            self.box_sync.set_sensitive(True)

        self.box_sync.set_sensitive(False)
        RunAsync(
            self.manager.update_config,
            callback=update,
            config=self.config,
            key="sync",
            value=sync,
            scope="Parameters"
        )

    def __set_wine_sync(self, widget):
        self.__set_sync_type("wine")

    def __set_esync(self, widget):
        self.__set_sync_type("esync")

    def __set_fsync(self, widget):
        self.__set_sync_type("fsync")

    def __set_futex2(self, widget):
        self.__set_sync_type("futex2")

    def __toggle_dxvk(self, widget=False, state=False):
        """Install/Uninstall DXVK from the bottle"""
        self.set_dxvk_status(pending=True)

        RunAsync(
            task_func=self.manager.install_dll_component,
            callback=self.set_dxvk_status,
            config=self.config,
            component="dxvk",
            remove=not state
        )

        self.config = self.manager.update_config(
            config=self.config,
            key="dxvk",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_dxvk_hud(self, widget, state):
        """Toggle the DXVK HUD for current bottle"""
        self.config = self.manager.update_config(
            config=self.config,
            key="dxvk_hud",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_mangohud(self, widget, state):
        """Toggle the Mangohud for current bottle"""
        self.config = self.manager.update_config(
            config=self.config,
            key="mangohud",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_obsvkc(self, widget, state):
        """Toggle the OBS Vulkan capture for current bottle"""
        self.config = self.manager.update_config(
            config=self.config,
            key="obsvkc",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_vkbasalt(self, widget, state):
        """Toggle the vkBasalt for current bottle"""
        self.config = self.manager.update_config(
            config=self.config,
            key="vkbasalt",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_vkd3d(self, widget=False, state=False):
        """Install/Uninstall VKD3D from the bottle"""
        self.set_vkd3d_status(pending=True)

        RunAsync(
            task_func=self.manager.install_dll_component,
            callback=self.set_vkd3d_status,
            config=self.config,
            component="vkd3d",
            remove=not state
        )

        self.config = self.manager.update_config(
            config=self.config,
            key="vkd3d",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_nvapi(self, widget=False, state=False):
        """Install/Uninstall NVAPI from the bottle"""
        self.set_nvapi_status(pending=True)

        RunAsync(
            task_func=self.manager.install_dll_component,
            callback=self.set_nvapi_status,
            config=self.config,
            component="nvapi",
            remove=not state
        )

        self.config = self.manager.update_config(
            config=self.config,
            key="dxvk_nvapi",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_latencyflex(self, widget=False, state=False):
        """Install/Uninstall LatencyFlex from the bottle"""
        self.set_latencyflex_status(pending=True)

        RunAsync(
            task_func=self.manager.install_dll_component,
            callback=self.set_latencyflex_status,
            config=self.config,
            component="latencyflex",
            remove=not state
        )

        self.config = self.manager.update_config(
            config=self.config,
            key="latencyflex",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_gamemode(self, widget=False, state=False):
        """Toggle the gamemode for current bottle"""
        self.config = self.manager.update_config(
            config=self.config,
            key="gamemode",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_gamescope(self, widget=False, state=False):
        """Toggle the gamescope for current bottle"""
        self.config = self.manager.update_config(
            config=self.config,
            key="gamescope",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_fsr(self, widget, state):
        """Toggle the FSR for current bottle"""
        self.config = self.manager.update_config(
            config=self.config,
            key="fsr",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_runtime(self, widget, state):
        """Toggle the Bottles runtime for current bottle"""
        self.config = self.manager.update_config(
            config=self.config,
            key="use_runtime",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_steam_runtime(self, widget, state):
        """Toggle the Steam runtime for current bottle"""
        self.config = self.manager.update_config(
            config=self.config,
            key="use_steam_runtime",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_discrete_gpu(self, widget, state):
        """Toggle the discrete GPU for current bottle"""
        self.config = self.manager.update_config(
            config=self.config,
            key="discrete_gpu",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_virt_desktop(self, widget, state):
        """Toggle the virtual desktop option."""
        widget.set_sensitive(False)

        def update(result, error=False):
            self.config = self.manager.update_config(
                config=self.config,
                key="virtual_desktop",
                value=state,
                scope="Parameters"
            ).data["config"]
            widget.set_sensitive(True)

        rk = RegKeys(self.config)
        resolution = self.combo_virt_res.get_active_id()
        RunAsync(
            task_func=rk.toggle_virtual_desktop,
            callback=update,
            state=state,
            resolution=resolution
        )

    def __set_virtual_desktop_res(self, widget):
        """Set the virtual desktop resolution."""
        widget.set_sensitive(False)

        def update(result, error=False):
            self.config = self.manager.update_config(
                config=self.config,
                key="virtual_desktop_res",
                value=resolution,
                scope="Parameters"
            ).data["config"]
            widget.set_sensitive(True)

        rk = RegKeys(self.config)
        resolution = widget.get_active_id()
        if self.switch_virt_desktop.get_active():
            RunAsync(
                task_func=rk.toggle_virtual_desktop,
                callback=update,
                state=True,
                resolution=resolution
            )

    def __set_fsr_level(self, widget):
        """Set the FSR level of sharpness (from 0 to 5, where 5 is the default)"""
        level = int(widget.get_active_id())
        self.config = self.manager.update_config(
            config=self.config,
            key="fsr_level",
            value=level,
            scope="Parameters"
        ).data["config"]

    def __set_runner(self, widget):
        """Set the runner to use for the bottle"""

        def set_widgets_status(status=True):
            for w in [
                widget,
                self.switch_dxvk,
                self.switch_nvapi,
                self.switch_vkd3d,
                self.combo_dxvk,
                self.combo_nvapi,
                self.combo_vkd3d
            ]:
                w.set_sensitive(status)
            if status:
                self.spinner_runner.stop()
            else:
                self.spinner_runner.start()

        def update(result, error=False):
            if result and "config" in result.data.keys():
                self.config = result.data["config"]
                if self.config["Parameters"].get("use_steam_runtime"):
                    self.switch_steam_runtime.handler_block_by_func(self.__toggle_steam_runtime)
                    self.switch_steam_runtime.set_active(True)
                    self.switch_steam_runtime.handler_unblock_by_func(self.__toggle_steam_runtime)
            set_widgets_status(True)

        set_widgets_status(False)
        runner = widget.get_active_id()

        RunAsync(
            Runner.runner_update,
            callback=update,
            config=self.config,
            manager=self.manager,
            runner=runner
        )

    def __dll_component_task_func(self, *args, **kwargs):
        # Remove old version
        self.manager.install_dll_component(config=kwargs["config"], component=kwargs["component"], remove=True)
        # Install new version
        self.manager.install_dll_component(config=kwargs["config"], component=kwargs["component"])

    def __set_dxvk(self, widget):
        """Set the DXVK version to use for the bottle"""
        self.set_dxvk_status(pending=True)

        dxvk = widget.get_active_id()
        self.config = self.manager.update_config(
            config=self.config,
            key="DXVK",
            value=dxvk
        ).data["config"]

        RunAsync(
            task_func=self.__dll_component_task_func,
            callback=self.set_dxvk_status,
            config=self.config,
            component="dxvk"
        )

    def __set_vkd3d(self, widget):
        """Set the VKD3D version to use for the bottle"""
        self.set_vkd3d_status(pending=True)

        vkd3d = widget.get_active_id()
        self.config = self.manager.update_config(
            config=self.config,
            key="VKD3D",
            value=vkd3d
        ).data["config"]

        RunAsync(
            task_func=self.__dll_component_task_func,
            callback=self.set_vkd3d_status,
            config=self.config,
            component="vkd3d"
        )

    def __set_nvapi(self, widget):
        """Set the NVAPI version to use for the bottle"""
        self.set_nvapi_status(pending=True)

        nvapi = widget.get_active_id()
        self.config = self.manager.update_config(
            config=self.config,
            key="NVAPI",
            value=nvapi
        ).data["config"]

        RunAsync(
            task_func=self.__dll_component_task_func,
            callback=self.set_nvapi_status,
            config=self.config,
            component="nvapi"
        )

    def __set_latencyflex(self, widget):
        """Set the latency flex value"""
        latencyflex = widget.get_active_id()
        self.config = self.manager.update_config(
            config=self.config,
            key="LatencyFleX",
            value=latencyflex
        ).data["config"]

        RunAsync(
            task_func=self.__dll_component_task_func,
            callback=self.set_latencyflex_status,
            config=self.config,
            component="latencyflex"
        )

    def __set_windows(self, widget):
        """Set the Windows version to use for the bottle"""

        def update(result, error=False):
            self.spinner_win.stop()
            widget.set_sensitive(True)

        self.spinner_win.start()
        widget.set_sensitive(False)
        rk = RegKeys(self.config)

        win = widget.get_active_id()
        self.config = self.manager.update_config(
            config=self.config,
            key="Windows",
            value=win
        ).data["config"]

        RunAsync(
            rk.set_windows,
            callback=update,
            version=win
        )

    def __set_renderer(self, widget):
        """Set the renderer to use for the bottle"""
        def update(result, error=False):
            self.config = self.manager.update_config(
                config=self.config,
                key="renderer",
                value=renderer,
                scope="Parameters"
            ).data["config"]
            widget.set_sensitive(True)

        rk = RegKeys(self.config)
        widget.set_sensitive(False)
        renderer = widget.get_active_id()

        RunAsync(
            rk.set_renderer,
            callback=update,
            value=renderer
        )

    def __toggle_pulse_latency(self, widget, state):
        """Set the pulse latency to use for the bottle"""
        self.config = self.manager.update_config(
            config=self.config,
            key="pulseaudio_latency",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_fixme(self, widget, state):
        """Set the Wine logging level to use for the bottle"""
        self.config = self.manager.update_config(
            config=self.config,
            key="fixme_logs",
            value=state,
            scope="Parameters"
        ).data["config"]

    def __toggle_x11_reg_key(self, widget, state, rkey, ckey):
        """Update x11 registry keys"""

        def update(result, error=False):
            nonlocal widget
            self.config = self.manager.update_config(
                config=self.config,
                key=ckey,
                value=state,
                scope="Parameters"
            ).data["config"]
            widget.set_sensitive(True)

        reg = Reg(self.config)
        widget.set_sensitive(False)
        _rule = "Y" if state else "N"

        RunAsync(
            reg.add,
            callback=update,
            key="HKEY_CURRENT_USER\\Software\\Wine\\X11 Driver",
            value=rkey,
            data=_rule
        )

    def __set_custom_dpi(self, widget):
        """Set the custom dpi value"""

        def update(result, error=False):
            self.config = self.manager.update_config(
                config=self.config,
                key="custom_dpi",
                value=dpi,
                scope="Parameters"
            ).data["config"]
            widget.set_sensitive(True)

        rk = RegKeys(self.config)
        widget.set_sensitive(False)
        dpi = int(widget.get_active_id())

        RunAsync(
            rk.set_dpi,
            callback=update,
            value=dpi
        )

    def __show_dll_overrides_view(self, widget=False):
        """Show the DLL overrides view"""
        new_window = DLLOverridesDialog(
            window=self.window,
            config=self.config
        )
        new_window.present()

    def set_dxvk_status(self, status=None, error=None, pending=False):
        """Set the dxvk status"""
        self.switch_dxvk.set_sensitive(not pending)
        self.combo_dxvk.set_sensitive(not pending)
        if pending:
            self.spinner_dxvk.start()
            self.spinner_dxvkbool.start()
        else:
            self.spinner_dxvk.stop()
            self.spinner_dxvkbool.stop()

    def set_vkd3d_status(self, status=None, error=None, pending=False):
        """Set the vkd3d status"""
        self.switch_vkd3d.set_sensitive(not pending)
        self.combo_vkd3d.set_sensitive(not pending)
        if pending:
            self.spinner_vkd3d.start()
            self.spinner_vkd3dbool.start()
        else:
            self.spinner_vkd3d.stop()
            self.spinner_vkd3dbool.stop()

    def set_nvapi_status(self, status=None, error=None, pending=False):
        """Set the nvapi status"""
        self.switch_nvapi.set_sensitive(not pending)
        self.combo_nvapi.set_sensitive(not pending)
        if pending:
            self.spinner_nvapi.start()
            self.spinner_nvapibool.start()
        else:
            self.spinner_nvapi.stop()
            self.spinner_nvapibool.stop()

    def set_latencyflex_status(self, status=None, error=None, pending=False):
        """Set the latencyflex status"""
        self.switch_latencyflex.set_sensitive(not pending)
        self.combo_latencyflex.set_sensitive(not pending)
        if pending:
            self.spinner_latencyflex.start()
            self.spinner_latencyflexbool.start()
        else:
            self.spinner_latencyflex.stop()
            self.spinner_latencyflexbool.stop()

    def __prevent_scroll(self):
        """Prevent the scroll event when the mouse enter a combobox"""

        def no_action(widget, event):
            return True

        for c in [
            self.combo_fsr,
            self.combo_virt_res,
            self.combo_runner,
            self.combo_dxvk,
            self.combo_vkd3d,
            self.combo_nvapi,
            self.combo_latencyflex,
            self.combo_windows,
            self.combo_renderer
        ]:
            c.connect('scroll-event', no_action)

    def __set_steam_rules(self):
        """Set the Steam Environment specific rules"""
        status = False if self.config.get("Environment") == "Steam" else True

        for w in [
            self.action_discrete,
            self.action_runner,
            self.action_runtime,
            self.action_steam_runtime,
            self.action_dxvk,
            self.action_vkd3d,
            self.action_nvapi,
            self.action_latencyflex,
            self.group_details,
            self.exp_components
        ]:
            w.set_visible(status)
            w.set_sensitive(status)
