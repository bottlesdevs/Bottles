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

import os
import re
import webbrowser
from datetime import datetime
from gettext import gettext as _
from gi.repository import Gtk, GLib, Handy

from ..dialogs.generic import MessageDialog
from ..dialogs.duplicate import DuplicateDialog
from ..dialogs.runargs import RunArgsDialog
from ..dialogs.envvars import EnvVarsDialog
from ..dialogs.dlloverrides import DLLOverridesDialog

from ..widgets.page import PageRow
from ..widgets.installer import InstallerEntry
from ..widgets.state import StateEntry
from ..widgets.program import ProgramEntry
from ..widgets.dependency import DependencyEntry

from ..backend.runner import Runner, gamemode_available
from ..backend.backup import RunnerBackup


pages = {}

@Gtk.Template(resource_path='/com/usebottles/bottles/details.ui')
class DetailsView(Handy.Leaflet):
    __gtype_name__ = 'Details'

    # region Widgets
    label_runner = Gtk.Template.Child()
    label_state = Gtk.Template.Child()
    label_environment = Gtk.Template.Child()
    label_arch = Gtk.Template.Child()
    btn_rename = Gtk.Template.Child()
    btn_winecfg = Gtk.Template.Child()
    btn_debug = Gtk.Template.Child()
    btn_execute = Gtk.Template.Child()
    btn_run_args = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_cmd = Gtk.Template.Child()
    btn_taskmanager = Gtk.Template.Child()
    btn_controlpanel = Gtk.Template.Child()
    btn_uninstaller = Gtk.Template.Child()
    btn_regedit = Gtk.Template.Child()
    btn_shutdown = Gtk.Template.Child()
    btn_reboot = Gtk.Template.Child()
    btn_killall = Gtk.Template.Child()
    btn_programs_updates = Gtk.Template.Child()
    btn_programs_add = Gtk.Template.Child()
    btn_environment_variables = Gtk.Template.Child()
    btn_overrides = Gtk.Template.Child()
    btn_backup_config = Gtk.Template.Child()
    btn_backup_full = Gtk.Template.Child()
    btn_duplicate = Gtk.Template.Child()
    btn_add_state = Gtk.Template.Child()
    btn_delete = Gtk.Template.Child()
    btn_flatpak_doc = Gtk.Template.Child()
    btn_flatpak_doc_home = Gtk.Template.Child()
    btn_flatpak_doc_expose = Gtk.Template.Child()
    btn_flatpak_doc_upgrade = Gtk.Template.Child()
    btn_manage_runners = Gtk.Template.Child()
    btn_manage_dxvk = Gtk.Template.Child()
    btn_manage_vkd3d = Gtk.Template.Child()
    btn_manage_nvapi = Gtk.Template.Child()
    btn_help_versioning = Gtk.Template.Child()
    btn_help_debug = Gtk.Template.Child()
    btn_request_dependency = Gtk.Template.Child()
    btn_cwd = Gtk.Template.Child()
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
    toggle_sync = Gtk.Template.Child()
    toggle_esync = Gtk.Template.Child()
    toggle_fsync = Gtk.Template.Child()
    combo_fsr = Gtk.Template.Child()
    combo_virt_res = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    combo_dxvk = Gtk.Template.Child()
    combo_vkd3d = Gtk.Template.Child()
    combo_nvapi = Gtk.Template.Child()
    list_dependencies = Gtk.Template.Child()
    list_programs = Gtk.Template.Child()
    list_installers = Gtk.Template.Child()
    list_states = Gtk.Template.Child()
    list_pages = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    entry_state_comment = Gtk.Template.Child()
    entry_search_deps = Gtk.Template.Child()
    pop_state = Gtk.Template.Child()
    grid_versioning = Gtk.Template.Child()
    group_programs = Gtk.Template.Child()
    stack_bottle = Gtk.Template.Child()
    infobar_testing = Gtk.Template.Child()
    row_cwd = Gtk.Template.Child()
    row_uninstaller = Gtk.Template.Child()
    row_regedit = Gtk.Template.Child()
    row_browse = Gtk.Template.Child()
    actions_programs = Gtk.Template.Child()
    actions_versioning = Gtk.Template.Child()
    actions_installers = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config={}, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.versioning_manager = window.manager.versioning_manager
        self.config = config

        if "FLATPAK_ID" in os.environ:
            '''
            If Flatpak, show the btn_flatpak_doc widget to reach
            the documentation on how to expose directories
            '''
            self.btn_flatpak_doc.set_visible(True)

        # region signals
        self.entry_name.connect('key-release-event', self.__check_entry_name)

        self.btn_winecfg.connect('activate', self.run_winecfg)
        self.btn_debug.connect('activate', self.run_debug)
        self.btn_execute.connect('activate', self.run_executable)
        self.btn_run_args.connect('activate', self.__run_executable_with_args)
        self.btn_browse.connect('activate', self.run_browse)
        self.btn_cmd.connect('activate', self.run_cmd)
        self.btn_taskmanager.connect('activate', self.run_taskmanager)
        self.btn_controlpanel.connect('activate', self.run_controlpanel)
        self.btn_uninstaller.connect('activate', self.run_uninstaller)
        self.btn_regedit.connect('activate', self.run_regedit)
        self.btn_overrides.connect('activate', self.__show_dll_overrides_view)
        self.btn_environment_variables.connect(
            'activate', self.__show_environment_variables
        )
        self.btn_cwd.connect('activate', self.choose_cwd)

        self.btn_winecfg.connect('pressed', self.run_winecfg)
        self.btn_debug.connect('pressed', self.run_debug)
        self.btn_execute.connect('pressed', self.run_executable)
        self.btn_run_args.connect('pressed', self.__run_executable_with_args)
        self.btn_browse.connect('pressed', self.run_browse)
        self.btn_cmd.connect('pressed', self.run_cmd)
        self.btn_taskmanager.connect('pressed', self.run_taskmanager)
        self.btn_controlpanel.connect('pressed', self.run_controlpanel)
        self.btn_uninstaller.connect('pressed', self.run_uninstaller)
        self.btn_regedit.connect('pressed', self.run_regedit)
        self.btn_delete.connect('pressed', self.__confirm_delete)
        self.btn_overrides.connect('pressed', self.__show_dll_overrides_view)
        self.btn_manage_runners.connect('pressed', self.window.show_prefs_view)
        self.btn_manage_dxvk.connect('pressed', self.window.show_prefs_view)
        self.btn_manage_vkd3d.connect('pressed', self.window.show_prefs_view)
        self.btn_manage_nvapi.connect('pressed', self.window.show_prefs_view)
        self.btn_cwd.connect('pressed', self.choose_cwd)
        self.btn_shutdown.connect('pressed', self.run_shutdown)
        self.btn_reboot.connect('pressed', self.run_reboot)
        self.btn_killall.connect('pressed', self.run_killall)
        self.btn_programs_updates.connect('pressed', self.update_programs)
        self.btn_programs_add.connect('pressed', self.__add_program)
        self.btn_environment_variables.connect(
            'pressed', self.__show_environment_variables
        )
        self.btn_backup_config.connect('pressed', self.__backup_config)
        self.btn_backup_full.connect('pressed', self.__backup_full)
        self.btn_duplicate.connect('pressed', self.__duplicate)
        self.btn_add_state.connect('pressed', self.__add_state)
        self.btn_help_versioning.connect(
            'pressed', self.open_doc_url, "bottles/versioning"
        )
        self.btn_help_debug.connect(
            'pressed',
            self.open_doc_url,
            "utilities/logs-and-debugger#wine-debugger"
        )
        self.btn_request_dependency.connect(
            'pressed', 
            self.open_doc_url, 
            "contribute/missing-dependencies"
        )
        self.btn_flatpak_doc_home.connect(
            'pressed', 
            self.open_doc_url, 
            "flatpak/expose-directories/use-system-home"
        )
        self.btn_flatpak_doc_expose.connect(
            'pressed', 
            self.open_doc_url, 
            "flatpak/expose-directories"
        )
        self.btn_flatpak_doc_upgrade.connect(
            'pressed', 
            self.open_doc_url, 
            "flatpak/migrate-bottles-to-flatpak"
        )

        self.btn_rename.connect('toggled', self.__toggle_rename)
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

        self.entry_search_deps.connect(
            'key-release-event', self.__search_dependencies
        )
        self.entry_search_deps.connect('changed', self.__search_dependencies)
        self.entry_state_comment.connect(
            'key-release-event', self.check_entry_state_comment
        )

        self.list_pages.connect('row-selected', self.__change_page)
        self.stack_bottle.connect('notify::visible-child', self.__on_page_change)
        # endregion

        '''
        Toggle the gamemode sensitivity based on gamemode_available
        also update the tooltip text with an helpfull message if it
        is not available.
        '''
        self.switch_gamemode.set_sensitive(gamemode_available)
        if not gamemode_available:
            self.switch_gamemode.set_tooltip_text(
                _("Gamemode is either not available on your system or not running."))

        self.build_pages()

        if "TESTING_REPOS" in os.environ and os.environ["TESTING_REPOS"] == "1":
            self.infobar_testing.set_visible(True)

    def __on_page_change(self, *args):
        '''
        Update headerbar title according to the current page.
        '''
        global pages
        page = self.stack_bottle.get_visible_child_name()
        self.window.set_title(pages[page]['title'], pages[page]['description'])
        if page == "programs":
            self.window.set_actions(self.actions_programs)
        elif page == "versioning":
            self.window.set_actions(self.actions_versioning)
        elif page == "installers":
            self.window.set_actions(self.actions_installers)
        else:
            self.window.set_actions(None)

    def __update_by_env(self):
        widgets = [
            self.row_uninstaller,
            self.row_regedit,
            self.row_browse
        ]
        for widget in widgets:
            if self.config.get("Environment") == "Layered":
                widget.set_visible(False)
            else:
                widget.set_visible(True)

    def build_pages(self):
        '''
        This function build the pages list according to the
        user settings (some pages are shown only if experimental
        features are enabled).
        '''
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
            }
        }

        if not self.window.settings.get_boolean("experiments-versioning"):
            del pages["versioning"]

        if not self.window.settings.get_boolean("experiments-installers"):
            del pages["installers"]

        for w in self.list_pages.get_children():
            w.destroy()

        for p in pages:
            self.list_pages.add(PageRow(p, pages[p]))

    def __change_page(self, widget, row):
        '''
        This function try to change the page based on user choice, if
        the page is not available, it will show the "bottle" page.
        '''
        try:
            self.stack_bottle.set_visible_child_name(row.page_name)
        except AttributeError:
            self.stack_bottle.set_visible_child_name("bottle")

    def __search_dependencies(self, widget, event=None, data=None):
        '''
        This function search in the list of dependencies the
        text written in the search entry.
        '''
        terms = widget.get_text()
        self.list_dependencies.set_filter_func(
            self.__filter_dependencies,
            terms
        )

    @staticmethod
    def __filter_dependencies(row, terms=None):
        if terms.lower() in row.get_title().lower():
            return True
        return False

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
            Runner().get_bottle_path(self.config)
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
        '''
        This function update widgets according to the bottle
        configuration. It also temporarily disable the functions
        connected to the widgets to avoid the bottle configuration 
        to be updated during this process.
        '''
        self.config = config
        self.__update_by_env()

        # format update_date
        update_date = datetime.strptime(
            config.get("Update_Date"),
            "%Y-%m-%d %H:%M:%S.%f"
        )
        update_date = update_date.strftime("%b %d %Y %H:%M:%S")

        # format arch
        arch = _("64-bit")
        if self.config.get("Arch") == "win32":
            arch = _("32-bit")

        # temporary lcok functions connected to the widgets
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

        # update widgets data with bottle configuration
        parameters = self.config.get("Parameters")
        self.entry_name.set_text(self.config.get("Name"))
        self.entry_name.set_tooltip_text(_("Updated: %s" % update_date))
        self.label_runner.set_text(self.config.get("Runner"))
        self.label_arch.set_text(arch)
        self.label_environment.set_text(
            _(self.config.get("Environment"))
        )
        self.label_environment.get_style_context().add_class(
            f"tag-{self.config.get('Environment').lower()}"
        )
        self.label_state.set_text(str(self.config.get("State")))
        self.switch_dxvk.set_active(parameters["dxvk"])
        self.switch_dxvk_hud.set_active(parameters["dxvk_hud"])
        self.switch_vkd3d.set_active(parameters["vkd3d"])
        self.switch_nvapi.set_active(parameters["dxvk_nvapi"])
        self.switch_gamemode.set_active(parameters["gamemode"])
        self.switch_fsr.set_active(parameters["fsr"])
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
        self.grid_versioning.set_visible(self.config.get("Versioning"))

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

        self.update_programs()
        self.__update_dependencies()
        self.__update_installers()
        self.update_states()

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

    def __check_entry_name(self, widget, event_key):
        '''
        This function check if the entry name is valid, looking
        for special characters. It also toggle the widget icon
        and the save button sensitivity according to the result.
        '''
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:.;,]')
        name = widget.get_text()

        if(regex.search(name) is None) and name != "":
            self.btn_rename.set_sensitive(True)
            widget.set_icon_from_icon_name(1, "")
        else:
            self.btn_rename.set_sensitive(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")

    def __toggle_rename(self, widget):
        '''
        This function toggle the entry_name editability. It will
        also update the bottle configuration with the new bottle name
        if the entry_name status is False (not editable).
        '''
        status = widget.get_active()
        self.entry_name.set_editable(status)

        if status:
            self.entry_name.grab_focus()
        else:
            self.manager.update_config(
                config=self.config,
                key="Name",
                value=self.entry_name.get_text()
            )

    def __add_program(self, widget=False):
        '''
        This function popup the add program dialog to the user. It
        will also update the bottle configuration, appending the
        path to the program picked by the user. It will also update
        the programs list.
        The file chooser path is set to the bottle path by default.
        '''
        file_dialog = Gtk.FileChooserNative.new(
            _("Choose an executable path"),
            self.window,
            Gtk.FileChooserAction.OPEN,
            _("Add"),
            _("Cancel")
        )
        file_dialog.set_current_folder(
            Runner().get_bottle_path(self.config)
        )
        response = file_dialog.run()

        if response == -3:
            self.manager.update_config(
                config=self.config,
                key=file_dialog.get_filename().split("/")[-1][:-4],
                value=file_dialog.get_filename(),
                scope="External_Programs"
            )
            self.update_programs()

        file_dialog.destroy()

    def update_programs(self, widget=False):
        '''
        This function update the programs lists. The list in the
        details page is limited to 5 items.
        '''
        for w in self.list_programs:
            w.destroy()
        for w in self.group_programs:
            w.destroy()

        programs = self.manager.get_programs(self.config)

        if len(programs) == 0:
            self.group_programs.set_visible(False)
            return

        self.group_programs.set_visible(True)

        i = 0
        for program in programs:
            self.list_programs.add(ProgramEntry(
                self.window, self.config, program))

            # append first 5 entries to group_programs
            if i < 5:
                self.group_programs.add(ProgramEntry(
                    self.window, self.config, program))
            i = + 1

    def __update_dependencies(self, widget=False):
        '''
        This function update the dependencies list with the
        supported by the manager.
        '''
        for w in self.list_dependencies:
            w.destroy()

        supported_dependencies = self.manager.supported_dependencies
        if len(supported_dependencies.items()) > 0:
            for dependency in supported_dependencies.items():
                if dependency[0] in self.config.get("Installed_Dependencies"):
                    '''
                    If the dependency is already installed, do not
                    list it in the list. It will be listed in the
                    installed dependencies list.
                    '''
                    continue
                self.list_dependencies.add(
                    DependencyEntry(
                        window=self.window,
                        config=self.config,
                        dependency=dependency
                    )
                )

        if len(self.config.get("Installed_Dependencies")) > 0:
            for dependency in self.config.get("Installed_Dependencies"):
                plain = True
                if dependency in supported_dependencies:
                    dependency = (
                        dependency,
                        supported_dependencies[dependency]
                    )
                    plain = False

                self.list_dependencies.add(
                    DependencyEntry(
                        window=self.window,
                        config=self.config,
                        dependency=dependency,
                        plain=plain
                    )
                )

    def __update_installers(self, widget=False):
        '''
        This function update the installers list with the
        supported by the manager.
        '''
        for w in self.list_installers:
            w.destroy()

        supported_installers = self.manager.supported_installers.items()

        if len(supported_installers) > 0:
            for installer in supported_installers:
                self.list_installers.add(
                    InstallerEntry(
                        window=self.window,
                        config=self.config,
                        installer=installer
                    )
                )

    def __idle_update_states(self, widget=False):
        '''
        This function update the states list with the
        ones from the bottle configuration.
        '''
        if self.config.get("Versioning"):
            for w in self.list_states:
                w.destroy()

            states = self.versioning_manager.list_states(
                self.config
            ).items()

            if len(states) > 0:
                for state in states:
                    self.list_states.add(
                        StateEntry(
                            window=self.window,
                            config=self.config,
                            state=state
                        )
                    )

    def update_states(self, widget=False):
        GLib.idle_add(self.__idle_update_states, widget=False)

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
            self.manager.install_dxvk(
                config=self.config,
                widget=widget
            )
        else:
            self.manager.remove_dxvk(
                config=self.config,
                widget=widget
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
            self.manager.install_vkd3d(
                config=self.config,
                widget=widget
            )
        else:
            self.manager.remove_vkd3d(
                config=self.config,
                widget=widget
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
            self.manager.install_nvapi(
                config=self.config,
                widget=widget
            )
        else:
            self.manager.remove_nvapi(
                config=self.config,
                widget=widget
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
        self.manager.toggle_virtual_desktop(
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
            self.manager.toggle_virtual_desktop(
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

    def __run_executable_with_args(self, widget):
        '''
        This function pop up the dialog to run an executable with
        custom arguments.
        '''
        new_window = RunArgsDialog(self)
        new_window.present()

    def run_executable(self, widget, args=False):
        '''
        This function pop up the dialog to run an executable.
        The file will be executed by the runner after the
        user confirmation.
        '''
        file_dialog = Gtk.FileChooserNative.new(
            _("Choose a Windows executable file"),
            self.window,
            Gtk.FileChooserAction.OPEN,
            _("Run"),
            _("Cancel")
        )

        response = file_dialog.run()

        if response == -3:
            if args:
                Runner().run_executable(
                    config=self.config,
                    file_path=file_dialog.get_filename(),
                    arguments=args
                )
            else:
                Runner().run_executable(
                    config=self.config,
                    file_path=file_dialog.get_filename()
                )

        file_dialog.destroy()

    def check_entry_state_comment(self, widget, event_key):
        '''
        This function check if the entry state comment is valid,
        looking for special characters. It also toggle the widget icon
        and the save button sensitivity according to the result.
        '''
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:.;,"]')
        comment = widget.get_text()

        if(regex.search(comment) is None):
            self.btn_add_state.set_sensitive(True)
            widget.set_icon_from_icon_name(1, "")
        else:
            self.btn_add_state.set_sensitive(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")

    def __add_state(self, widget):
        '''
        This function create ask the versioning manager to
        create a new bottle state with the given comment.
        '''
        comment = self.entry_state_comment.get_text()
        if comment != "":
            self.versioning_manager.create_state(
                config=self.config,
                comment=comment,
                after=self.update_states
            )
            self.entry_state_comment.set_text("")
            self.pop_state.popdown()

    def __backup_config(self, widget):
        '''
        This function pop up the a file chooser where the user
        can select the path where to export the bottle configuration
        backup. It will also ask the RunnerBackup to export the new
        backup after the user confirmation.
        '''
        file_dialog = Gtk.FileChooserDialog(
            _("Select the location where to save the backup config"),
            self.window,
            Gtk.FileChooserAction.SAVE,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        )
        file_dialog.set_current_name("backup_%s.yml" % self.config.get("Path"))

        response = file_dialog.run()

        if response == Gtk.ResponseType.OK:
            RunnerBackup().export_backup(
                self.window,
                self.config,
                "config",
                file_dialog.get_filename()
            )

        file_dialog.destroy()

    def __backup_full(self, widget):
        '''
        This function pop up the a file chooser where the user
        can select the path where to export the bottle full backup. 
        It will also ask the RunnerBackup to export the backup
        after the user confirmation.
        '''
        file_dialog = Gtk.FileChooserDialog(
            _("Select the location where to save the backup archive"),
            self.window,
            Gtk.FileChooserAction.SAVE,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        )
        file_dialog.set_current_name(
            "backup_%s.tar.gz" % self.config.get("Path")
        )

        response = file_dialog.run()

        if response == Gtk.ResponseType.OK:
            RunnerBackup().export_backup(
                self.window,
                self.config,
                "full",
                file_dialog.get_filename()
            )

        file_dialog.destroy()

    def __duplicate(self, widget):
        '''
        This function pop up the duplicate dialog, so the user can
        choose the new bottle name and perform duplication.
        '''
        new_window = DuplicateDialog(self)
        new_window.present()

    def __confirm_delete(self, widget):
        '''
        This function pop up the delete confirm dialog. If user confirm
        it will ask the manager to delete the bottle and will return
        to the bottles list.
        '''
        dialog_delete = MessageDialog(
            parent=self.window,
            title=_("Confirm deletion"),
            message=_(
                "Are you sure you want to delete this Bottle and all files?"
            )
        )
        response = dialog_delete.run()

        if response == Gtk.ResponseType.OK:
            self.manager.delete_bottle(self.config)
            self.window.go_back()

        dialog_delete.destroy()

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

    '''
    The following functions are used like wrappers for the
    runner utilities.
    '''

    def run_winecfg(self, widget):
        Runner().run_winecfg(self.config)

    def run_debug(self, widget):
        Runner().run_debug(self.config)

    def run_browse(self, widget):
        Runner().open_filemanager(self.config)

    def run_cmd(self, widget):
        Runner().run_cmd(self.config)

    def run_taskmanager(self, widget):
        Runner().run_taskmanager(self.config)

    def run_controlpanel(self, widget):
        Runner().run_controlpanel(self.config)

    def run_uninstaller(self, widget):
        Runner().run_uninstaller(self.config)

    def run_regedit(self, widget):
        Runner().run_regedit(self.config)

    def run_shutdown(self, widget):
        Runner().send_status(self.config, "shutdown")

    def run_reboot(self, widget):
        Runner().send_status(self.config, "reboot")

    def run_killall(self, widget):
        Runner().send_status(self.config, "kill")

    '''
    The following methods open resources (URLs) in the
    system browser.
    '''
    @staticmethod
    def open_report_url(widget):
        webbrowser.open_new_tab(
            "https://github.com/bottlesdevs/dependencies/issues/new/choose")

    @staticmethod
    def open_doc_url(widget, page):
        webbrowser.open_new_tab(f"https://docs.usebottles.com/{page}")
