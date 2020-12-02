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


@Gtk.Template(resource_path='/pm/mirko/bottles/dependency-entry.ui')
class BottlesDependencyEntry(Gtk.Box):
    __gtype_name__ = 'BottlesDependencyEntry'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    label_name = Gtk.Template.Child()
    label_description = Gtk.Template.Child()

    def __init__(self, window, name, description, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        '''
        Common variables
        '''
        self.window = window

        '''
        Set dependency name to the label
        '''
        self.label_name.set_text(name)
        self.label_description.set_text(description)


@Gtk.Template(resource_path='/pm/mirko/bottles/details.ui')
class BottlesDetails(Gtk.Box):
    __gtype_name__ = 'BottlesDetails'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    label_name = Gtk.Template.Child()
    label_size = Gtk.Template.Child()
    label_disk = Gtk.Template.Child()
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
    switch_dxvk = Gtk.Template.Child()
    switch_esync = Gtk.Template.Child()
    switch_fsync = Gtk.Template.Child()
    switch_discrete = Gtk.Template.Child()
    switch_virtual_desktop = Gtk.Template.Child()
    combo_virtual_resolutions = Gtk.Template.Child()
    switch_pulseaudio_latency = Gtk.Template.Child()
    list_dependencies = Gtk.Template.Child()

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
        self.switch_dxvk.connect('state-set', self.toggle_dxvk)
        self.switch_esync.connect('state-set', self.toggle_esync)
        self.switch_fsync.connect('state-set', self.toggle_fsync)
        self.switch_discrete.connect('state-set', self.toggle_discrete_graphics)
        self.switch_virtual_desktop.connect('state-set', self.toggle_virtual_desktop)
        self.combo_virtual_resolutions.connect('changed', self.set_virtual_desktop_resolution)
        self.switch_pulseaudio_latency.connect('state-set', self.toggle_pulseaudio_latency)

        '''
        Add entries to list_dependencies
        TODO: In BottlesDependencyEntry should check for installation status
        from Bottle configuration `Installed_Dependencies`
        '''
        for dependency in self.runner.supported_dependencies.items():
            self.list_dependencies.add(
                BottlesDependencyEntry(self.window,
                                       dependency[0],
                                       dependency[1].get("description")))

    def set_configuration(self, configuration):
        self.configuration = configuration

        '''
        Set widgets status from configuration
        '''
        parameters = self.configuration.get("Parameters")
        self.label_name.set_text(self.configuration.get("Name"))
        self.label_size.set_text(self.runner.get_bottle_size(configuration))
        self.label_disk.set_text(self.runner.get_disk_size()["free"])
        self.switch_dxvk.set_active(parameters["dxvk"])
        self.switch_esync.set_active(parameters["esync"])
        self.switch_fsync.set_active(parameters["fsync"])
        self.switch_discrete.set_active(parameters["discrete_gpu"])
        self.switch_virtual_desktop.set_active(parameters["virtual_desktop"])
        self.combo_virtual_resolutions.set_active_id(parameters["virtual_desktop_res"])
        self.switch_pulseaudio_latency.set_active(parameters["pulseaudio_latency"])

    '''
    Methods to change environment variables
    '''
    def toggle_dxvk(self, widget, state):
        '''
        TODO: dxvk should be installed and removed only when the switcher is
        toggled by the user and not when configuration is applied
        '''
        if state:
            self.runner.install_dxvk(self.configuration)
        else:
            self.runner.remove_dxvk(self.configuration)

        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "dxvk",
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
        '''
        TODO: to enable virtual desktop, change /Software/Wine/Explorer/Desktops
        '''
        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "virtual_desktop",
                                                             state,
                                                             True)
        self.configuration = new_configuration

    def set_virtual_desktop_resolution(self, widget):
        option = widget.get_active_id()
        new_configuration = self.runner.update_configuration(self.configuration,
                                                             "virtual_desktop_res",
                                                             option,
                                                             True)
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
