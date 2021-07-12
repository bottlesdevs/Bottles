# taskmanager.py
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

@Gtk.Template(resource_path='/com/usebottles/bottles/task-manager.ui')
class BottlesTaskManager(Gtk.Box):
    __gtype_name__ = 'BottlesTaskManager'

    '''Get widgets from template'''
    treeview_processes = Gtk.Template.Child()
    btn_processes_update = Gtk.Template.Child()

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        '''Common variables'''
        self.window = window
        self.runner = window.runner

        '''Apply model to treeview_processes'''
        self.liststore_processes = Gtk.ListStore(str, str, str, str, str, str)
        self.treeview_processes.set_model(self.liststore_processes)

        cell_renderer = Gtk.CellRendererText()
        i = 0

        '''Add columns to treeview_processes'''
        for column in ["PID", "Memory", "CPU", "Start", "Time", "Command"]:
            column = Gtk.TreeViewColumn(column, cell_renderer, text=i)
            self.treeview_processes.append_column(column)
            i += 1

        '''Signal connections'''
        self.btn_processes_update.connect('pressed', self.update_processes)

        '''Run updates'''
        self.update_processes()

    '''Populate liststore_processes'''
    def update_processes(self, widget=False):
        self.liststore_processes.clear()
        processes = self.runner.get_running_processes()

        if len(processes) > 0:
            for process in processes:
                self.liststore_processes.append ([
                    process["pid"],
                    process["pmem"],
                    process["pcpu"],
                    process["stime"],
                    process["time"],
                    process["cmd"]
                ])
