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
from gettext import gettext as _
from gi.repository import Gtk

from ..utils import RunAsync

from ..backend.runner import Runner, gamemode_available
from ..backend.manager_utils import ManagerUtils

from ..dialogs.envvars import EnvVarsDialog
from ..dialogs.dlloverrides import DLLOverridesDialog


@Gtk.Template(resource_path='/com/usebottles/bottles/details-preferences.ui')
class PreferencesView(Gtk.ScrolledWindow):
    __gtype_name__ = 'DetailsPreferences'

    # region Widgets
    btn_manage_runners = Gtk.Template.Child()
    btn_manage_dxvk = Gtk.Template.Child()
    btn_manage_vkd3d = Gtk.Template.Child()
    btn_manage_nvapi = Gtk.Template.Child()
    btn_cwd = Gtk.Template.Child()
    btn_environment_variables = Gtk.Template.Child()
    btn_overrides = Gtk.Template.Child()
    switch_dxvk = Gtk.Template.Child()
    switch_dxvk_hud = Gtk.Template.Child()
    switch_vkd3d = Gtk.Template.Child()
    switch_nvapi = Gtk.Template.Child()
    switch_gamemode = Gtk.Template.Child()
    switch_aco = Gtk.Template.Child()
    switch_fsr = Gtk.Template.Child()
    switch_discrete = Gtk.Template.Child()
    switch_virt_desktop = Gtk.Template.Child()
    switch_pulse_latency = Gtk.Template.Child()
    switch_fixme = Gtk.Template.Child()
    switch_runtime = Gtk.Template.Child()
    toggle_sync = Gtk.Template.Child()
    toggle_esync = Gtk.Template.Child()
    toggle_fsync = Gtk.Template.Child()
    combo_fsr = Gtk.Template.Child()
    combo_virt_res = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    combo_dxvk = Gtk.Template.Child()
    combo_vkd3d = Gtk.Template.Child()
    combo_nvapi = Gtk.Template.Child()
    combo_windows = Gtk.Template.Child()
    row_cwd = Gtk.Template.Child()
    action_runtime = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        self.btn_overrides.connect('activate', self.__show_dll_overrides_view)
        self.btn_environment_variables.connect(
            'activate', self.__show_environment_variables
        )
        self.btn_cwd.connect('activate', self.choose_cwd)
        self.btn_overrides.connect('pressed', self.__show_dll_overrides_view)
        self.btn_manage_runners.connect('pressed', self.window.show_prefs_view)
        self.btn_manage_dxvk.connect('pressed', self.window.show_prefs_view)
        self.btn_manage_vkd3d.connect('pressed', self.window.show_prefs_view)
        self.btn_manage_nvapi.connect('pressed', self.window.show_prefs_view)
        self.btn_cwd.connect('pressed', self.choose_cwd)
        self.btn_environment_variables.connect(
            'pressed', self.__show_environment_variables
        )
        self.toggle_sync.connect('toggled', self.__set_wine_sync)
        self.toggle_esync.connect('toggled', self.__set_esync)
        self.toggle_fsync.connect('toggled', self.__set_fsync)

        self.switch_dxvk.connect('state-set', self.__toggle_dxvk)
        self.switch_dxvk_hud.connect('state-set', self.__toggle_dxvk_hud)
        self.switch_vkd3d.connect('state-set', self.__toggle_vkd3d)
        self.switch_nvapi.connect('state-set', self.__toggle_nvapi)
        self.switch_gamemode.connect('state-set', self.__toggle_gamemode)
        self.switch_aco.connect('state-set', self.__toggle_aco)
        self.switch_fsr.connect('state-set', self.__toggle_fsr)
        self.switch_discrete.connect('state-set', self.__toggle_discrete_gpu)
        self.switch_virt_desktop.connect(
            'state-set', self.__toggle_virt_desktop
        )
        self.switch_pulse_latency.connect(
            'state-set', self.__toggle_pulse_latency
        )
        self.switch_fixme.connect('state-set', self.__toggle_fixme)

        self.combo_fsr.connect('changed', self.__set_fsr_level)
        self.combo_virt_res.connect('changed', self.__set_virtual_desktop_res)
        self.combo_runner.connect('changed', self.__set_runner)
        self.combo_dxvk.connect('changed', self.__set_dxvk)
        self.combo_vkd3d.connect('changed', self.__set_vkd3d)
        self.combo_nvapi.connect('changed', self.__set_nvapi)
        self.combo_windows.connect('changed', self.__set_windows)

        self.__prevent_scroll()

        if "FLATPAK_ID" in os.environ:
            self.action_runtime.set_visible(True)
            self.switch_runtime.connect('state-set', self.__toggle_runtime)

        '''
        Toggle the gamemode sensitivity based on gamemode_available
        also update the tooltip text with an helpfull message if it
        is not available.
        '''
        self.switch_gamemode.set_sensitive(gamemode_available)
        if not gamemode_available:
            self.switch_gamemode.set_tooltip_text(
                _("Gamemode is either not available on your system or not running."))

    def choose_cwd(self, widget):
        '''
        This function pop up a file chooser to choose the
        cwd (current working directory) of the bottle and update
        the bottle configuration with the new value.
        The default path for the file chooser is the bottle path by default.
        '''
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
            self.manager.update_config(
                config=self.config,
                key="WorkingDir",
                value=file_dialog.get_filename()
            )

        file_dialog.destroy()

    def update_combo_components(self):
        '''
        This function update the components combo boxes with the
        items in the manager catalogs. It also temporarily disable 
        the functions connected to the combo boxes to avoid the 
        bottle configuration to be updated during the process.
        '''
        self.combo_runner.handler_block_by_func(self.__set_runner)
        self.combo_dxvk.handler_block_by_func(self.__set_dxvk)
        self.combo_vkd3d.handler_block_by_func(self.__set_vkd3d)
        self.combo_nvapi.handler_block_by_func(self.__set_nvapi)

        self.combo_runner.remove_all()
        self.combo_dxvk.remove_all()
        self.combo_vkd3d.remove_all()
        self.combo_nvapi.remove_all()

        for runner in self.manager.runners_available:
            self.combo_runner.append(runner, runner)

        for dxvk in self.manager.dxvk_available:
            self.combo_dxvk.append(dxvk, dxvk)

        for vkd3d in self.manager.vkd3d_available:
            self.combo_vkd3d.append(vkd3d, vkd3d)

        for nvapi in self.manager.nvapi_available:
            self.combo_nvapi.append(nvapi, nvapi)

        self.combo_runner.handler_unblock_by_func(self.__set_runner)
        self.combo_dxvk.handler_unblock_by_func(self.__set_dxvk)
        self.combo_vkd3d.handler_unblock_by_func(self.__set_vkd3d)
        self.combo_nvapi.handler_unblock_by_func(self.__set_nvapi)
    
    def set_config(self, config):
        self.config = config
        parameters = self.config.get("Parameters")

        # temporary lock functions connected to the widgets
        self.switch_dxvk.handler_block_by_func(self.__toggle_dxvk)
        self.switch_vkd3d.handler_block_by_func(self.__toggle_vkd3d)
        self.switch_nvapi.handler_block_by_func(self.__toggle_nvapi)
        self.switch_virt_desktop.handler_block_by_func(
            self.__toggle_virt_desktop
        )
        self.combo_fsr.handler_block_by_func(self.__set_fsr_level)
        self.combo_virt_res.handler_block_by_func(
            self.__set_virtual_desktop_res
        )
        self.combo_runner.handler_block_by_func(self.__set_runner)
        self.combo_dxvk.handler_block_by_func(self.__set_dxvk)
        self.combo_vkd3d.handler_block_by_func(self.__set_vkd3d)
        self.combo_nvapi.handler_block_by_func(self.__set_nvapi)
        self.combo_windows.handler_block_by_func(self.__set_windows)
        
        self.switch_dxvk.set_active(parameters["dxvk"])
        self.switch_dxvk_hud.set_active(parameters["dxvk_hud"])
        self.switch_vkd3d.set_active(parameters["vkd3d"])
        self.switch_nvapi.set_active(parameters["dxvk_nvapi"])
        self.switch_gamemode.set_active(parameters["gamemode"])
        self.switch_fsr.set_active(parameters["fsr"])
        self.switch_runtime.set_active(parameters["use_runtime"])
        self.switch_aco.set_active(parameters["aco_compiler"])

        if parameters["sync"] == "wine":
            self.toggle_sync.set_active(True)
        if parameters["sync"] == "esync":
            self.toggle_esync.set_active(True)
        if parameters["sync"] == "fsync":
            self.toggle_fsync.set_active(True)

        self.switch_discrete.set_active(parameters["discrete_gpu"])
        self.switch_virt_desktop.set_active(parameters["virtual_desktop"])
        self.switch_pulse_latency.set_active(
            parameters["pulseaudio_latency"]
        )
        self.combo_virt_res.set_active_id(
            parameters["virtual_desktop_res"]
        )
        self.combo_fsr.set_active_id(str(parameters["fsr_level"]))
        self.combo_runner.set_active_id(self.config.get("Runner"))
        self.combo_dxvk.set_active_id(self.config.get("DXVK"))
        self.combo_vkd3d.set_active_id(self.config.get("VKD3D"))
        self.combo_nvapi.set_active_id(self.config.get("NVAPI"))
        self.combo_windows.set_active_id(self.config.get("Windows"))

        # unlock functions connected to the widgets
        self.switch_dxvk.handler_unblock_by_func(self.__toggle_dxvk)
        self.switch_vkd3d.handler_unblock_by_func(self.__toggle_vkd3d)
        self.switch_nvapi.handler_unblock_by_func(self.__toggle_nvapi)
        self.switch_virt_desktop.handler_unblock_by_func(
            self.__toggle_virt_desktop
        )
        self.combo_fsr.handler_unblock_by_func(
            self.__set_fsr_level
        )
        self.combo_virt_res.handler_unblock_by_func(
            self.__set_virtual_desktop_res
        )
        self.combo_runner.handler_unblock_by_func(self.__set_runner)
        self.combo_dxvk.handler_unblock_by_func(self.__set_dxvk)
        self.combo_vkd3d.handler_unblock_by_func(self.__set_vkd3d)
        self.combo_nvapi.handler_unblock_by_func(self.__set_nvapi)
        self.combo_windows.handler_unblock_by_func(self.__set_windows)


    def __show_environment_variables(self, widget=False):
        '''
        This function popup the environment variables dialog
        to the user.
        '''
        new_window = EnvVarsDialog(
            window=self.window,
            config=self.config
        )
        new_window.present()

    def __set_sync_type(self, sync):
        '''
        This function update the sync type on the bottle
        configuration according to the widget state.
        '''
        new_config = self.manager.update_config(
            config=self.config,
            key="sync",
            value=sync,
            scope="Parameters"
        )
        self.config = new_config

        if sync in ["esync", "fsync"]:
            self.toggle_sync.handler_block_by_func(self.__set_wine_sync)
            self.toggle_sync.set_active(False)
            self.toggle_sync.handler_unblock_by_func(self.__set_wine_sync)
        if sync in ["esync", "wine"]:
            self.toggle_fsync.handler_block_by_func(self.__set_fsync)
            self.toggle_fsync.set_active(False)
            self.toggle_fsync.handler_unblock_by_func(self.__set_fsync)
        if sync in ["fsync", "wine"]:
            self.toggle_esync.handler_block_by_func(self.__set_esync)
            self.toggle_esync.set_active(False)
            self.toggle_esync.handler_unblock_by_func(self.__set_esync)

    def __set_wine_sync(self, widget):
        self.__set_sync_type("wine")

    def __set_esync(self, widget):
        self.__set_sync_type("esync")

    def __set_fsync(self, widget):
        self.__set_sync_type("fsync")
    
    def __toggle_dxvk(self, widget=False, state=False):
        '''
        This function perform DXVK installation or removal, according
        to the widget state. It will also update the bottle configuration
        once the process is finished.
        '''
        if widget:
            widget.set_sensitive(False)
        if state:
            RunAsync(
                task_func=self.manager.install_dxvk,
                callback=self.set_dxvk_status,
                config=self.config
            )
        else:
            RunAsync(
                self.manager.remove_dxvk,
                callback=self.set_dxvk_status,
                config=self.config,
            )

        new_config = self.manager.update_config(
            config=self.config,
            key="dxvk",
            value=state,
            scope="Parameters"
        )
        self.config = new_config

    def __toggle_dxvk_hud(self, widget, state):
        '''
        This function update the DXVK HUD status on the bottle
        configuration according to the widget state.
        '''
        new_config = self.manager.update_config(
            config=self.config,
            key="dxvk_hud",
            value=state,
            scope="Parameters"
        )
        self.config = new_config

    def __toggle_vkd3d(self, widget=False, state=False):
        '''
        This function perform VKD3D installation or removal, according
        to the widget state. It will also update the bottle configuration
        once the process is finished.
        '''
        if widget:
            widget.set_sensitive(False)
        if state:
            RunAsync(
                task_func=self.manager.install_vkd3d,
                callback=self.set_vkd3d_status,
                config=self.config
            )
        else:
            RunAsync(
                task_func=self.manager.remove_vkd3d,
                callback=self.set_vkd3d_status,
                config=self.config
            )

        new_config = self.manager.update_config(
            config=self.config,
            key="vkd3d",
            value=state,
            scope="Parameters"
        )
        self.config = new_config

    def __toggle_nvapi(self, widget=False, state=False):
        '''
        This function perform DXVK-NVAPI installation or removal, according
        to the widget state. It will also update the bottle configuration
        once the process is finished.
        '''
        if widget:
            widget.set_sensitive(False)
        if state:
            RunAsync(
                task_func=self.manager.install_nvapi,
                callback=self.set_nvapi_status,
                config=self.config
            )
        else:
            RunAsync(
                task_func=self.manager.remove_nvapi,
                callback=self.set_nvapi_status,
                config=self.config
            )

        new_config = self.manager.update_config(
            config=self.config,
            key="dxvk_nvapi",
            value=state,
            scope="Parameters"
        )
        self.config = new_config

    def __toggle_gamemode(self, widget=False, state=False):
        '''
        This function update the gamemode status on the bottle
        configuration according to the widget state.
        '''
        new_config = self.manager.update_config(
            config=self.config,
            key="gamemode",
            value=state,
            scope="Parameters"
        )
        self.config = new_config

    def __toggle_fsr(self, widget, state):
        '''
        This function update the aco status on the bottle
        configuration according to the widget state.
        '''
        new_config = self.manager.update_config(
            config=self.config,
            key="fsr",
            value=state,
            scope="Parameters"
        )
        self.config = new_config
    
    def __toggle_runtime(self, widget, state):
        '''
        This function update the runtime status on the bottle
        configuration according to the widget state.
        '''
        new_config = self.manager.update_config(
            config=self.config,
            key="use_runtime",
            value=state,
            scope="Parameters"
        )
        self.config = new_config

    def __toggle_aco(self, widget, state):
        '''
        This function update the aco status on the bottle
        configuration according to the widget state.
        '''
        new_config = self.manager.update_config(
            config=self.config,
            key="aco_compiler",
            value=state,
            scope="Parameters"
        )
        self.config = new_config

    def __toggle_discrete_gpu(self, widget, state):
        '''
        This function update the discrete gpu status on the bottle
        configuration according to the widget state.
        '''
        new_config = self.manager.update_config(
            config=self.config,
            key="discrete_gpu",
            value=state,
            scope="Parameters"
        )
        self.config = new_config

    def __toggle_virt_desktop(self, widget, state):
        '''
        This function update the virtual desktop status on the bottle
        configuration according to the widget state.
        '''
        resolution = self.combo_virt_res.get_active_id()
        Runner.toggle_virtual_desktop(
            config=self.config,
            state=state,
            resolution=resolution
        )
        new_config = self.manager.update_config(
            config=self.config,
            key="virtual_desktop",
            value=state,
            scope="Parameters")
        self.config = new_config

    def __set_virtual_desktop_res(self, widget):
        '''
        This function update the virtual desktop resolution on the bottle
        configuration according to the selected one.
        '''
        resolution = widget.get_active_id()
        if self.switch_virt_desktop.get_active():
            Runner.toggle_virtual_desktop(
                config=self.config,
                state=True,
                resolution=resolution
            )
        new_config = self.manager.update_config(
            config=self.config,
            key="virtual_desktop_res",
            value=resolution,
            scope="Parameters"
        )
        self.config = new_config

    def __set_fsr_level(self, widget):
        '''
        This function update the AMD FSR level of sharpness
        (from 0 to 5, where 5 is the default).
        '''
        level = widget.get_active_id()
        new_config = self.manager.update_config(
            config=self.config,
            key="fsr_level",
            value=level,
            scope="Parameters"
        )
        self.config = new_config

    def __set_runner(self, widget):
        '''
        This function update the runner on the bottle configuration
        according to the selected one.
        '''
        runner = widget.get_active_id()
        new_config = self.manager.update_config(
            config=self.config,
            key="Runner",
            value=runner
        )
        self.config = new_config

    def __set_dxvk(self, widget):
        '''
        This function update the dxvk version on the bottle 
        configuration according to the selected one. It will
        also trigger the toggle_dxvk method to force the
        installation of the new version.
        '''
        self.__toggle_dxvk(widget=self.switch_dxvk, state=False)

        dxvk = widget.get_active_id()
        new_config = self.manager.update_config(
            config=self.config,
            key="DXVK",
            value=dxvk
        )
        self.config = new_config
        self.__toggle_dxvk(state=True)

    def __set_vkd3d(self, widget):
        '''
        This function update the vkd3d version on the bottle 
        configuration according to the selected one. It will
        also trigger the toggle_vkd3d method to force the
        installation of the new version.
        '''
        self.__toggle_vkd3d(widget=self.switch_vkd3d, state=False)

        vkd3d = widget.get_active_id()
        new_config = self.manager.update_config(
            config=self.config,
            key="VKD3D",
            value=vkd3d
        )
        self.config = new_config
        self.__toggle_vkd3d(state=True)

    def __set_nvapi(self, widget):
        '''
        This function update the dxvk-nvapi version on the bottle 
        configuration according to the selected one. It will
        also trigger the toggle_dxvk method to force the
        installation of the new version.
        '''
        self.__toggle_nvapi(widget=self.switch_nvapi, state=False)

        nvapi = widget.get_active_id()
        new_config = self.manager.update_config(
            config=self.config,
            key="NVAPI",
            value=nvapi
        )
        self.config = new_config
        self.__toggle_nvapi(state=True)

    def __set_windows(self, widget):
        '''
        This function update the Windows version on the bottle 
        configuration according to the selected one.
        '''
        win = widget.get_active_id()
        new_config = self.manager.update_config(
            config=self.config,
            key="Windows",
            value=win
        )
        Runner.set_windows(config=new_config, version=win)
        self.config = new_config

    def __toggle_pulse_latency(self, widget, state):
        '''
        This function update the pulseaudio latency status on the bottle
        configuration according to the widget state.
        '''
        new_config = self.manager.update_config(
            config=self.config,
            key="pulseaudio_latency",
            value=state,
            scope="Parameters"
        )
        self.config = new_config

    def __toggle_fixme(self, widget, state):
        '''
        This function update the fixme logs status on the bottle
        configuration according to the widget state.
        '''
        new_config = self.manager.update_config(
            config=self.config,
            key="fixme_logs",
            value=state,
            scope="Parameters"
        )
        self.config = new_config

    def __show_dll_overrides_view(self, widget=False):
        '''
        This function pop up the DLL overrides dialog, where the
        user can add and remove new ones.
        '''
        new_window = DLLOverridesDialog(
            window=self.window,
            config=self.config
        )
        new_window.present()
    
    def set_dxvk_status(self, status, error=None):
        self.switch_dxvk.set_sensitive(True)
    
    def set_vkd3d_status(self, status, error=None):
        self.switch_vkd3d.set_sensitive(True)
    
    def set_nvapi_status(self, status, error=None):
        self.switch_nvapi.set_sensitive(True)
    
    def __prevent_scroll(self):
        def no_action(widget, event):
            return True

        for c in [
            self.combo_fsr,
            self.combo_virt_res,
            self.combo_runner,
            self.combo_dxvk,
            self.combo_vkd3d,
            self.combo_nvapi,
            self.combo_windows
        ]:
            c.connect('scroll-event', no_action)
