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

from gi.repository import Gtk, GLib, Handy

import os
import re
import webbrowser
from datetime import datetime

from .dialog import BottlesDialog, BottlesMessageDialog
from ..installer_manager import InstallerManager
from ..runner_utilities import RunnerUtilities, gamemode_available
from ..runner_backup import RunnerBackup

class BottlesDetailsPageRow(Gtk.ListBoxRow):

    def __init__(self, page_name, title, **kwargs):
        super().__init__(**kwargs)
        self.page_name = page_name

        icons = {
            "bottle": "com.usebottles.bottles-symbolic",
            "preferences": "applications-system-symbolic",
            "dependencies": "application-x-addon-symbolic",
            "programs": "preferences-desktop-apps-symbolic",
            "versioning": "preferences-system-time-symbolic",
            "installers": "system-software-install-symbolic"
        }

        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, 
            spacing=6
        )
        icon = Gtk.Image()
        icon.set_from_icon_name(icons[page_name], Gtk.IconSize.SMALL_TOOLBAR)
        box.pack_start(icon, False, False, 0)

        box.pack_start(Gtk.Label(
            label=title,
            xalign=0.0
        ), False, False, 0)

        self.get_style_context().add_class("page-row")

        self.add(box)

        self.show_all()

@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-run-args.ui')
class BottlesRunArgs(Handy.Window):
    __gtype_name__ = 'BottlesRunArgs'

    '''Get widgets from template'''
    entry_args = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_run = Gtk.Template.Child()

    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent.window)

        '''Common variables'''
        self.parent = parent

        '''Signal connections'''
        self.btn_cancel.connect('pressed', self.close_window)
        self.btn_run.connect('pressed', self.run_executable)

    '''Destroy the window'''
    def close_window(self, widget=None):
        self.destroy()

    '''Run executable with args'''
    def run_executable(self, widget):
        args = self.entry_args.get_text()
        self.parent.run_executable(False, args)
        self.close_window()

