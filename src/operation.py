# operation.py
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
from gi.repository import Gtk, GLib, Handy


@Gtk.Template(resource_path='/com/usebottles/bottles/task-entry.ui')
class TaskEntry(Handy.ActionRow):
    __gtype_name__ = 'TaskEntry'

    # region Widgets
    btn_cancel = Gtk.Template.Child()
    spinner_task = Gtk.Template.Child()
    label_task_status = Gtk.Template.Child()
    # endregion

    def __init__(self, window, file_name, cancellable=True, **kwargs):
        super().__init__(**kwargs)

        self.window = window
        self.list_tasks = window.list_tasks

        if len(file_name) > 30:
            file_name = f"{file_name[:20]}..."

        # Set btn_operations visible
        self.window.btn_operations.set_visible(True)

        # Populate widgets data
        self.set_title(file_name)
        if not cancellable:
            self.btn_cancel.hide()

        self.spinner_task.start()

    def idle_update_status(
        self,
        count=False,
        block_size=False,
        total_size=False,
        completed=False
    ):
        if not self.label_task_status.get_visible():
            self.label_task_status.set_visible(True)

        if not completed:
            percent = int(count * block_size * 100 / total_size)
            self.label_task_status.set_text(f'{str(percent)}%')
        else:
            percent = 100

        if percent == 100:
            self.spinner_task.stop()
            self.remove()

    def update_status(
        self,
        count=False,
        block_size=False,
        total_size=False,
        completed=False
    ):
        GLib.idle_add(
            self.idle_update_status,
            count,
            block_size,
            total_size,
            completed
        )

    def remove(self):
        tasks = self.list_tasks.get_children()
        if len(tasks) <= 1:
            self.window.btn_operations.set_visible(False)
        self.destroy()


class OperationManager():

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        # Common variables
        self.window = window
        self.list_tasks = window.list_tasks

    def new_task(self, file_name, cancellable=True):
        task_entry = TaskEntry(
            self.window, file_name, cancellable)
        self.window.list_tasks.add(task_entry)

        return task_entry
