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

from ..dialogs.generic import Dialog, MessageDialog
from ..dialogs.duplicate import DuplicateDialog
from ..dialogs.runargs import RunArgsDialog
from ..dialogs.envvars import EnvVarsDialog
from ..dialogs.dlloverrides import DLLOverridesDialog
from ..dialogs.launchoptions import LaunchOptionsDialog
from ..backend.runner import Runner, gamemode_available
from ..backend.backup import RunnerBackup

class PageRow(Gtk.ListBoxRow):

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

@Gtk.Template(resource_path='/com/usebottles/bottles/installer-entry.ui')
class InstallerEntry(Handy.ActionRow):
    __gtype_name__ = 'InstallerEntry'

    # region Widgets
    btn_install = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
    img_installed = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, installer, plain=False, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
        self.installer = installer
        self.spinner = Gtk.Spinner()

        '''Populate widgets'''
        self.set_title(installer[0])
        self.set_subtitle(installer[1].get("Description"))

        # connect signals
        self.btn_install.connect('pressed', self.execute_installer)
        self.btn_manifest.connect('pressed', self.open_manifest)

    '''Open installer manifest'''
    def open_manifest(self, widget):
        dialog = Dialog(
            parent=self.window,
            title=_("Manifest for {0}").format(self.installer[0]),
            message=False,
            log=self.manager.installer_manager.get_installer(
                installer_name=self.installer[0],
                installer_category=self.installer[1]["Category"],
                plain=True
            )
        )
        dialog.run()
        dialog.destroy()

    '''Execute installer'''
    def execute_installer(self, widget):
        self.get_parent().set_sensitive(False)
        for w in widget.get_children(): w.destroy()

        widget.set_sensitive(False)
        widget.add(self.spinner)
        
        self.spinner.show()
        GLib.idle_add(self.spinner.start)

        self.manager.installer_manager.install(
            config=self.config,
            installer=self.installer,
            widget=self
        )
    
    '''Set installed status'''
    def set_installed(self):
        self.spinner.stop()
        self.btn_install.set_visible(False)
        self.img_installed.set_visible(True)
        self.get_parent().set_sensitive(True)

@Gtk.Template(resource_path='/com/usebottles/bottles/state-entry.ui')
class StateEntry(Handy.ActionRow):
    __gtype_name__ = 'StateEntry'

    # region Widgets
    label_creation_date = Gtk.Template.Child()
    btn_restore = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, state, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.state = state
        self.state_name = "State: {0}".format(state[0])
        self.config = config
        self.versioning_manager = self.manager.versioning_manager
        self.spinner = Gtk.Spinner()

        '''Format creation date'''
        creation_date = datetime.strptime(state[1].get("Creation_Date"), "%Y-%m-%d %H:%M:%S.%f")
        creation_date = creation_date.strftime("%b %d %Y %H:%M:%S")

        '''Populate widgets'''
        self.set_title(self.state_name)
        self.set_subtitle(self.state[1].get("Comment"))
        self.label_creation_date.set_text(creation_date)
        if state[0] == config.get("State"):
            self.get_style_context().add_class("current-state")

        # connect signals
        self.btn_restore.connect('pressed', self.set_state)
        self.btn_manifest.connect('pressed', self.open_index)

    '''Set bottle state'''
    def set_state(self, widget):
        for w in widget.get_children(): w.destroy()
        self.get_parent().set_sensitive(False)

        widget.set_sensitive(False)
        widget.add(self.spinner)
        
        self.spinner.show()
        GLib.idle_add(self.spinner.start)
        self.versioning_manager.set_bottle_state(self.config, self.state[0], self.set_completed)

    '''Open state index'''
    def open_index(self, widget):
        dialog = Dialog(
            parent=self.window,
            title=_("Index for state {0}").format(self.state[0]),
            message=False,
            log=self.versioning_manager.get_bottle_state_edits(
                self.config,
                self.state[0],
                True))
        dialog.run()
        dialog.destroy()
    
    '''Set installed status'''
    def set_completed(self):
        self.spinner.stop()
        self.btn_restore.set_visible(False)
        self.get_parent().set_sensitive(True)

