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

from gi.repository import Gtk

import webbrowser

@Gtk.Template(resource_path='/pm/mirko/bottles/program-entry.ui')
class BottlesProgramEntry(Gtk.Box):
    __gtype_name__ = 'BottlesProgramEntry'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    label_name = Gtk.Template.Child()
    btn_run = Gtk.Template.Child()

    def __init__(self, window, configuration, program, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        '''
        Common variables
        '''
        self.window = window
        self.runner = window.runner
        self.configuration = configuration
        self.program_name = program[0]
        self.program_executable = program[1]

        '''
        Set runner name to the label
        '''
        self.label_name.set_text(self.program_name)

        '''
        Connect signals to widgets
        '''
        self.btn_run.connect('pressed', self.run_executable)

    def run_executable(self, widget):
        self.runner.run_executable(self.configuration,
                                   self.program_executable)


@Gtk.Template(resource_path='/pm/mirko/bottles/dependency-entry.ui')
class BottlesDependencyEntry(Gtk.Box):
    __gtype_name__ = 'BottlesDependencyEntry'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    label_name = Gtk.Template.Child()
    label_description = Gtk.Template.Child()
    btn_install = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()

    def __init__(self, window, configuration, dependency, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        '''
        Common variables
        '''
        self.window = window
        self.runner = window.runner
        self.configuration = configuration
        self.dependency = dependency

        '''
        Set dependency name to the label
        '''
        self.label_name.set_text(dependency[0])
        self.label_description.set_text(dependency[1].get("Description"))

        '''
        Connect signals to widgets
        '''
        self.btn_install.connect('pressed', self.install_dependency)
        self.btn_remove.connect('pressed', self.remove_dependency)

        '''
        Set widgets status from configuration
        '''
        if dependency[0] in self.configuration.get("Installed_Dependencies"):
            self.btn_install.set_visible(False)
            self.btn_remove.set_visible(True)

    def install_dependency(self, widget):
        widget.set_sensitive(False)
        self.runner.install_dependency(self.configuration,
                                       self.dependency,
                                       self)

    def remove_dependency(self, widget):
        widget.set_sensitive(False)
        self.runner.remove_dependency(self.configuration,
                                      self.dependency,
                                      self)


@Gtk.Template(resource_path='/pm/mirko/bottles/details.ui')
class BottlesDetails(Gtk.Box):
    __gtype_name__ = 'BottlesDetails'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    label_name = Gtk.Template.Child()
    label_runner = Gtk.Template.Child()
    label_size = Gtk.Template.Child()
    label_disk = Gtk.Template.Child()
    notebook_details = Gtk.Template.Child()
    btn_winecfg = Gtk.Template.Child()
    btn_winetricks = Gtk.Template.Child()
    btn_debug = Gtk.Template.Child()
    btn_execute = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_cmd = Gtk.Template.Child()
    btn_taskmanager = Gtk.Template.Child()
    btn_controlpanel = Gtk.Template.Child()
    btn_uninstaller = Gtk.Template.Child()
    btn_regedit = Gtk.Template.Child()
    btn_shutdown = Gtk.Template.Child()
    btn_reboot = Gtk.Template.Child()
    btn_killall = Gtk.Template.Child()
    btn_report_dependency = Gtk.Template.Child()
    btn_programs_updates = Gtk.Template.Child()
    btn_environment_variables = Gtk.Template.Child()
    btn_manage_runners = Gtk.Template.Child()
    switch_dxvk = Gtk.Template.Child()
    switch_dxvk_hud = Gtk.Template.Child()
    switch_esync = Gtk.Template.Child()
    switch_fsync = Gtk.Template.Child()
    switch_discrete = Gtk.Template.Child()
    switch_virtual_desktop = Gtk.Template.Child()
    combo_virtual_resolutions = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    switch_pulseaudio_latency = Gtk.Template.Child()
    list_dependencies = Gtk.Template.Child()
    list_programs = Gtk.Template.Child()
    progress_disk = Gtk.Template.Child()
    textview_overrides = Gtk.Template.Child()
    entry_environment_variables = Gtk.Template.Child()
    buffer_overrides = Gtk.Template.Child()

    def __init__(self, window, configuration={}, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        '''
        Common variables
        '''
        self.window = window
        self.runner = window.runner
        self.configuration = configuration

        '''
        Populate combo_runner with installed runners
        '''
        for runner in self.runner.runners_available:
            self.combo_runner.append(runner, runner)

        '''
        Connect signals to widgets
        '''
        self.btn_winecfg.connect('pressed', self.run_winecfg)
        self.btn_winetricks.connect('pressed', self.run_winetricks)
        self.btn_debug.connect('pressed', self.run_debug)
        self.btn_execute.connect('pressed', self.run_executable)
        self.btn_browse.connect('pressed', self.run_browse)
        self.btn_cmd.connect('pressed', self.run_cmd)
        self.btn_taskmanager.connect('pressed', self.run_taskmanager)
        self.btn_controlpanel.connect('pressed', self.run_controlpanel)
        self.btn_uninstaller.connect('pressed', self.run_uninstaller)
        self.btn_regedit.connect('pressed', self.run_regedit)
        self.btn_shutdown.connect('pressed', self.run_shutdown)
        self.btn_reboot.connect('pressed', self.run_reboot)
        self.btn_killall.connect('pressed', self.run_killall)
        self.btn_report_dependency.connect('pressed', self.open_report_url)
        self.btn_programs_updates.connect('pressed', self.update_programs)
        self.btn_environment_variables.connect('pressed', self.save_environment_variables)
        self.btn_manage_runners.connect('pressed', self.window.show_runners_preferences_view)
        self.switch_dxvk.connect('state-set', self.toggle_dxvk)
        self.switch_dxvk_hud.connect('state-set', self.toggle_dxvk_hud)
        self.switch_esync.connect('state-set', self.toggle_esync)
        self.switch_fsync.connect('state-set', self.toggle_fsync)
        self.switch_discrete.connect('state-set', self.toggle_discrete_graphics)
        self.switch_virtual_desktop.connect('state-set', self.toggle_virtual_desktop)
        self.combo_virtual_resolutions.connect('changed', self.set_virtual_desktop_resolution)
        self.combo_runner.connect('changed', self.set_runner)
        self.switch_pulseaudio_latency.connect('state-set', self.toggle_pulseaudio_latency)

    def set_configuration(self, configuration):
        self.configuration = configuration

        '''
        Block signals to prevent execute widget callbacks
        '''
        self.switch_dxvk.handler_block_by_func(self.toggle_dxvk)
        self.switch_virtual_desktop.handler_block_by_func(self.toggle_virtual_desktop)
        self.combo_virtual_resolutions.handler_block_by_func(self.set_virtual_desktop_resolution)
        self.combo_runner.handler_block_by_func(self.set_runner)

        '''
        Get bottle disk usage and free space
        '''
        bottle_size = self.runner.get_bottle_size(configuration)
        bottle_size_float = self.runner.get_bottle_size(configuration, False)
        disk_total = self.runner.get_disk_size()["total"]
        disk_total_float = self.runner.get_disk_size(False)["total"]
        disk_free = self.runner.get_disk_size()["free"]
        disk_fraction = ((bottle_size_float / disk_total_float) * 100) / 10

        '''
        Set widgets status from configuration
        '''
        parameters = self.configuration.get("Parameters")
        self.label_name.set_text(self.configuration.get("Name"))
        self.label_runner.set_text(self.configuration.get("Runner"))
        self.label_size.set_text(bottle_size)
        self.label_disk.set_text(disk_free)
        self.progress_disk.set_fraction(disk_fraction)
        self.switch_dxvk.set_active(parameters["dxvk"])
        self.switch_dxvk_hud.set_active(parameters["dxvk_hud"])
        self.switch_esync.set_active(parameters["esync"])
        self.switch_fsync.set_active(parameters["fsync"])
        self.switch_discrete.set_active(parameters["discrete_gpu"])
        self.switch_virtual_desktop.set_active(parameters["virtual_desktop"])
        self.combo_virtual_resolutions.set_active_id(parameters["virtual_desktop_res"])
        self.combo_runner.set_active_id(self.configuration.get("Runner"))
        self.switch_pulseaudio_latency.set_active(parameters["pulseaudio_latency"])
        self.entry_environment_variables.set_text(parameters["environment_variables"])

        '''
        Unlock signals
        '''
        self.switch_dxvk.handler_unblock_by_func(self.toggle_dxvk)
        self.switch_virtual_desktop.handler_unblock_by_func(self.toggle_virtual_desktop)
        self.combo_virtual_resolutions.handler_unblock_by_func(self.set_virtual_desktop_resolution)
        self.combo_runner.handler_unblock_by_func(self.set_runner)

        self.update_programs()
        self.update_dependencies()

    def set_page(self, page):
        self.notebook_details.set_current_page(page)

    def save_environment_variables(self, widget):
        environment_variables = self.entry_environment_variables.get_text()
        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "environment_variables",
                                                             environment_variables,
                                                             True)
        self.configuration = new_configuration

    '''
    Add entries to list_programs
    '''
    def update_programs(self, widget=False):
        for w in self.list_programs: w.destroy()

        for program in self.runner.get_programs(self.configuration):
            self.list_programs.add(
                BottlesProgramEntry(self.window, self.configuration, program))

    '''
    Add entries to list_dependencies
    '''
    def update_dependencies(self, widget=False):
        for w in self.list_dependencies: w.destroy()

        for dependency in self.runner.supported_dependencies.items():
            self.list_dependencies.add(
                BottlesDependencyEntry(self.window,
                                       self.configuration,
                                       dependency))

    '''
    Methods to change environment variables
    '''
    def toggle_dxvk(self, widget, state):
        if state:
            self.runner.install_dxvk(self.configuration)
        else:
            self.runner.remove_dxvk(self.configuration)

        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "dxvk",
                                                             state,
                                                             True)
        self.configuration = new_configuration

    def toggle_dxvk_hud(self, widget, state):
        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "dxvk_hud",
                                                             state,
                                                             True)
        self.configuration = new_configuration

    def toggle_esync(self, widget, state):
        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "esync",
                                                             state,
                                                             True)
        self.configuration = new_configuration

    def toggle_fsync(self, widget, state):
        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "fsync",
                                                             state,
                                                             True)
        self.configuration = new_configuration

    def toggle_discrete_graphics(self, widget, state):
        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "discrete_gpu",
                                                             state,
                                                             True)
        self.configuration = new_configuration

    def toggle_virtual_desktop(self, widget, state):
        resolution = self.combo_virtual_resolutions.get_active_id()
        self.runner.toggle_virtual_desktop(self.configuration,
                                           state,
                                           resolution)
        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "virtual_desktop",
                                                             state,
                                                             True)
        self.configuration = new_configuration

    def set_virtual_desktop_resolution(self, widget):
        resolution = widget.get_active_id()
        if self.switch_virtual_desktop.get_active():
            self.runner.toggle_virtual_desktop(self.configuration,
                                               True,
                                               resolution)
        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "virtual_desktop_res",
                                                             resolution,
                                                             True)
        self.configuration = new_configuration

    def set_runner(self, widget):
        runner = widget.get_active_id()
        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "Runner",
                                                             runner,
                                                             False)
        self.configuration = new_configuration

    def toggle_pulseaudio_latency(self, widget, state):
        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "pulseaudio_latency",
                                                             state,
                                                             True)
        self.configuration = new_configuration

    '''
    Methods for wine utilities
    '''
    def run_winecfg(self, widget):
        self.runner.run_winecfg(self.configuration)

    def run_winetricks(self, widget):
        self.runner.run_winetricks(self.configuration)

    def run_debug(self, widget):
        self.runner.run_debug(self.configuration)

    '''
    Show a file chooser dialog to choose and run a Windows executable
    TODO: this method  (and other) should be declared in different file
    to be reusable in other files, like list.py
    '''
    def run_executable(self, widget):
        file_dialog = Gtk.FileChooserDialog("Choose a Windows executable file",
                                            self.window,
                                            Gtk.FileChooserAction.OPEN,
                                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                            Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

        '''
        Create filter for each allowed file extension
        '''
        filter_exe = Gtk.FileFilter()
        filter_exe.set_name(".exe")
        filter_exe.add_pattern("*.exe")

        filter_msi = Gtk.FileFilter()
        filter_msi.set_name(".msi")
        filter_msi.add_pattern("*.msi")

        file_dialog.add_filter(filter_exe)
        file_dialog.add_filter(filter_msi)

        response = file_dialog.run()

        if response == Gtk.ResponseType.OK:
            self.runner.run_executable(self.configuration,
                                       file_dialog.get_filename())

        file_dialog.destroy()

    def run_browse(self, widget):
        self.runner.open_filemanager(self.configuration)

    def run_cmd(self, widget):
        self.runner.run_cmd(self.configuration)

    def run_taskmanager(self, widget):
        self.runner.run_taskmanager(self.configuration)

    def run_controlpanel(self, widget):
        self.runner.run_controlpanel(self.configuration)

    def run_uninstaller(self, widget):
        self.runner.run_uninstaller(self.configuration)

    def run_regedit(self, widget):
        self.runner.run_regedit(self.configuration)

    def run_shutdown(self, widget):
        self.runner.send_status(self.configuration, "shutdown")

    def run_reboot(self, widget):
        self.runner.send_status(self.configuration, "reboot")

    def run_killall(self, widget):
        self.runner.send_status(self.configuration, "kill")

    '''
    Open URLs
    '''
    def open_report_url(self, widget):
        webbrowser.open_new_tab("https://github.com/bottlesdevs/dependencies/issues/new/choose")
