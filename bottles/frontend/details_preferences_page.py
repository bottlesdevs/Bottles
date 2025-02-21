# details_preferences_page.py
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

import contextlib
import os
import re
from gettext import gettext as _

from gi.repository import Gtk, Adw, Xdp

from bottles.backend.globals import (
    gamemode_available,
    vkbasalt_available,
    mangohud_available,
    obs_vkc_available,
    vmtouch_available,
    gamescope_available,
    base_version,
)
import logging
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.enum import Arch
from bottles.backend.models.result import Result
from bottles.backend.runner import Runner
from bottles.backend.utils.gpu import GPUUtils, GPUVendors
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync
from bottles.backend.wine.regkeys import RegKeys
from bottles.frontend.gtk import GtkUtils
from bottles.frontend.display_dialog import DisplayDialog
from bottles.frontend.dll_overrides_dialog import DLLOverridesDialog
from bottles.frontend.drives_dialog import DrivesDialog
from bottles.frontend.environment_variables_dialog import (
    EnvironmentVariablesDialog,
)
from bottles.frontend.fsr_dialog import FsrDialog
from bottles.frontend.gamescope_dialog import GamescopeDialog
from bottles.frontend.mangohud_dialog import MangoHudDialog
from bottles.frontend.proton_alert_dialog import ProtonAlertDialog
from bottles.frontend.sandbox_dialog import SandboxDialog
from bottles.frontend.vkbasalt_dialog import VkBasaltDialog
from bottles.frontend.vmtouch_dialog import VmtouchDialog


