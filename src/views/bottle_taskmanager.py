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

from gettext import gettext as _
from gi.repository import Gtk

from ..utils import RunAsync
from ..backend.runner import Runner


@Gtk.Template(resource_path='/com/usebottles/bottles/details-taskmanager.ui')
class TaskManagerView(Gtk.ScrolledWindow):
    __gtype_name__ = 'TaskManagerView'

    # region Widgets
    treeview_processes = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        # apply model to treeview_processes
        self.liststore_processes = Gtk.ListStore(str, str, str, str)
        self.treeview_processes.set_model(self.liststore_processes)

        cell_renderer = Gtk.CellRendererText()
        i = 0

        for column in ["PID", "Name", "Threads", "Parent"]:
            '''
            For each column, add it to the treeview_processes
            '''
            column = Gtk.TreeViewColumn(column, cell_renderer, text=i)
            self.treeview_processes.append_column(column)
            i += 1

        self.update()

    def update_processes(self, widget=False, config={}):
        '''
        This function scan for new processed and update the
        liststore_processes with the new data
        '''
        self.config = config

        self.liststore_processes.clear()
        processes = Runner.get_processes(self.config)

        if len(processes) > 0:
            for process in processes:
                self.liststore_processes.append([
                    process.get("pid"),
                    process.get("name", "n/a"),
                    process.get("threads", "0"),
                    process.get("parent", "0")
                ])
    
    def update(self, widget=False, config={}):
        '''
        This function is called when the btn_processes_updates is
        pressed. It will update the liststore_processes with the
        new data. It is an async wrapper for update_processes.
        '''
        RunAsync(self.update_processes, None, False, config)    