@Gtk.Template(resource_path='/com/usebottles/bottles/program-entry.ui')
class ProgramEntry(Handy.ActionRow):
    __gtype_name__ = 'ProgramEntry'

    # region Widgets
    btn_run = Gtk.Template.Child()
    btn_winehq = Gtk.Template.Child()
    btn_protondb = Gtk.Template.Child()
    btn_issues = Gtk.Template.Child()
    btn_launch_options = Gtk.Template.Child()
    btn_uninstall = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, program, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
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

        '''Populate entry_arguments by config'''
        if self.program_executable in self.config["Programs"]:
            self.arguments = self.config["Programs"][self.program_executable]

    '''Show dialog for launch options'''
    def show_launch_options_view(self, widget=False):
        new_window = LaunchOptionsDialog(self.window,
                                          self.config,
                                          self.program_executable,
                                          self.arguments)
        new_window.present()

    '''Run executable'''
    def run_executable(self, widget):
        if self.program_executable in self.config["Programs"]:
            arguments = self.config["Programs"][self.program_executable]
        else:
            arguments = False
        Runner().run_executable(
            self.config,
            self.program_executable_path,
            arguments,
            cwd=self.program_folder)

    def uninstall_program(self, widget):
        self.manager.remove_program(self.config, self.program_name)

    def remove_program(self, widget):
        self.manager.update_config(
            config=self.config,
            key=self.program_name,
            value=False,
            remove=True,
            scope="External_Programs")
        self.destroy()

    def browse_program_folder(self, widget):
        Runner().open_filemanager(
            config=self.config, 
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
class DependencyEntry(Handy.ActionRow):
    __gtype_name__ = 'DependencyEntry'

    # region Widgets
    label_category = Gtk.Template.Child()
    btn_install = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_manifest = Gtk.Template.Child()
    btn_license = Gtk.Template.Child()
    btn_err = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, dependency, plain=False, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config
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

        # connect signals
        self.btn_install.connect('pressed', self.install_dependency)
        self.btn_remove.connect('pressed', self.remove_dependency)
        self.btn_manifest.connect('pressed', self.open_manifest)
        self.btn_license.connect('pressed', self.open_license)

        '''
        Set widgets status from config
        '''
        if dependency[0] in self.config.get("Installed_Dependencies"):
            self.btn_install.set_visible(False)
            self.btn_remove.set_visible(True)
        
        '''If dependency has no uninstaller'''
        if dependency[0] in self.config.get("Uninstallers").keys():
            if self.config["Uninstallers"][dependency[0]] == "NO_UNINSTALLER":
                self.btn_remove.set_sensitive(False)

    '''Open dependency manifest'''
    def open_manifest(self, widget):
        dialog = Dialog(
            parent=self.window,
            title=_("Manifest for {0}").format(self.dependency[0]),
            message=False,
            log=self.manager.dependency_manager.get_dependency(
                dependency_name=self.dependency[0],
                dependency_category=self.dependency[1]["Category"],
                plain=True
            )
        )
        dialog.run()
        dialog.destroy()

    '''Open dependency license'''
    def open_license(self, widget):
        manifest = self.manager.dependency_manager.get_dependency(
            dependency_name=self.dependency[0],
            dependency_category=self.dependency[1]["Category"]
        )
        webbrowser.open(manifest["License_url"])

    '''Install dependency'''
    def install_dependency(self, widget):
        self.get_parent().set_sensitive(False)
        for w in widget.get_children(): w.destroy()

        widget.set_sensitive(False)
        widget.add(self.spinner)
        
        self.spinner.show()
        GLib.idle_add(self.spinner.start)

        self.manager.dependency_manager.install(
            config=self.config,
            dependency=self.dependency,
            widget=self
        )

    '''Remove dependency'''
    def remove_dependency(self, widget):
        GLib.idle_add(widget.set_sensitive, False)
        self.manager.remove_dependency(self.config,
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

        self.get_parent().set_sensitive(True)

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
    btn_expose_dirs = Gtk.Template.Child()
    btn_manage_runners = Gtk.Template.Child()
    btn_manage_dxvk = Gtk.Template.Child()
    btn_manage_vkd3d = Gtk.Template.Child()
    btn_help_versioning = Gtk.Template.Child()
    btn_help_debug = Gtk.Template.Child()
    btn_request_dependency = Gtk.Template.Child()
    btn_cwd = Gtk.Template.Child()
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
    row_cwd = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config=dict, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.versioning_manager = window.manager.versioning_manager
        self.config = config

        '''If Flatpak, show the btn_expose_dirs widget to reach
        the documentation on how to expose directories'''
        if "FLATPAK_ID" in os.environ:
            self.btn_expose_dirs.set_visible(True)

        # connect signals
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
        self.btn_manage_runners.connect('pressed', self.window.show_prefs_view)
        self.btn_manage_dxvk.connect('pressed', self.window.show_prefs_view)
        self.btn_manage_vkd3d.connect('pressed', self.window.show_prefs_view)
        self.btn_cwd.connect('pressed', self.choose_cwd)

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
        self.btn_cwd.connect('activate', self.choose_cwd)

        self.btn_shutdown.connect('pressed', self.run_shutdown)
        self.btn_reboot.connect('pressed', self.run_reboot)
        self.btn_killall.connect('pressed', self.run_killall)
        self.btn_programs_updates.connect('pressed', self.update_programs)
        self.btn_programs_add.connect('pressed', self.add_program)
        self.btn_environment_variables.connect('pressed', self.show_environment_variables)
        self.btn_backup_config.connect('pressed', self.backup_config)
        self.btn_backup_full.connect('pressed', self.backup_full)
        self.btn_duplicate.connect('pressed', self.duplicate)
        self.btn_add_state.connect('pressed', self.add_state)
        self.btn_help_versioning.connect('pressed', self.open_doc_url, "bottles/versioning")
        self.btn_help_debug.connect('pressed', self.open_doc_url, "utilities/logs-and-debugger#wine-debugger")
        self.btn_request_dependency.connect('pressed', self.open_doc_url, "contribute/missing-dependencies")
        self.btn_expose_dirs.connect('pressed', self.open_doc_url, "flatpak/expose-directories")

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
            self.list_pages.add(PageRow(p, pages[p]))

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

    def choose_cwd(self, widget):
        file_dialog = Gtk.FileChooserNative.new(
            _("Choose working directory for executables"),
            self.window,
            Gtk.FileChooserAction.SELECT_FOLDER,
            _("Done"),
            _("Cancel")
        )
        file_dialog.set_current_folder(
            Runner().get_bottle_path(self.config))
            
        response = file_dialog.run()

        if response == -3:
            self.manager.update_config(
                config=self.config,
                key="WorkingDir",
                value=file_dialog.get_filename())

        file_dialog.destroy()

    def update_combo_components(self):
        self.combo_runner.handler_block_by_func(self.set_runner)
        self.combo_dxvk.handler_block_by_func(self.set_dxvk)
        self.combo_vkd3d.handler_block_by_func(self.set_vkd3d)

        '''Populate combo_runner, combo_dxvk, combo_vkd3d'''
        self.combo_runner.remove_all()
        self.combo_dxvk.remove_all()
        self.combo_vkd3d.remove_all()

        for runner in self.manager.runners_available:
            self.combo_runner.append(runner, runner)

        for dxvk in self.manager.dxvk_available:
            self.combo_dxvk.append(dxvk, dxvk)

        for vkd3d in self.manager.vkd3d_available:
            self.combo_vkd3d.append(vkd3d, vkd3d)

        self.combo_runner.handler_unblock_by_func(self.set_runner)
        self.combo_dxvk.handler_unblock_by_func(self.set_dxvk)
        self.combo_vkd3d.handler_unblock_by_func(self.set_vkd3d)

    '''Set bottle config'''
    def set_config(self, config):
        self.config = config

        '''Format update date'''
        update_date = datetime.strptime(config.get("Update_Date"), "%Y-%m-%d %H:%M:%S.%f")
        update_date = update_date.strftime("%b %d %Y %H:%M:%S")

        '''Format arch'''
        arch = _("64-bit")
        if self.config.get("Arch") == "win32":
            arch = _("32-bit")
        
        '''Lock signals preventing triggering'''
        self.switch_dxvk.handler_block_by_func(self.toggle_dxvk)
        self.switch_vkd3d.handler_block_by_func(self.toggle_vkd3d)
        self.switch_virtual_desktop.handler_block_by_func(self.toggle_virtual_desktop)
        self.combo_virtual_resolutions.handler_block_by_func(self.set_virtual_desktop_resolution)
        self.combo_runner.handler_block_by_func(self.set_runner)
        self.combo_dxvk.handler_block_by_func(self.set_dxvk)
        self.combo_vkd3d.handler_block_by_func(self.set_vkd3d)

        '''Populate widgets from config'''
        parameters = self.config.get("Parameters")
        self.entry_name.set_text(self.config.get("Name"))
        self.entry_name.set_tooltip_text(_("Updated: %s" % update_date))
        self.label_runner.set_text(self.config.get("Runner"))
        self.label_arch.set_text(arch)
        self.label_environment.set_text(
            _(self.config.get("Environment"))
        )
        self.label_environment.get_style_context().add_class(
            f"tag-{self.config.get('Environment').lower()}")
        self.label_state.set_text(str(self.config.get("State")))
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
        self.combo_runner.set_active_id(self.config.get("Runner"))
        self.combo_dxvk.set_active_id(self.config.get("DXVK"))
        self.combo_vkd3d.set_active_id(self.config.get("VKD3D"))
        self.grid_versioning.set_visible(self.config.get("Versioning"))

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
        new_window = EnvVarsDialog(self.window,
                                                 self.config)
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
            self.manager.update_config(config=self.config,
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
        new_config = self.manager.update_config(
            config=self.config,
            key="environment_variables",
            value=environment_variables,
            scope="Parameters")
        self.config = new_config

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
            Runner().get_bottle_path(self.config))
        response = file_dialog.run()

        if response == -3:
            self.manager.update_config(
                config=self.config,
                key=file_dialog.get_filename().split("/")[-1][:-4],
                value=file_dialog.get_filename(),
                scope="External_Programs")
            self.update_programs()

        file_dialog.destroy()

    '''Populate list_programs'''
    def update_programs(self, widget=False):
        for w in self.list_programs: w.destroy()
        for w in self.group_programs: w.destroy()

        programs = self.manager.get_programs(self.config)

        if len(programs) == 0:
            self.group_programs.set_visible(False)
            return
            
        self.group_programs.set_visible(True)

        i = 0
        for program in programs:
            self.list_programs.add(ProgramEntry(
                self.window, self.config, program))

            '''Append first 5 entries to group_programs'''
            if i < 5:
                self.group_programs.add(ProgramEntry(
                    self.window, self.config, program))
            i =+ 1

    '''Populate list_dependencies'''
    def update_dependencies(self, widget=False):
        for w in self.list_dependencies: w.destroy()

        supported_dependencies = self.manager.supported_dependencies.items()
        if len(supported_dependencies) > 0:
            for dependency in supported_dependencies:
                self.list_dependencies.add(
                    DependencyEntry(self.window,
                                           self.config,
                                           dependency))
            return

        if len(self.config.get("Installed_Dependencies")) > 0:
            for dependency in self.config.get("Installed_Dependencies"):
                self.list_dependencies.add(
                    DependencyEntry(self.window,
                                           self.config,
                                           dependency,
                                           plain=True))
            return

    '''Populate list_installers'''
    def update_installers(self, widget=False):
        for w in self.list_installers: w.destroy()

        supported_installers = self.manager.supported_installers.items()

        if len(supported_installers) > 0:
            for installer in supported_installers:
                self.list_installers.add(
                    InstallerEntry(self.window,
                                          self.config,
                                          installer))
            return

    '''Populate list_states'''
    def idle_update_states(self, widget=False):
        if self.config.get("Versioning"):
            for w in self.list_states: w.destroy()

            states = self.versioning_manager.list_bottle_states(self.config).items()
            if len(states) > 0:
                for state in states:
                    self.list_states.add(
                        StateEntry(self.window,
                                          self.config,
                                          state))

    def update_states(self, widget=False):
        GLib.idle_add(self.idle_update_states, widget=False)

    '''Toggle DXVK'''
    def toggle_dxvk(self, widget=False, state=False):
        if state:
            self.manager.install_dxvk(self.config)
        else:
            self.manager.remove_dxvk(self.config)

        new_config = self.manager.update_config(
            config=self.config,
            key="dxvk",
            value=state,
            scope="Parameters")
        self.config = new_config

    '''Toggle DXVK HUD'''
    def toggle_dxvk_hud(self, widget, state):
        new_config = self.manager.update_config(
            config=self.config,
            key="dxvk_hud",
            value=state,
            scope="Parameters")
        self.config = new_config

    '''Toggle VKD3D'''
    def toggle_vkd3d(self, widget=False, state=False):
        if state:
            self.manager.install_vkd3d(self.config)
        else:
            self.manager.remove_vkd3d(self.config)

        new_config = self.manager.update_config(
            config=self.config,
            key="vkd3d",
            value=state,
            scope="Parameters")
        self.config = new_config

    '''Toggle Gamemode'''
    def toggle_gamemode(self, widget=False, state=False):
        new_config = self.manager.update_config(
            config=self.config,
            key="gamemode",
            value=state,
            scope="Parameters")
        self.config = new_config

    '''Set Wine synchronization type'''
    def set_sync_type(self, sync):
        new_config = self.manager.update_config(
            config=self.config,
            key="sync",
            value=sync,
            scope="Parameters")
        self.config = new_config

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
        new_config = self.manager.update_config(
            config=self.config,
            key="aco_compiler",
            value=state,
            scope="Parameters")
        self.config = new_config

    '''Toggle discrete graphics usage'''
    def toggle_discrete_graphics(self, widget, state):
        new_config = self.manager.update_config(
            config=self.config,
            key="discrete_gpu",
            value=state,
            scope="Parameters")
        self.config = new_config

    '''Toggle virtual desktop'''
    def toggle_virtual_desktop(self, widget, state):
        resolution = self.combo_virtual_resolutions.get_active_id()
        self.manager.toggle_virtual_desktop(self.config,
                                           state,
                                           resolution)
        new_config = self.manager.update_config(
            config=self.config,
            key="virtual_desktop",
            value=state,
            scope="Parameters")
        self.config = new_config

    '''Set virtual desktop resolution'''
    def set_virtual_desktop_resolution(self, widget):
        resolution = widget.get_active_id()
        if self.switch_virtual_desktop.get_active():
            self.manager.toggle_virtual_desktop(self.config,
                                               True,
                                               resolution)
        new_config = self.manager.update_config(
            config=self.config,
            key="virtual_desktop_res",
            value=resolution,
            scope="Parameters")
        self.config = new_config

    '''Set (change) runner'''
    def set_runner(self, widget):
        runner = widget.get_active_id()
        new_config = self.manager.update_config(
            config=self.config,
            key="Runner",
            value=runner)
        self.config = new_config

    '''Set (change) dxvk'''
    def set_dxvk(self, widget):
        # remove old dxvk
        self.toggle_dxvk(state=False)

        dxvk = widget.get_active_id()
        new_config = self.manager.update_config(
            config=self.config,
            key="DXVK",
            value=dxvk)
        self.config = new_config

        # install new dxvk
        self.toggle_dxvk(state=True)

    '''Set (change) vkd3d'''
    def set_vkd3d(self, widget):
        # remove old vkd3d
        self.toggle_vkd3d(state=False)

        vkd3d = widget.get_active_id()
        new_config = self.manager.update_config(
            config=self.config,
            key="VKD3D",
            value=vkd3d)
        self.config = new_config

        # install new vkd3d
        self.toggle_vkd3d(state=True)

    '''Toggle pulseaudio latency'''
    def toggle_pulseaudio_latency(self, widget, state):
        new_config = self.manager.update_config(
            config=self.config,
            key="pulseaudio_latency",
            value=state,
            scope="Parameters")
        self.config = new_config

    '''Toggle fixme wine logs'''
    def toggle_fixme(self, widget, state):
        new_config = self.manager.update_config(
            config=self.config,
            key="fixme_logs",
            value=state,
            scope="Parameters")
        self.config = new_config

    def run_executable_with_args(self, widget):
        new_window = RunArgsDialog(self)
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
                Runner().run_executable(
                    config=self.config,
                    file_path=file_dialog.get_filename(),
                    arguments=args)
            else:
                Runner().run_executable(
                    config=self.config,
                    file_path=file_dialog.get_filename())

        file_dialog.destroy()

    '''Run wine executables and utilities'''
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
            self.versioning_manager.create_bottle_state(self.config, comment, after=self.update_states)
            self.entry_state_comment.set_text("")
            self.pop_state.popdown()

    '''Display file dialog for backup config'''
    def backup_config(self, widget):
        file_dialog = Gtk.FileChooserDialog(
            _("Select the location where to save the backup config"),
            self.window,
            Gtk.FileChooserAction.SAVE,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK))
        file_dialog.set_current_name("backup_%s.yml" % self.config.get("Path"))

        response = file_dialog.run()

        if response == Gtk.ResponseType.OK:
            RunnerBackup().backup_bottle(
                self.window,
                self.config,
                "config",
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
            "backup_%s.tar.gz" % self.config.get("Path"))

        response = file_dialog.run()

        if response == Gtk.ResponseType.OK:
            RunnerBackup().backup_bottle(
                self.window,
                self.config,
                "full",
                file_dialog.get_filename()
            )

        file_dialog.destroy()
    
    '''Duplicate bottle with another name'''
    def duplicate(self, widget):
        new_window = DuplicateDialog(self)
        new_window.present()

    '''Show dialog to confirm bottle deletion'''
    def confirm_delete(self, widget):
        dialog_delete = MessageDialog(
            parent=self.window,
            title=_("Confirm deletion"),
            message=_("Are you sure you want to delete this Bottle and all files?")
        )
        response = dialog_delete.run()

        if response == Gtk.ResponseType.OK:
            self.manager.delete_bottle(self.config)
            self.window.go_back()

        dialog_delete.destroy()

    '''Show dialog for DLL overrides'''
    def show_dll_overrides_view(self, widget=False):
        new_window = DLLOverridesDialog(self.window,
                                         self.config)
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