@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-environment-variables.ui')
class BottlesEnvironmentVariables(Handy.Window):
    __gtype_name__ = 'BottlesEnvironmentVariables'

    '''Get widgets from template'''
    entry_variables = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()

    def __init__(self, window, configuration, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.configuration = configuration
        self.variables = configuration["Parameters"]["environment_variables"]

        '''Populate widgets'''
        self.entry_variables.set_text(self.variables)

        '''Signal connections'''
        self.btn_cancel.connect('pressed', self.close_window)
        self.btn_save.connect('pressed', self.save_variables)

    '''Destroy the window'''
    def close_window(self, widget):
        self.destroy()

    '''Save launch options'''
    def save_variables(self, widget):
        self.variables = self.entry_variables.get_text()
        self.runner.update_configuration(configuration=self.configuration,
                                         key="environment_variables",
                                         value=self.variables,
                                         scope="Parameters")
        self.close_window(widget)
        self.window.page_details.update_programs()

@Gtk.Template(resource_path='/com/usebottles/bottles/dll-override-entry.ui')
class BottlesDLLOverrideEntry(Handy.ActionRow):
    __gtype_name__ = 'BottlesDLLOverrideEntry'

    '''Get widgets from template'''
    btn_remove = Gtk.Template.Child()
    combo_type = Gtk.Template.Child()

    def __init__(self, window, configuration, override, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.configuration = configuration
        self.override = override

        '''Populate widgets'''
        self.set_title(self.override[0])
        self.combo_type.set_active_id(self.override[1])

        '''Signal connections'''
        self.btn_remove.connect('pressed', self.remove_override)
        self.combo_type.connect('changed', self.set_override_type)

    def set_override_type(self, widget):
        override_type = widget.get_active_id()
        self.runner.update_configuration(configuration=self.configuration,
                                         key=self.override[0],
                                         value=override_type,
                                         scope="DLL_Overrides")

    '''Remove DLL override'''
    def remove_override(self, widget):
        '''Remove override from bottle configuration'''
        self.runner.update_configuration(configuration=self.configuration,
                                         key=self.override[0],
                                         value=False,
                                         scope="DLL_Overrides",
                                         remove=True)

        '''Remove entry from list_overrides'''
        self.destroy()

@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-dll-overrides.ui')
class BottlesDLLOverrides(Handy.Window):
    __gtype_name__ = 'BottlesDLLOverrides'

    '''Get widgets from template'''
    entry_name = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    list_overrides = Gtk.Template.Child()

    def __init__(self, window, configuration, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.configuration = configuration

        '''Populate widgets'''
        self.populate_overrides_list()

        '''Signal connections'''
        self.btn_save.connect('pressed', self.save_override)

    '''Save new DLL override'''
    def idle_save_override(self, widget=False):
        dll_name = self.entry_name.get_text()

        if dll_name !=  "":
            '''Store new override in bottle configuration'''
            self.runner.update_configuration(configuration=self.configuration,
                                             key=dll_name,
                                             value="n,b",
                                             scope="DLL_Overrides")

            '''Create new entry in list_overrides'''
            self.list_overrides.add(BottlesDLLOverrideEntry(self.window,
                                                            self.configuration,
                                                            [dll_name, "n,b"]))
            '''Empty entry_name'''
            self.entry_name.set_text("")

    def save_override(self,widget=False):
        GLib.idle_add(self.idle_save_override)

    def idle_populate_overrides_list(self):
        for override in self.configuration.get("DLL_Overrides").items():
            self.list_overrides.add(BottlesDLLOverrideEntry(self.window,
                                                            self.configuration,
                                                            override))

    def populate_overrides_list(self):
        GLib.idle_add(self.idle_populate_overrides_list)

@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-launch-options.ui')
class BottlesLaunchOptions(Handy.Window):
    __gtype_name__ = 'BottlesLaunchOptions'

    '''Get widgets from template'''
    entry_arguments = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()

    def __init__(self, window, configuration, program_executable, arguments, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.configuration = configuration
        self.program_executable = program_executable
        self.arguments = arguments

        '''Populate widgets'''
        self.entry_arguments.set_text(self.arguments)

        '''Signal connections'''
        self.btn_cancel.connect('pressed', self.close_window)
        self.btn_save.connect('pressed', self.save_options)

    '''Destroy the window'''
    def close_window(self, widget):
        self.destroy()

    '''Save launch options'''
    def save_options(self, widget):
        self.arguments = self.entry_arguments.get_text()
        self.runner.update_configuration(configuration=self.configuration,
                                         key=self.program_executable,
                                         value=self.arguments,
                                         scope="Programs")
        self.close_window(widget)
        self.window.page_details.update_programs()

@Gtk.Template(resource_path='/com/usebottles/bottles/installer-entry.ui')
class BottlesInstallerEntry(Handy.ActionRow):
    __gtype_name__ = 'BottlesInstallerEntry'

    '''Get widgets from template'''
    btn_install = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
    img_installed = Gtk.Template.Child()

    def __init__(self, window, configuration, installer, plain=False, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.configuration = configuration
        self.installer = installer
        self.spinner = Gtk.Spinner()

        '''Populate widgets'''
        self.set_title(installer[0])
        self.set_subtitle(installer[1].get("Description"))

        '''Signal connections'''
        self.btn_install.connect('pressed', self.execute_installer)
        self.btn_manifest.connect('pressed', self.open_manifest)

    '''Open installer manifest'''
    def open_manifest(self, widget):
        dialog = BottlesDialog(
            parent=self.window,
            title=_("Manifest for {0}").format(self.installer[0]),
            message=False,
            log=self.runner.fetch_installer_manifest(self.installer[0],
                                                    self.installer[1]["Category"],
                                                    plain=True))
        dialog.run()
        dialog.destroy()

    '''Execute installer'''
    def execute_installer(self, widget):
        for w in widget.get_children(): w.destroy()

        widget.set_sensitive(False)
        widget.add(self.spinner)
        
        self.spinner.show()
        GLib.idle_add(self.spinner.start)

        InstallerManager(
            runner=self.runner,
            configuration=self.configuration,
            installer=self.installer,
            widget=self).install()
    
    '''Set installed status'''
    def set_installed(self):
        self.spinner.stop()
        self.btn_install.set_visible(False)
        self.img_installed.set_visible(True)

@Gtk.Template(resource_path='/com/usebottles/bottles/state-entry.ui')
class BottlesStateEntry(Handy.ActionRow):
    __gtype_name__ = 'BottlesStateEntry'

    '''Get widgets from template'''
    label_creation_date = Gtk.Template.Child()
    btn_restore = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()

    def __init__(self, window, configuration, state, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.state = state
        self.state_name = "State: {0}".format(state[0])
        self.configuration = configuration
        self.versioning_manager = self.runner.versioning_manager
        self.spinner = Gtk.Spinner()

        '''Format creation date'''
        creation_date = datetime.strptime(state[1].get("Creation_Date"), "%Y-%m-%d %H:%M:%S.%f")
        creation_date = creation_date.strftime("%b %d %Y %H:%M:%S")

        '''Populate widgets'''
        self.set_title(self.state_name)
        self.set_subtitle(self.state[1].get("Comment"))
        self.label_creation_date.set_text(creation_date)
        if state[0] == configuration.get("State"):
            self.get_style_context().add_class("current-state")

        '''Signal connections'''
        self.btn_restore.connect('pressed', self.set_state)
        self.btn_manifest.connect('pressed', self.open_index)

    '''Set bottle state'''
    def set_state(self, widget):
        for w in widget.get_children(): w.destroy()

        widget.set_sensitive(False)
        widget.add(self.spinner)
        
        self.spinner.show()
        GLib.idle_add(self.spinner.start)
        self.versioning_manager.set_bottle_state(self.configuration, self.state[0], self.set_completed)

    '''Open state index'''
    def open_index(self, widget):
        dialog = BottlesDialog(
            parent=self.window,
            title=_("Index for state {0}").format(self.state[0]),
            message=False,
            log=self.versioning_manager.get_bottle_state_edits(
                self.configuration,
                self.state[0],
                True))
        dialog.run()
        dialog.destroy()
    
    '''Set installed status'''
    def set_completed(self):
        self.spinner.stop()
        self.btn_restore.set_visible(False)

@Gtk.Template(resource_path='/com/usebottles/bottles/program-entry.ui')
class BottlesProgramEntry(Handy.ActionRow):
    __gtype_name__ = 'BottlesProgramEntry'

    '''Get widgets from template'''
    btn_run = Gtk.Template.Child()
    btn_winehq = Gtk.Template.Child()
    btn_protondb = Gtk.Template.Child()
    btn_issues = Gtk.Template.Child()
    btn_launch_options = Gtk.Template.Child()
    btn_uninstall = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()

    def __init__(self, window, configuration, program, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.configuration = configuration
        self.arguments = ""
        self.program_name = program[0]
        self.program_executable = program[1].split("\\")[-1]
        self.program_executable_path = program[1]
        self.program_folder = program[3]

        '''Populate widgets'''
        self.set_title(self.program_name)
        self.set_icon_name(program[2])

        '''Signal conenctions'''
        self.btn_run.connect('pressed', self.run_executable)
        self.btn_winehq.connect('pressed', self.open_winehq)
        self.btn_protondb.connect('pressed', self.open_protondb)
        self.btn_issues.connect('pressed', self.open_issues)
        self.btn_launch_options.connect('pressed', self.show_launch_options_view)
        self.btn_uninstall.connect('pressed', self.uninstall_program)
        self.btn_remove.connect('pressed', self.remove_program)
        self.btn_browse.connect('pressed', self.browse_program_folder)

        '''Populate entry_arguments by configuration'''
        if self.program_executable in self.configuration["Programs"]:
            self.arguments = self.configuration["Programs"][self.program_executable]

    '''Show dialog for launch options'''
    def show_launch_options_view(self, widget=False):
        new_window = BottlesLaunchOptions(self.window,
                                          self.configuration,
                                          self.program_executable,
                                          self.arguments)
        new_window.present()

    '''Run executable'''
    def run_executable(self, widget):
        if self.program_executable in self.configuration["Programs"]:
            arguments = self.configuration["Programs"][self.program_executable]
        else:
            arguments = False
        RunnerUtilities().run_executable(
            self.configuration,
            self.program_executable_path,
            arguments,
            cwd=self.program_folder)

    def uninstall_program(self, widget):
        self.runner.remove_program(self.configuration, self.program_name)

    def remove_program(self, widget):
        self.runner.update_configuration(
            configuration=self.configuration,
            key=self.program_name,
            value=False,
            remove=True,
            scope="External_Programs")
        self.destroy()

    def browse_program_folder(self, widget):
        RunnerUtilities().open_filemanager(
            configuration=self.configuration, 
            path_type="custom",
            custom_path=self.program_folder)

    '''Open URLs'''
    def open_winehq(self, widget):
        query = self.program_name.replace(" ", "+")
        webbrowser.open_new_tab("https://www.winehq.org/search?q=%s" % query)

    def open_protondb(self, widget):
        query = self.program_name
        webbrowser.open_new_tab("https://www.protondb.com/search?q=%s" % query)

    def open_issues(self, widget):
        query = self.program_name.replace(" ", "+")
        webbrowser.open_new_tab("https://github.com/bottlesdevs/Bottles/issues?q=is:issue%s" % query)

@Gtk.Template(resource_path='/com/usebottles/bottles/dependency-entry.ui')
class BottlesDependencyEntry(Handy.ActionRow):
    __gtype_name__ = 'BottlesDependencyEntry'

    '''Get widgets from template'''
    label_category = Gtk.Template.Child()
    btn_install = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
    btn_license = Gtk.Template.Child()
    btn_err = Gtk.Template.Child()

    def __init__(self, window, configuration, dependency, plain=False, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.configuration = configuration
        self.dependency = dependency
        self.spinner = Gtk.Spinner()

        '''If dependency is plain text (placeholder)'''
        if plain:
            self.set_title(dependency)
            self.set_subtitle("")
            self.btn_install.set_visible(False)
            self.btn_remove.set_visible(False)
            return None
        
        '''Populate widgets'''
        self.set_title(dependency[0])
        self.set_subtitle(dependency[1].get("Description"))
        self.label_category.set_text(dependency[1].get("Category"))

        '''Signal connections'''
        self.btn_install.connect('pressed', self.install_dependency)
        self.btn_remove.connect('pressed', self.remove_dependency)
        self.btn_manifest.connect('pressed', self.open_manifest)
        self.btn_license.connect('pressed', self.open_license)

        '''
        Set widgets status from configuration
        '''
        if dependency[0] in self.configuration.get("Installed_Dependencies"):
            self.btn_install.set_visible(False)
            self.btn_remove.set_visible(True)
        
        '''If dependency has no uninstaller'''
        if dependency[0] in self.configuration.get("Uninstallers").keys():
            if self.configuration["Uninstallers"][dependency[0]] == "NO_UNINSTALLER":
                self.btn_remove.set_sensitive(False)

    '''Open dependency manifest'''
    def open_manifest(self, widget):
        dialog = BottlesDialog(
            parent=self.window,
            title=_("Manifest for {0}").format(self.dependency[0]),
            message=False,
            log=self.runner.fetch_dependency_manifest(self.dependency[0],
                                                      self.dependency[1]["Category"],
                                                      plain=True))
        dialog.run()
        dialog.destroy()

    '''Open dependency license'''
    def open_license(self, widget):
        manifest = self.runner.fetch_dependency_manifest(
            self.dependency[0],
            self.dependency[1]["Category"])
        webbrowser.open(manifest["License_url"])

    '''Install dependency'''
    def install_dependency(self, widget):
        for w in widget.get_children(): w.destroy()

        widget.set_sensitive(False)
        widget.add(self.spinner)
        
        self.spinner.show()
        GLib.idle_add(self.spinner.start)

        self.runner.install_dependency(self.configuration,
                                       self.dependency,
                                       self)

    '''Remove dependency'''
    def remove_dependency(self, widget):
        GLib.idle_add(widget.set_sensitive, False)
        self.runner.remove_dependency(self.configuration,
                                      self.dependency,
                                      self)
    
    '''Set error status'''
    def set_err(self):
        self.spinner.stop()
        self.btn_install.set_visible(False)
        self.btn_remove.set_visible(False)
        self.btn_err.set_visible(True)
    
    '''Set installed status'''
    def set_installed(self, has_installer=True):
        self.spinner.stop()
        self.btn_install.set_visible(False)
        if has_installer:
            self.btn_remove.set_visible(True)
            self.btn_remove.set_sensitive(True)

@Gtk.Template(resource_path='/com/usebottles/bottles/details.ui')
class BottlesDetails(Handy.Leaflet):
    __gtype_name__ = 'BottlesDetails'

    '''Get widgets from template'''
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
    btn_add_state = Gtk.Template.Child()
    btn_delete = Gtk.Template.Child()
    btn_manage_runners = Gtk.Template.Child()
    btn_manage_dxvk = Gtk.Template.Child()
    btn_manage_vkd3d = Gtk.Template.Child()
    btn_help_versioning = Gtk.Template.Child()
    btn_help_debug = Gtk.Template.Child()
    btn_request_dependency = Gtk.Template.Child()
    switch_dxvk = Gtk.Template.Child()
    switch_dxvk_hud = Gtk.Template.Child()
    switch_vkd3d = Gtk.Template.Child()
    switch_gamemode = Gtk.Template.Child()
    switch_aco = Gtk.Template.Child()
    switch_discrete = Gtk.Template.Child()
    switch_virtual_desktop = Gtk.Template.Child()
    switch_pulseaudio_latency = Gtk.Template.Child()
    switch_fixme = Gtk.Template.Child()
    toggle_sync = Gtk.Template.Child()
    toggle_esync = Gtk.Template.Child()
    toggle_fsync = Gtk.Template.Child()
    combo_virtual_resolutions = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    combo_dxvk = Gtk.Template.Child()
    combo_vkd3d = Gtk.Template.Child()
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

    def __init__(self, window, configuration=dict, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.versioning_manager = window.runner.versioning_manager
        self.configuration = configuration

        '''Signal connections'''
        self.entry_name.connect('key-release-event', self.check_entry_name)

        self.btn_winecfg.connect('pressed', self.run_winecfg)
        self.btn_debug.connect('pressed', self.run_debug)
        self.btn_execute.connect('pressed', self.run_executable)
        self.btn_run_args.connect('pressed', self.run_executable_with_args)
        self.btn_browse.connect('pressed', self.run_browse)
        self.btn_cmd.connect('pressed', self.run_cmd)
        self.btn_taskmanager.connect('pressed', self.run_taskmanager)
        self.btn_controlpanel.connect('pressed', self.run_controlpanel)
        self.btn_uninstaller.connect('pressed', self.run_uninstaller)
        self.btn_regedit.connect('pressed', self.run_regedit)
        self.btn_delete.connect('pressed', self.confirm_delete)
        self.btn_overrides.connect('pressed', self.show_dll_overrides_view)
        self.btn_manage_runners.connect('pressed', self.window.show_preferences_view)
        self.btn_manage_dxvk.connect('pressed', self.window.show_preferences_view)
        self.btn_manage_vkd3d.connect('pressed', self.window.show_preferences_view)

        self.btn_winecfg.connect('activate', self.run_winecfg)
        self.btn_debug.connect('activate', self.run_debug)
        self.btn_execute.connect('activate', self.run_executable)
        self.btn_run_args.connect('activate', self.run_executable_with_args)
        self.btn_browse.connect('activate', self.run_browse)
        self.btn_cmd.connect('activate', self.run_cmd)
        self.btn_taskmanager.connect('activate', self.run_taskmanager)
        self.btn_controlpanel.connect('activate', self.run_controlpanel)
        self.btn_uninstaller.connect('activate', self.run_uninstaller)
        self.btn_regedit.connect('activate', self.run_regedit)
        self.btn_overrides.connect('activate', self.show_dll_overrides_view)
        self.btn_environment_variables.connect('activate', self.show_environment_variables)

        self.btn_shutdown.connect('pressed', self.run_shutdown)
        self.btn_reboot.connect('pressed', self.run_reboot)
        self.btn_killall.connect('pressed', self.run_killall)
        self.btn_programs_updates.connect('pressed', self.update_programs)
        self.btn_programs_add.connect('pressed', self.add_program)
        self.btn_environment_variables.connect('pressed', self.show_environment_variables)
        self.btn_backup_config.connect('pressed', self.backup_config)
        self.btn_backup_full.connect('pressed', self.backup_full)
        self.btn_add_state.connect('pressed', self.add_state)
        self.btn_help_versioning.connect('pressed', self.open_doc_url, "bottles/versioning")
        self.btn_help_debug.connect('pressed', self.open_doc_url, "utilities/logs-and-debugger#wine-debugger")
        self.btn_request_dependency.connect('pressed', self.open_doc_url, "contribute/missing-dependencies")

        self.btn_rename.connect('toggled', self.toggle_rename)
        self.toggle_sync.connect('toggled', self.set_wine_sync)
        self.toggle_esync.connect('toggled', self.set_esync)
        self.toggle_fsync.connect('toggled', self.set_fsync)

        self.switch_dxvk.connect('state-set', self.toggle_dxvk)
        self.switch_dxvk_hud.connect('state-set', self.toggle_dxvk_hud)
        self.switch_vkd3d.connect('state-set', self.toggle_vkd3d)
        self.switch_gamemode.connect('state-set', self.toggle_gamemode)
        self.switch_aco.connect('state-set', self.toggle_aco)
        self.switch_discrete.connect('state-set', self.toggle_discrete_graphics)
        self.switch_virtual_desktop.connect('state-set', self.toggle_virtual_desktop)
        self.switch_pulseaudio_latency.connect('state-set', self.toggle_pulseaudio_latency)
        self.switch_fixme.connect('state-set', self.toggle_fixme)

        self.combo_virtual_resolutions.connect('changed', self.set_virtual_desktop_resolution)
        self.combo_runner.connect('changed', self.set_runner)
        self.combo_dxvk.connect('changed', self.set_dxvk)
        self.combo_vkd3d.connect('changed', self.set_vkd3d)

        self.entry_search_deps.connect('key-release-event', self.search_dependencies)
        self.entry_search_deps.connect('changed', self.search_dependencies)
        self.entry_state_comment.connect('key-release-event', self.check_entry_state_comment)

        self.list_pages.connect('row-selected', self.change_page)

        # Toggle gamemode switcher sensitivity
        self.switch_gamemode.set_sensitive(gamemode_available)
        if not gamemode_available:
            self.switch_gamemode.set_tooltip_text(_("Gamemode is either not available on your system or not running."))

        self.build_pages()

        if "TESTING_REPOS" in os.environ and os.environ["TESTING_REPOS"] == "1":
            self.infobar_testing.set_visible(True)


    def build_pages(self):
        pages = {
            "bottle": _("Details & Utilities"),
            "preferences": _("Preferences"),
            "dependencies": _("Dependencies"),
            "programs": _("Programs")
        }
        if self.window.settings.get_boolean("experiments-versioning"):
            pages["versioning"] = _("Versioning")
        if self.window.settings.get_boolean("experiments-installers"):
            pages["installers"] = _("Installers")

        for w in self.list_pages.get_children():
            w.destroy()

        for p in pages:
            self.list_pages.add(BottlesDetailsPageRow(p, pages[p]))

    def change_page(self, widget, row):
        try:
            self.stack_bottle.set_visible_child_name(row.page_name)
        except AttributeError:
            pass

    def search_dependencies(self, widget, event=None, data=None):
        terms = widget.get_text()
        self.list_dependencies.set_filter_func(
            self.filter_dependencies,
            terms)

    def filter_dependencies(self, row, terms=None):
        if terms.lower() in row.get_title().lower():
            return True
        return False

    def update_combo_components(self):
        self.combo_runner.handler_block_by_func(self.set_runner)
        self.combo_dxvk.handler_block_by_func(self.set_dxvk)
        self.combo_vkd3d.handler_block_by_func(self.set_vkd3d)

        '''Populate combo_runner, combo_dxvk, combo_vkd3d'''
        self.combo_runner.remove_all()
        self.combo_dxvk.remove_all()
        self.combo_vkd3d.remove_all()

        for runner in self.runner.runners_available:
            self.combo_runner.append(runner, runner)

        for dxvk in self.runner.dxvk_available:
            self.combo_dxvk.append(dxvk, dxvk)

        for vkd3d in self.runner.vkd3d_available:
            self.combo_vkd3d.append(vkd3d, vkd3d)

        self.combo_runner.handler_unblock_by_func(self.set_runner)
        self.combo_dxvk.handler_unblock_by_func(self.set_dxvk)
        self.combo_vkd3d.handler_unblock_by_func(self.set_vkd3d)

    '''Set bottle configuration'''
    def set_configuration(self, configuration):
        self.configuration = configuration

        '''Format update date'''
        update_date = datetime.strptime(configuration.get("Update_Date"), "%Y-%m-%d %H:%M:%S.%f")
        update_date = update_date.strftime("%b %d %Y %H:%M:%S")

        '''Format arch'''
        arch = "64-bit"
        if self.configuration.get("Arch") == "win32":
            arch = "32-bit"
        
        '''Lock signals preventing triggering'''
        self.switch_dxvk.handler_block_by_func(self.toggle_dxvk)
        self.switch_vkd3d.handler_block_by_func(self.toggle_vkd3d)
        self.switch_virtual_desktop.handler_block_by_func(self.toggle_virtual_desktop)
        self.combo_virtual_resolutions.handler_block_by_func(self.set_virtual_desktop_resolution)
        self.combo_runner.handler_block_by_func(self.set_runner)
        self.combo_dxvk.handler_block_by_func(self.set_dxvk)
        self.combo_vkd3d.handler_block_by_func(self.set_vkd3d)

        '''Populate widgets from configuration'''
        parameters = self.configuration.get("Parameters")
        self.entry_name.set_text(self.configuration.get("Name"))
        self.entry_name.set_tooltip_text(_("Updated: %s" % update_date))
        self.label_runner.set_text(self.configuration.get("Runner"))
        self.label_arch.set_text(arch)
        self.label_environment.set_text(self.configuration.get("Environment"))
        self.label_environment.get_style_context().add_class(
            "tag-%s" % self.configuration.get("Environment").lower())
        self.label_state.set_text(str(self.configuration.get("State")))
        self.switch_dxvk.set_active(parameters["dxvk"])
        self.switch_dxvk_hud.set_active(parameters["dxvk_hud"])
        self.switch_vkd3d.set_active(parameters["vkd3d"])
        self.switch_gamemode.set_active(parameters["gamemode"])
        self.switch_aco.set_active(parameters["aco_compiler"])
        if parameters["sync"] == "wine": self.toggle_sync.set_active(True)
        if parameters["sync"] == "esync": self.toggle_esync.set_active(True)
        if parameters["sync"] == "fsync": self.toggle_fsync.set_active(True)
        self.switch_discrete.set_active(parameters["discrete_gpu"])
        self.switch_virtual_desktop.set_active(parameters["virtual_desktop"])
        self.switch_pulseaudio_latency.set_active(parameters["pulseaudio_latency"])
        self.combo_virtual_resolutions.set_active_id(parameters["virtual_desktop_res"])
        self.combo_runner.set_active_id(self.configuration.get("Runner"))
        self.combo_dxvk.set_active_id(self.configuration.get("DXVK"))
        self.combo_vkd3d.set_active_id(self.configuration.get("VKD3D"))
        self.grid_versioning.set_visible(self.configuration.get("Versioning"))

        '''Unlock signals'''
        self.switch_dxvk.handler_unblock_by_func(self.toggle_dxvk)
        self.switch_vkd3d.handler_unblock_by_func(self.toggle_vkd3d)
        self.switch_virtual_desktop.handler_unblock_by_func(self.toggle_virtual_desktop)
        self.combo_virtual_resolutions.handler_unblock_by_func(self.set_virtual_desktop_resolution)
        self.combo_runner.handler_unblock_by_func(self.set_runner)
        self.combo_dxvk.handler_unblock_by_func(self.set_dxvk)
        self.combo_vkd3d.handler_unblock_by_func(self.set_vkd3d)

        self.update_programs()
        self.update_dependencies()
        self.update_installers()
        self.update_states()



    '''Show dialog for launch options'''
    def show_environment_variables(self, widget=False):
        new_window = BottlesEnvironmentVariables(self.window,
                                                 self.configuration)
        new_window.present()

    '''Validate entry_name input'''
    def check_entry_name(self, widget, event_key):
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:.;,]')
        name = widget.get_text()

        if(regex.search(name) is None) and name != "":
            self.btn_rename.set_sensitive(True)
            widget.set_icon_from_icon_name(1, "")
        else:
            self.btn_rename.set_sensitive(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")

    '''Toggle entry_name editable'''
    def toggle_rename(self, widget):
        status = widget.get_active()
        self.entry_name.set_editable(status)

        if status:
            self.entry_name.grab_focus()
        else:
            self.runner.update_configuration(configuration=self.configuration,
                                             key="Name",
                                             value=self.entry_name.get_text())

    '''Set active page'''
    def set_page(self, page):
        self.notebook_details.set_current_page(page)

    '''Show dependencies tab'''
    def show_dependencies(self, widget):
        self.set_page(2)

    '''Save environment variables'''
    def save_environment_variables(self, widget):
        environment_variables = self.entry_environment_variables.get_text()
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="environment_variables",
            value=environment_variables,
            scope="Parameters")
        self.configuration = new_configuration

    '''Add custome executable to the Programs list'''
    def add_program(self, widget=False):
        file_dialog = Gtk.FileChooserNative.new(
            _("Choose an executable path"),
            self.window,
            Gtk.FileChooserAction.OPEN,
            _("Add"),
            _("Cancel")
        )
        file_dialog.set_current_folder(
            RunnerUtilities().get_bottle_path(self.configuration))
        response = file_dialog.run()

        if response == -3:
            self.runner.update_configuration(
                configuration=self.configuration,
                key=file_dialog.get_filename().split("/")[-1][:-4],
                value=file_dialog.get_filename(),
                scope="External_Programs")
            self.update_programs()

        file_dialog.destroy()

    '''Populate list_programs'''
    def update_programs(self, widget=False):
        for w in self.list_programs: w.destroy()
        for w in self.group_programs: w.destroy()

        programs = self.runner.get_programs(self.configuration)

        if len(programs) == 0:
            self.group_programs.set_visible(False)
            return
            
        self.group_programs.set_visible(True)

        i = 0
        for program in programs:
            self.list_programs.add(BottlesProgramEntry(
                self.window, self.configuration, program))

            '''Append first 5 entries to group_programs'''
            if i < 5:
                self.group_programs.add(BottlesProgramEntry(
                    self.window, self.configuration, program))
            i =+ 1

    '''Populate list_dependencies'''
    def update_dependencies(self, widget=False):
        for w in self.list_dependencies: w.destroy()

        supported_dependencies = self.runner.supported_dependencies.items()
        if len(supported_dependencies) > 0:
            for dependency in supported_dependencies:
                self.list_dependencies.add(
                    BottlesDependencyEntry(self.window,
                                           self.configuration,
                                           dependency))
            return

        if len(self.configuration.get("Installed_Dependencies")) > 0:
            for dependency in self.configuration.get("Installed_Dependencies"):
                self.list_dependencies.add(
                    BottlesDependencyEntry(self.window,
                                           self.configuration,
                                           dependency,
                                           plain=True))
            return

    '''Populate list_installers'''
    def update_installers(self, widget=False):
        for w in self.list_installers: w.destroy()

        supported_installers = self.runner.supported_installers.items()

        if len(supported_installers) > 0:
            for installer in supported_installers:
                self.list_installers.add(
                    BottlesInstallerEntry(self.window,
                                          self.configuration,
                                          installer))
            return

    '''Populate list_states'''
    def idle_update_states(self, widget=False):
        if self.configuration.get("Versioning"):
            for w in self.list_states: w.destroy()

            states = self.versioning_manager.list_bottle_states(self.configuration).items()
            if len(states) > 0:
                for state in states:
                    self.list_states.add(
                        BottlesStateEntry(self.window,
                                          self.configuration,
                                          state))

    def update_states(self, widget=False):
        GLib.idle_add(self.idle_update_states, widget=False)

    '''Toggle DXVK'''
    def toggle_dxvk(self, widget=False, state=False):
        if state:
            self.runner.install_dxvk(self.configuration)
        else:
            self.runner.remove_dxvk(self.configuration)

        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="dxvk",
            value=state,
            scope="Parameters")
        self.configuration = new_configuration

    '''Toggle DXVK HUD'''
    def toggle_dxvk_hud(self, widget, state):
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="dxvk_hud",
            value=state,
            scope="Parameters")
        self.configuration = new_configuration

    '''Toggle VKD3D'''
    def toggle_vkd3d(self, widget=False, state=False):
        if state:
            self.runner.install_vkd3d(self.configuration)
        else:
            self.runner.remove_vkd3d(self.configuration)

        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="vkd3d",
            value=state,
            scope="Parameters")
        self.configuration = new_configuration

    '''Toggle Gamemode'''
    def toggle_gamemode(self, widget=False, state=False):
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="gamemode",
            value=state,
            scope="Parameters")
        self.configuration = new_configuration

    '''Set Wine synchronization type'''
    def set_sync_type(self, sync):
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="sync",
            value=sync,
            scope="Parameters")
        self.configuration = new_configuration

        if sync in ["esync", "fsync"]:
            self.toggle_sync.handler_block_by_func(self.set_wine_sync)
            self.toggle_sync.set_active(False)
            self.toggle_sync.handler_unblock_by_func(self.set_wine_sync)
        if sync in ["esync", "wine"]:
            self.toggle_fsync.handler_block_by_func(self.set_fsync)
            self.toggle_fsync.set_active(False)
            self.toggle_fsync.handler_unblock_by_func(self.set_fsync)
        if sync in ["fsync", "wine"]:
            self.toggle_esync.handler_block_by_func(self.set_esync)
            self.toggle_esync.set_active(False)
            self.toggle_esync.handler_unblock_by_func(self.set_esync)

    def set_wine_sync(self, widget):
        self.set_sync_type("wine")

    def set_esync(self, widget):
        self.set_sync_type("esync")

    def set_fsync(self, widget):
        self.set_sync_type("fsync")

    '''Toggle ACO compiler'''
    def toggle_aco(self, widget, state):
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="aco_compiler",
            value=state,
            scope="Parameters")
        self.configuration = new_configuration

    '''Toggle discrete graphics usage'''
    def toggle_discrete_graphics(self, widget, state):
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="discrete_gpu",
            value=state,
            scope="Parameters")
        self.configuration = new_configuration

    '''Toggle virtual desktop'''
    def toggle_virtual_desktop(self, widget, state):
        resolution = self.combo_virtual_resolutions.get_active_id()
        self.runner.toggle_virtual_desktop(self.configuration,
                                           state,
                                           resolution)
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="virtual_desktop",
            value=state,
            scope="Parameters")
        self.configuration = new_configuration

    '''Set virtual desktop resolution'''
    def set_virtual_desktop_resolution(self, widget):
        resolution = widget.get_active_id()
        if self.switch_virtual_desktop.get_active():
            self.runner.toggle_virtual_desktop(self.configuration,
                                               True,
                                               resolution)
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="virtual_desktop_res",
            value=resolution,
            scope="Parameters")
        self.configuration = new_configuration

    '''Set (change) runner'''
    def set_runner(self, widget):
        runner = widget.get_active_id()
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="Runner",
            value=runner)
        self.configuration = new_configuration

    '''Set (change) dxvk'''
    def set_dxvk(self, widget):
        # remove old dxvk
        self.toggle_dxvk(state=False)

        dxvk = widget.get_active_id()
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="DXVK",
            value=dxvk)
        self.configuration = new_configuration

        # install new dxvk
        self.toggle_dxvk(state=True)

    '''Set (change) vkd3d'''
    def set_vkd3d(self, widget):
        # remove old vkd3d
        self.toggle_vkd3d(state=False)

        vkd3d = widget.get_active_id()
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="VKD3D",
            value=vkd3d)
        self.configuration = new_configuration

        # install new vkd3d
        self.toggle_vkd3d(state=True)

    '''Toggle pulseaudio latency'''
    def toggle_pulseaudio_latency(self, widget, state):
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="pulseaudio_latency",
            value=state,
            scope="Parameters")
        self.configuration = new_configuration

    '''Toggle fixme wine logs'''
    def toggle_fixme(self, widget, state):
        new_configuration = self.runner.update_configuration(
            configuration=self.configuration,
            key="fixme_logs",
            value=state,
            scope="Parameters")
        self.configuration = new_configuration

    def run_executable_with_args(self, widget):
        new_window = BottlesRunArgs(self)
        new_window.present()

    '''Display file dialog for executable selection'''
    def run_executable(self, widget, args=False):
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
                RunnerUtilities().run_executable(
                    configuration=self.configuration,
                    file_path=file_dialog.get_filename(),
                    arguments=args)
            else:
                RunnerUtilities().run_executable(
                    configuration=self.configuration,
                    file_path=file_dialog.get_filename())

        file_dialog.destroy()

    '''Run wine executables and utilities'''
    def run_winecfg(self, widget):
        RunnerUtilities().run_winecfg(self.configuration)

    def run_debug(self, widget):
        RunnerUtilities().run_debug(self.configuration)

    def run_browse(self, widget):
        RunnerUtilities().open_filemanager(self.configuration)

    def run_cmd(self, widget):
        RunnerUtilities().run_cmd(self.configuration)

    def run_taskmanager(self, widget):
        RunnerUtilities().run_taskmanager(self.configuration)

    def run_controlpanel(self, widget):
        RunnerUtilities().run_controlpanel(self.configuration)

    def run_uninstaller(self, widget):
        RunnerUtilities().run_uninstaller(self.configuration)

    def run_regedit(self, widget):
        RunnerUtilities().run_regedit(self.configuration)

    def run_shutdown(self, widget):
        RunnerUtilities().send_status(self.configuration, "shutdown")

    def run_reboot(self, widget):
        RunnerUtilities().send_status(self.configuration, "reboot")

    def run_killall(self, widget):
        RunnerUtilities().send_status(self.configuration, "kill")

    '''Validate entry_state input'''
    def check_entry_state_comment(self, widget, event_key):
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:.;,"]')
        comment = widget.get_text()

        if(regex.search(comment) is None):
            self.btn_add_state.set_sensitive(True)
            widget.set_icon_from_icon_name(1, "")
        else:
            self.btn_add_state.set_sensitive(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")

    '''Add new state'''
    def add_state(self, widget):
        comment = self.entry_state_comment.get_text()
        if comment != "":
            self.versioning_manager.create_bottle_state(self.configuration, comment, after=self.update_states)
            self.entry_state_comment.set_text("")
            self.pop_state.popdown()

    '''Display file dialog for backup configuration'''
    def backup_config(self, widget):
        file_dialog = Gtk.FileChooserDialog(
            _("Select the location where to save the backup configuration"),
            self.window,
            Gtk.FileChooserAction.SAVE,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK))
        file_dialog.set_current_name("backup_%s.yml" % self.configuration.get("Path"))

        response = file_dialog.run()

        if response == Gtk.ResponseType.OK:
            RunnerBackup().backup_bottle(
                self.window,
                self.configuration,
                "configuration",
                file_dialog.get_filename()
            )

        file_dialog.destroy()

    '''Display file dialog for backup archive'''
    def backup_full(self, widget):
        file_dialog = Gtk.FileChooserDialog(
            _("Select the location where to save the backup archive"),
            self.window,
            Gtk.FileChooserAction.SAVE,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK))
        file_dialog.set_current_name(
            "backup_%s.tar.gz" % self.configuration.get("Path"))

        response = file_dialog.run()

        if response == Gtk.ResponseType.OK:
            RunnerBackup().backup_bottle(
                self.window,
                self.configuration,
                "full",
                file_dialog.get_filename()
            )

        file_dialog.destroy()

    '''Show dialog to confirm bottle deletion'''
    def confirm_delete(self, widget):
        dialog_delete = BottlesMessageDialog(parent=self.window,
                                      title=_("Confirm deletion"),
                                      message=_("Are you sure you want to delete this Bottle and all files?"))
        response = dialog_delete.run()

        if response == Gtk.ResponseType.OK:
            self.runner.delete_bottle(self.configuration)
            self.window.go_back()

        dialog_delete.destroy()

    '''Show dialog for DLL overrides'''
    def show_dll_overrides_view(self, widget=False):
        new_window = BottlesDLLOverrides(self.window,
                                         self.configuration)
        new_window.present()

    '''Open URLs'''
    @staticmethod
    def open_report_url(widget):
        webbrowser.open_new_tab("https://github.com/bottlesdevs/dependencies/issues/new/choose")

    @staticmethod
    def open_doc_url(widget, page):
        webbrowser.open_new_tab(f"https://docs.usebottles.com/{page}")

    '''Methods for pop_more buttons'''
    def show_versioning_view(self, widget=False):
        self.stack_bottle.set_visible_child_name("versioning")

    def show_installers_view(self, widget=False):
        self.stack_bottle.set_visible_child_name("installers")
