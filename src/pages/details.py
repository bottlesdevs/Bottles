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


@Gtk.Template(resource_path='/pm/mirko/bottles/details.ui')
class BottlesDetails(Gtk.Box):
    __gtype_name__ = 'BottlesDetails'

    '''
    Get and assign widgets to variables from
    template childs
    '''
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

    def __init__(self, window, **kwargs):
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

    def run_winecfg(self, widget):
        '''
        p = Popen(['watch', 'ls'])
        '''
        self.runner.run_winecfg()

    def run_winetricks(self, widget):
        self.runner.run_winetricks()

    def run_debug(self, widget):
        self.runner.run_debug()

    def run_executable(self, widget):
        self.runner.run_executable()

    def run_browse(self, widget):
        self.runner.open_filemanager()

    def run_cmd(self, widget):
        self.runner.run_cmd()

    def run_taskmanager(self, widget):
        self.runner.run_taskmanager()

    def run_controlpanel(self, widget):
        self.runner.run_controlpanel()

    def run_uninstaller(self, widget):
        self.runner.run_uninstaller()

    def run_regedit(self, widget):
        self.runner.run_regedit()

    def run_shutdown(self, widget):
        self.runner.send_status(0)

    def run_reboot(self, widget):
        self.runner.send_status(1)