# noinspection PyUnusedLocal
@Gtk.Template(resource_path="/com/usebottles/bottles/details-preferences-page.ui")
class DetailsPreferencesPage(Adw.PreferencesPage):
    __gtype_name__ = "DetailsPreferencesPage"

    # region Widgets
    btn_manage_gamescope = Gtk.Template.Child()
    btn_manage_vkbasalt = Gtk.Template.Child()
    btn_manage_fsr = Gtk.Template.Child()
    btn_manage_mangohud = Gtk.Template.Child()
    btn_manage_sandbox = Gtk.Template.Child()
    btn_manage_vmtouch = Gtk.Template.Child()
    btn_cwd_reset = Gtk.Template.Child()
    btn_cwd = Gtk.Template.Child()
    row_nvapi = Gtk.Template.Child()
    row_discrete = Gtk.Template.Child()
    row_vkbasalt = Gtk.Template.Child()
    row_manage_display = Gtk.Template.Child()
    row_steam_runtime = Gtk.Template.Child()
    row_cwd = Gtk.Template.Child()
    label_cwd = Gtk.Template.Child()
    row_env_variables = Gtk.Template.Child()
    row_overrides = Gtk.Template.Child()
    row_drives = Gtk.Template.Child()
    row_sandbox = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    switch_mangohud = Gtk.Template.Child()
    switch_obsvkc = Gtk.Template.Child()
    switch_vkbasalt = Gtk.Template.Child()
    switch_fsr = Gtk.Template.Child()
    switch_nvapi = Gtk.Template.Child()
    switch_gamemode = Gtk.Template.Child()
    switch_gamescope = Gtk.Template.Child()
    switch_discrete = Gtk.Template.Child()
    switch_steam_runtime = Gtk.Template.Child()
    switch_sandbox = Gtk.Template.Child()
    switch_vmtouch = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    combo_dxvk = Gtk.Template.Child()
    combo_vkd3d = Gtk.Template.Child()
    combo_nvapi = Gtk.Template.Child()
    combo_latencyflex = Gtk.Template.Child()
    combo_windows = Gtk.Template.Child()
    combo_language = Gtk.Template.Child()
    combo_sync = Gtk.Template.Child()
    spinner_dxvk = Gtk.Template.Child()
    spinner_vkd3d = Gtk.Template.Child()
    spinner_nvapi = Gtk.Template.Child()
    spinner_nvapibool = Gtk.Template.Child()
    spinner_latencyflex = Gtk.Template.Child()
    spinner_runner = Gtk.Template.Child()
    spinner_windows = Gtk.Template.Child()
    spinner_display = Gtk.Template.Child()
    group_details = Gtk.Template.Child()
    str_list_languages = Gtk.Template.Child()
    str_list_runner = Gtk.Template.Child()
    str_list_dxvk = Gtk.Template.Child()
    str_list_vkd3d = Gtk.Template.Child()
    str_list_nvapi = Gtk.Template.Child()
    str_list_latencyflex = Gtk.Template.Child()
    str_list_windows = Gtk.Template.Child()

    # endregion

    def __init__(self, details, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = details.window
        self.config = config
        self.details = details

        if not gamemode_available or not Xdp.Portal.running_under_sandbox():
            return

        _not_available = _("This feature is unavailable on your system.")
        _flatpak_not_available = _(
            "{} To add this feature, please run flatpak install"
        ).format(_not_available)
        _gamescope_pkg_name = "org.freedesktop.Platform.VulkanLayer.gamescope"
        _vkbasalt_pkg_name = "org.freedesktop.Platform.VulkanLayer.vkBasalt"
        _mangohud_pkg_name = "org.freedesktop.Platform.VulkanLayer.MangoHud"
        _obsvkc_pkg_name = "com.obsproject.Studio.Plugin.OBSVkCapture"
        _flatpak_pkg_name = {
            "gamescope": (
                f"{_gamescope_pkg_name}//{base_version}"
                if base_version
                else _gamescope_pkg_name
            ),
            "vkbasalt": (
                f"{_vkbasalt_pkg_name}//{base_version}"
                if base_version
                else _vkbasalt_pkg_name
            ),
            "mangohud": (
                f"{_mangohud_pkg_name}//{base_version}"
                if base_version
                else _mangohud_pkg_name
            ),
            "obsvkc": _obsvkc_pkg_name,
        }

        if not gamescope_available:
            _gamescope_not_available = (
                f"{_flatpak_not_available} {_flatpak_pkg_name['gamescope']}"
            )
            self.switch_gamescope.set_tooltip_text(_gamescope_not_available)
            self.btn_manage_gamescope.set_tooltip_text(_gamescope_not_available)

        if not vkbasalt_available:
            _vkbasalt_not_available = (
                f"{_flatpak_not_available} {_flatpak_pkg_name['vkbasalt']}"
            )
            self.switch_vkbasalt.set_tooltip_text(_vkbasalt_not_available)
            self.btn_manage_vkbasalt.set_tooltip_text(_vkbasalt_not_available)

        if not mangohud_available:
            _mangohud_not_available = (
                f"{_flatpak_not_available} {_flatpak_pkg_name['mangohud']}"
            )
            self.switch_mangohud.set_tooltip_text(_mangohud_not_available)
            self.btn_manage_mangohud.set_tooltip_text(_mangohud_not_available)

        if not obs_vkc_available:
            _obsvkc_not_available = (
                f"{_flatpak_not_available} {_flatpak_pkg_name['obsvkc']}"
            )
            self.switch_obsvkc.set_tooltip_text(_obsvkc_not_available)

        # region signals
        self.row_manage_display.connect("activated", self.__show_display_settings)
        self.row_overrides.connect(
            "activated", self.__show_feature_dialog, DLLOverridesDialog
        )
        self.row_env_variables.connect(
            "activated", self.__show_feature_dialog, EnvironmentVariablesDialog
        )
        self.row_drives.connect("activated", self.__show_feature_dialog, DrivesDialog)
        self.btn_manage_gamescope.connect(
            "clicked", self.__show_feature_dialog, GamescopeDialog
        )
        self.btn_manage_vkbasalt.connect(
            "clicked", self.__show_feature_dialog, VkBasaltDialog
        )
        self.btn_manage_fsr.connect("clicked", self.__show_feature_dialog, FsrDialog)
        self.btn_manage_mangohud.connect(
            "clicked", self.__show_feature_dialog, MangoHudDialog
        )
        self.btn_manage_sandbox.connect(
            "clicked", self.__show_feature_dialog, SandboxDialog
        )
        self.btn_manage_vmtouch.connect(
            "clicked", self.__show_feature_dialog, VmtouchDialog
        )
        self.btn_cwd.connect("clicked", self.choose_cwd)
        self.btn_cwd_reset.connect("clicked", self.reset_cwd, True)
        self.switch_mangohud.connect("state-set", self.__toggle_feature, "mangohud")
        self.switch_obsvkc.connect("state-set", self.__toggle_feature, "obsvkc")
        self.switch_vkbasalt.connect("state-set", self.__toggle_feature, "vkbasalt")
        self.switch_fsr.connect("state-set", self.__toggle_feature, "fsr")
        self.switch_nvapi.connect("state-set", self.__toggle_nvapi)
        self.switch_gamemode.connect("state-set", self.__toggle_feature, "gamemode")
        self.switch_gamescope.connect("state-set", self.__toggle_feature, "gamescope")
        self.switch_sandbox.connect("state-set", self.__toggle_feature, "sandbox")
        self.switch_discrete.connect("state-set", self.__toggle_feature, "discrete_gpu")
        self.switch_vmtouch.connect("state-set", self.__toggle_feature, "vmtouch")
        self.combo_runner.connect("notify::selected", self.__set_runner)
        self.combo_dxvk.connect("notify::selected", self.__set_dxvk)
        self.combo_vkd3d.connect("notify::selected", self.__set_vkd3d)
        self.combo_nvapi.connect("notify::selected", self.__set_nvapi)
        self.combo_latencyflex.connect("notify::selected", self.__set_latencyflex)
        self.combo_windows.connect("notify::selected", self.__set_windows)
        self.combo_language.connect("notify::selected-item", self.__set_language)
        self.combo_sync.connect("notify::selected", self.__set_sync_type)
        self.entry_name.connect("changed", self.__check_entry_name)
        self.entry_name.connect("apply", self.__save_name)
        # endregion

        """Set DXVK_NVAPI related rows to visible when an NVIDIA GPU is detected (invisible by default)"""
        is_nvidia_gpu = GPUUtils.is_gpu(GPUVendors.NVIDIA)
        self.row_nvapi.set_visible(is_nvidia_gpu)
        self.combo_nvapi.set_visible(is_nvidia_gpu)

        """Toggle some utilities according to its availability"""
        self.switch_gamemode.set_sensitive(gamemode_available)
        self.switch_gamescope.set_sensitive(gamescope_available)
        self.btn_manage_gamescope.set_sensitive(gamescope_available)
        self.switch_vkbasalt.set_sensitive(vkbasalt_available)
        self.btn_manage_vkbasalt.set_sensitive(vkbasalt_available)
        self.switch_mangohud.set_sensitive(mangohud_available)
        self.btn_manage_mangohud.set_sensitive(mangohud_available)
        self.switch_obsvkc.set_sensitive(obs_vkc_available)
        self.switch_vmtouch.set_sensitive(vmtouch_available)

    def __check_entry_name(self, *_args):
        if self.entry_name.get_text() != self.config.Name:
            is_duplicate = self.entry_name.get_text() in self.manager.local_bottles
            if is_duplicate:
                self.window.show_toast(_("This bottle name is already in use."))
                self.__valid_name = False
                self.entry_name.add_css_class("error")
                return
        self.__valid_name = True
        self.entry_name.remove_css_class("error")

    def __save_name(self, *_args):
        if not self.__valid_name:
            self.entry_name.set_text(self.config.Name)
            self.__valid_name = True
            return

        new_name = self.entry_name.get_text()
        self.config.Name

        self.manager.update_config(config=self.config, key="Name", value=new_name)

        self.window.page_library.update()
        self.details.view_bottle.label_name.set_text(self.config.Name)

    def choose_cwd(self, widget):
        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            path = dialog.get_file().get_path()

            self.manager.update_config(
                config=self.config, key="WorkingDir", value=dialog.get_file().get_path()
            )
            self.label_cwd.set_label(os.path.basename(path))
            self.btn_cwd_reset.set_visible(True)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Working Directory"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            parent=self.window,
        )

        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def reset_cwd(self, *_args):
        self.manager.update_config(config=self.config, key="WorkingDir", value="")
        self.label_cwd.set_label("(Default)")
        self.btn_cwd_reset.set_visible(False)

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
        self.combo_language.handler_block_by_func(self.__set_language)
        self.combo_windows.handler_block_by_func(self.__set_windows)

        for string_list in [
            self.str_list_runner,
            self.str_list_dxvk,
            self.str_list_vkd3d,
            self.str_list_nvapi,
            self.str_list_latencyflex,
            self.str_list_languages,
            self.str_list_windows,
        ]:
            string_list.splice(0, string_list.get_n_items())

        self.str_list_dxvk.append("Disabled")
        self.str_list_vkd3d.append("Disabled")
        self.str_list_latencyflex.append("Disabled")
        for index, dxvk in enumerate(self.manager.dxvk_available):
            self.str_list_dxvk.append(dxvk)

        for index, vkd3d in enumerate(self.manager.vkd3d_available):
            self.str_list_vkd3d.append(vkd3d)

        for index, runner in enumerate(self.manager.runners_available):
            self.str_list_runner.append(runner)

        for index, nvapi in enumerate(self.manager.nvapi_available):
            self.str_list_nvapi.append(nvapi)

        for index, latencyflex in enumerate(self.manager.latencyflex_available):
            self.str_list_latencyflex.append(latencyflex)

        for lang in ManagerUtils.get_languages():
            self.str_list_languages.append(lang)

        self.combo_runner.handler_unblock_by_func(self.__set_runner)
        self.combo_dxvk.handler_unblock_by_func(self.__set_dxvk)
        self.combo_vkd3d.handler_unblock_by_func(self.__set_vkd3d)
        self.combo_nvapi.handler_unblock_by_func(self.__set_nvapi)
        self.combo_latencyflex.handler_unblock_by_func(self.__set_latencyflex)
        self.combo_language.handler_unblock_by_func(self.__set_language)
        self.combo_windows.handler_unblock_by_func(self.__set_windows)

    def set_config(self, config: BottleConfig):
        self.config = config
        parameters = self.config.Parameters

        # temporary lock functions connected to the widgets
        self.switch_mangohud.handler_block_by_func(self.__toggle_feature)
        self.switch_nvapi.handler_block_by_func(self.__toggle_nvapi)
        self.switch_vkbasalt.handler_block_by_func(self.__toggle_feature)
        self.switch_fsr.handler_block_by_func(self.__toggle_feature)
        self.switch_obsvkc.handler_block_by_func(self.__toggle_feature)
        self.switch_gamemode.handler_block_by_func(self.__toggle_feature)
        self.switch_gamescope.handler_block_by_func(self.__toggle_feature)
        self.switch_sandbox.handler_block_by_func(self.__toggle_feature)
        self.switch_discrete.handler_block_by_func(self.__toggle_feature)
        with contextlib.suppress(TypeError):
            self.switch_steam_runtime.handler_block_by_func(self.__toggle_feature)
        self.combo_runner.handler_block_by_func(self.__set_runner)
        self.combo_dxvk.handler_block_by_func(self.__set_dxvk)
        self.combo_vkd3d.handler_block_by_func(self.__set_vkd3d)
        self.combo_nvapi.handler_block_by_func(self.__set_nvapi)
        self.combo_latencyflex.handler_block_by_func(self.__set_latencyflex)
        self.combo_windows.handler_block_by_func(self.__set_windows)
        self.combo_language.handler_block_by_func(self.__set_language)
        self.switch_mangohud.set_active(parameters.mangohud)
        self.switch_obsvkc.set_active(parameters.obsvkc)
        self.switch_vkbasalt.set_active(parameters.vkbasalt)
        self.switch_fsr.set_active(parameters.fsr)
        self.switch_nvapi.set_active(parameters.dxvk_nvapi)
        self.switch_gamemode.set_active(parameters.gamemode)
        self.switch_gamescope.set_active(parameters.gamescope)
        self.switch_sandbox.set_active(parameters.sandbox)
        self.switch_steam_runtime.set_active(parameters.use_steam_runtime)
        self.switch_vmtouch.set_active(parameters.vmtouch)

        # self.toggle_sync.set_active(parameters["sync"] == "wine")
        # self.toggle_esync.set_active(parameters["sync"] == "esync")
        # self.toggle_fsync.set_active(parameters["sync"] == "fsync")

        self.switch_discrete.set_active(parameters.discrete_gpu)

        self.btn_cwd_reset.set_visible(self.config.WorkingDir)

        self.entry_name.set_text(config.Name)

        self.row_cwd.set_subtitle(
            _(f'Directory that contains the data of "{config.Name}".')
        )

        self.combo_language.set_selected(
            ManagerUtils.get_languages(from_locale=self.config.Language, get_index=True)
        )

        # region Windows Versions
        # NOTE: this should not be here but it's the only way to handle windows
        # versions in the current structure, we will fix this in the future
        # with the new Bottles Backend.
        self.windows_versions = {
            "win11": "Windows 11",
            "win10": "Windows 10",
            "win81": "Windows 8.1",
            "win8": "Windows 8",
            "win7": "Windows 7",
            "win2008r2": "Windows 2008 R2",
            "win2008": "Windows 2008",
            # "vista": "Windows Vista", # TODO: implement this in the backend
            "winxp": "Windows XP",
        }

        if self.config.Arch == Arch.WIN32:
            self.windows_versions["win98"] = "Windows 98"
            self.windows_versions["win95"] = "Windows 95"

        for index, windows_version in enumerate(self.windows_versions):
            self.str_list_windows.append(self.windows_versions[windows_version])
            if windows_version == self.config.Windows:
                self.combo_windows.set_selected(index)
        # endregion

        parameters = self.config.Parameters

        _dxvk = self.config.DXVK
        if parameters.dxvk:
            if _dxvk in self.manager.dxvk_available:
                if _i_dxvk := self.manager.dxvk_available.index(_dxvk) + 1:
                    self.combo_dxvk.set_selected(_i_dxvk)
        else:
            self.combo_dxvk.set_selected(0)

        _vkd3d = self.config.VKD3D
        if parameters.vkd3d:
            if _vkd3d in self.manager.vkd3d_available:
                if _i_vkd3d := self.manager.vkd3d_available.index(_vkd3d) + 1:
                    self.combo_vkd3d.set_selected(_i_vkd3d)
        else:
            self.combo_vkd3d.set_selected(0)

        _nvapi = self.config.NVAPI
        if _nvapi in self.manager.nvapi_available:
            if _i_nvapi := self.manager.nvapi_available.index(_nvapi):
                self.combo_nvapi.set_selected(_i_nvapi)

        _latencyflex = self.config.LatencyFleX
        if parameters.latencyflex:
            if _latencyflex in self.manager.latencyflex_available:
                if (
                    _i_latencyflex := self.manager.latencyflex_available.index(
                        _latencyflex
                    )
                    + 1
                ):
                    self.combo_latencyflex.set_selected(_i_latencyflex)
        else:
            self.combo_latencyflex.set_selected(0)

        _runner = self.config.Runner
        if _runner in self.manager.runners_available:
            if _i_runner := self.manager.runners_available.index(_runner):
                self.combo_runner.set_selected(_i_runner)

        sync_types = [
            "wine",
            "esync",
            "fsync",
        ]
        for sync in sync_types:
            if sync == parameters.sync:
                self.combo_sync.set_selected(sync_types.index(sync))

        # unlock functions connected to the widgets
        self.switch_mangohud.handler_unblock_by_func(self.__toggle_feature)
        self.switch_nvapi.handler_unblock_by_func(self.__toggle_nvapi)
        self.switch_vkbasalt.handler_unblock_by_func(self.__toggle_feature)
        self.switch_fsr.handler_unblock_by_func(self.__toggle_feature)
        self.switch_obsvkc.handler_unblock_by_func(self.__toggle_feature)
        self.switch_gamemode.handler_unblock_by_func(self.__toggle_feature)
        self.switch_gamescope.handler_unblock_by_func(self.__toggle_feature)
        self.switch_sandbox.handler_unblock_by_func(self.__toggle_feature)
        self.switch_discrete.handler_unblock_by_func(self.__toggle_feature)
        with contextlib.suppress(TypeError):
            self.switch_steam_runtime.handler_unblock_by_func(self.__toggle_feature)
        self.combo_runner.handler_unblock_by_func(self.__set_runner)
        self.combo_dxvk.handler_unblock_by_func(self.__set_dxvk)
        self.combo_vkd3d.handler_unblock_by_func(self.__set_vkd3d)
        self.combo_nvapi.handler_unblock_by_func(self.__set_nvapi)
        self.combo_latencyflex.handler_unblock_by_func(self.__set_latencyflex)
        self.combo_windows.handler_unblock_by_func(self.__set_windows)
        self.combo_language.handler_unblock_by_func(self.__set_language)

        self.__set_steam_rules()

    def __show_display_settings(self, widget):
        new_window = DisplayDialog(
            parent_window=self.window,
            config=self.config,
            details=self.details,
            widget=widget,
            spinner_display=self.spinner_display,
        )
        new_window.present()

    def __show_feature_dialog(self, _widget: Gtk.Widget, dialog: Adw.Window) -> None:
        """Present dialog of a specific feature."""
        window = dialog(window=self.window, config=self.config)
        window.present()

    def __toggle_feature(self, _widget: Gtk.Widget, state: bool, key: str) -> None:
        """Toggle a specific feature."""
        self.config = self.manager.update_config(
            config=self.config, key=key, value=state, scope="Parameters"
        ).data["config"]

    def __set_sync_type(self, *_args):
        """
        Set the sync type (wine, esync, fsync)
        """
        sync_types = [
            "wine",
            "esync",
            "fsync",
        ]
        self.combo_sync.set_sensitive(False)
        RunAsync(
            self.manager.update_config,
            config=self.config,
            key="sync",
            value=sync_types[self.combo_sync.get_selected()],
            scope="Parameters",
        )
        self.combo_sync.set_sensitive(True)

    def __toggle_nvapi(self, widget=False, state=False):
        """Install/Uninstall NVAPI from the bottle"""
        self.set_nvapi_status(pending=True)

        RunAsync(
            task_func=self.manager.install_dll_component,
            callback=self.set_nvapi_status,
            config=self.config,
            component="nvapi",
            remove=not state,
        )

        self.__toggle_feature(widget=None, state=state, key="dxvk_nvapi")

    def __toggle_versioning_compression(self, widget, state):
        """Toggle the versioning compression for current bottle"""

        def update():
            self.config = self.manager.update_config(
                config=self.config,
                key="versioning_compression",
                value=state,
                scope="Parameters",
            ).data["config"]

        update()

    def __set_runner(self, *_args):
        """Set the runner to use for the bottle"""

        def set_widgets_status(status=True):
            for w in [
                self.combo_runner,
                self.switch_nvapi,
                self.combo_dxvk,
                self.combo_nvapi,
                self.combo_vkd3d,
            ]:
                w.set_sensitive(status)
            if status:
                self.spinner_runner.stop()
                self.spinner_runner.set_visible(False)
            else:
                self.spinner_runner.start()
                self.spinner_runner.set_visible(True)

        @GtkUtils.run_in_main_loop
        def update(result: Result[dict], error=False):
            if isinstance(result, Result) and isinstance(
                result.data, dict
            ):  # expecting Result[dict].data["config"]
                self.details.update_runner_label(runner)

                if "config" in result.data:
                    self.config = result.data["config"]
                if self.config.Parameters.use_steam_runtime:
                    self.switch_steam_runtime.handler_block_by_func(
                        self.__toggle_feature
                    )
                    self.switch_steam_runtime.set_active(True)
                    self.switch_steam_runtime.handler_unblock_by_func(
                        self.__toggle_feature
                    )

            set_widgets_status(True)

        set_widgets_status(False)
        runner = self.manager.runners_available[self.combo_runner.get_selected()]

        def run_task(status=True):
            if not status:
                update(Result(True))
                self.combo_runner.handler_block_by_func(self.__set_runner)
                self.combo_runner.handler_unblock_by_func(self.__set_runner)
                return

            RunAsync(
                Runner.runner_update,
                callback=update,
                config=self.config,
                manager=self.manager,
                runner=runner,
            )

        if re.search("^(GE-)?Proton", runner):
            dialog = ProtonAlertDialog(self.window, run_task)
            dialog.show()
        else:
            run_task()

    def __dll_component_task_func(self, *args, **kwargs):
        # Remove old version
        self.manager.install_dll_component(
            config=kwargs["config"], component=kwargs["component"], remove=True
        )
        # Install new version
        self.manager.install_dll_component(
            config=kwargs["config"], component=kwargs["component"]
        )

    def __set_dxvk(self, *_args):
        """Set the DXVK version to use for the bottle"""
        self.set_dxvk_status(pending=True)

        if (self.combo_dxvk.get_selected()) == 0:
            self.set_dxvk_status(pending=True)

            if self.combo_vkd3d.get_selected() != 0:
                logging.info("VKD3D is enabled, disabling")
                self.combo_vkd3d.set_selected(0)

            RunAsync(
                task_func=self.manager.install_dll_component,
                callback=self.set_dxvk_status,
                config=self.config,
                component="dxvk",
                remove=True,
            )

            self.config = self.manager.update_config(
                config=self.config, key="dxvk", value=False, scope="Parameters"
            ).data["config"]
        else:
            dxvk = self.manager.dxvk_available[self.combo_dxvk.get_selected() - 1]
            self.config = self.manager.update_config(
                config=self.config, key="DXVK", value=dxvk
            ).data["config"]

            RunAsync(
                task_func=self.__dll_component_task_func,
                callback=self.set_dxvk_status,
                config=self.config,
                component="dxvk",
            )

            self.config = self.manager.update_config(
                config=self.config, key="dxvk", value=True, scope="Parameters"
            ).data["config"]

    def __set_vkd3d(self, *_args):
        """Set the VKD3D version to use for the bottle"""
        self.set_vkd3d_status(pending=True)

        if (self.combo_vkd3d.get_selected()) == 0:
            self.set_vkd3d_status(pending=True)

            RunAsync(
                task_func=self.manager.install_dll_component,
                callback=self.set_vkd3d_status,
                config=self.config,
                component="vkd3d",
                remove=True,
            )

            self.config = self.manager.update_config(
                config=self.config, key="vkd3d", value=False, scope="Parameters"
            ).data["config"]
        else:
            if self.combo_dxvk.get_selected() == 0:
                logging.info("DXVK is disabled, reenabling")
                self.combo_dxvk.set_selected(1)

            vkd3d = self.manager.vkd3d_available[self.combo_vkd3d.get_selected() - 1]
            self.config = self.manager.update_config(
                config=self.config, key="VKD3D", value=vkd3d
            ).data["config"]

            RunAsync(
                task_func=self.__dll_component_task_func,
                callback=self.set_vkd3d_status,
                config=self.config,
                component="vkd3d",
            )

            self.config = self.manager.update_config(
                config=self.config, key="vkd3d", value=True, scope="Parameters"
            ).data["config"]

    def __set_nvapi(self, *_args):
        """Set the NVAPI version to use for the bottle"""
        self.set_nvapi_status(pending=True)

        self.switch_nvapi.set_active(True)

        nvapi = self.manager.nvapi_available[self.combo_nvapi.get_selected()]
        self.config = self.manager.update_config(
            config=self.config, key="NVAPI", value=nvapi
        ).data["config"]

        RunAsync(
            task_func=self.__dll_component_task_func,
            callback=self.set_nvapi_status,
            config=self.config,
            component="nvapi",
        )

        self.config = self.manager.update_config(
            config=self.config, key="dxvk_nvapi", value=True, scope="Parameters"
        ).data["config"]

    def __set_latencyflex(self, *_args):
        """Set the latency flex value"""
        if self.combo_latencyflex.get_selected() == 0:
            RunAsync(
                task_func=self.manager.install_dll_component,
                callback=self.set_latencyflex_status,
                config=self.config,
                component="latencyflex",
                remove=True,
            )

            self.config = self.manager.update_config(
                config=self.config, key="latencyflex", value=False, scope="Parameters"
            ).data["config"]
        else:
            latencyflex = self.manager.latencyflex_available[
                self.combo_latencyflex.get_selected() - 1
            ]
            self.config = self.manager.update_config(
                config=self.config, key="LatencyFleX", value=latencyflex
            ).data["config"]

            RunAsync(
                task_func=self.__dll_component_task_func,
                callback=self.set_latencyflex_status,
                config=self.config,
                component="latencyflex",
            )
            self.config = self.manager.update_config(
                config=self.config, key="latencyflex", value=True, scope="Parameters"
            ).data["config"]

    def __set_windows(self, *_args):
        """Set the Windows version to use for the bottle"""

        # self.manager.dxvk_available[self.combo_dxvk.get_selected()]
        @GtkUtils.run_in_main_loop
        def update(result, error=False):
            self.spinner_windows.stop()
            self.spinner_windows.set_visible(False)
            self.combo_windows.set_sensitive(True)

        self.spinner_windows.start()
        self.spinner_windows.set_visible(True)
        self.combo_windows.set_sensitive(False)
        rk = RegKeys(self.config)

        for index, windows_version in enumerate(self.windows_versions):
            if self.combo_windows.get_selected() == index:
                self.config = self.manager.update_config(
                    config=self.config, key="Windows", value=windows_version
                ).data["config"]

                RunAsync(rk.lg_set_windows, callback=update, version=windows_version)
                break

    def __set_language(self, *_args):
        """Set the language to use for the bottle"""
        index = self.combo_language.get_selected()
        language = ManagerUtils.get_languages(from_index=index)
        self.config = self.manager.update_config(
            config=self.config,
            key="Language",
            value=language[0],
        ).data["config"]

    @GtkUtils.run_in_main_loop
    def set_dxvk_status(self, status=None, error=None, pending=False):
        """Set the dxvk status"""
        self.combo_dxvk.set_sensitive(not pending)
        if pending:
            self.spinner_dxvk.start()
            self.spinner_dxvk.set_visible(True)
        else:
            self.spinner_dxvk.stop()
            self.spinner_dxvk.set_visible(False)

    @GtkUtils.run_in_main_loop
    def set_vkd3d_status(self, status=None, error=None, pending=False):
        """Set the vkd3d status"""
        self.combo_vkd3d.set_sensitive(not pending)
        if pending:
            self.spinner_vkd3d.start()
            self.spinner_vkd3d.set_visible(True)
        else:
            self.spinner_vkd3d.stop()
            self.spinner_vkd3d.set_visible(False)

    @GtkUtils.run_in_main_loop
    def set_nvapi_status(self, status=None, error=None, pending=False):
        """Set the nvapi status"""
        self.switch_nvapi.set_sensitive(not pending)
        self.combo_nvapi.set_sensitive(not pending)
        if pending:
            self.spinner_nvapi.start()
            self.spinner_nvapibool.start()
            self.spinner_nvapi.set_visible(True)
            self.spinner_nvapibool.set_visible(True)
        else:
            self.spinner_nvapi.stop()
            self.spinner_nvapibool.stop()
            self.spinner_nvapi.set_visible(False)
            self.spinner_nvapibool.set_visible(False)

    @GtkUtils.run_in_main_loop
    def set_latencyflex_status(self, status=None, error=None, pending=False):
        """Set the latencyflex status"""
        self.combo_latencyflex.set_sensitive(not pending)
        if pending:
            self.spinner_latencyflex.start()
            self.spinner_latencyflex.set_visible(True)
        else:
            self.spinner_latencyflex.stop()
            self.spinner_latencyflex.set_visible(False)

    def __set_steam_rules(self):
        """Set the Steam Environment specific rules"""
        status = self.config.Environment != "Steam"

        for w in [
            self.row_discrete,
            self.combo_dxvk,
            self.row_sandbox,
            self.group_details,
        ]:
            w.set_visible(status)
            w.set_sensitive(status)

        self.row_sandbox.set_visible(
            self.window.settings.get_boolean("experiments-sandbox")
        )
