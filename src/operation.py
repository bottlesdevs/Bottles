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

import gi
from gettext import gettext as _
gi.require_version('Handy', '1')
from gi.repository import Gtk, Handy


@Gtk.Template(resource_path='/com/usebottles/bottles/task-entry.ui')
class TaskEntry(Handy.ActionRow):
    __gtype_name__ = 'TaskEntry'

    # region Widgets
    btn_cancel = Gtk.Template.Child()
    spinner_task = Gtk.Template.Child()
    label_task_status = Gtk.Template.Child()

    # endregion

    def __init__(self, window, title, cancellable=True, **kwargs):
        super().__init__(**kwargs)

        self.window = window
        self.list_tasks = window.list_tasks
        self.btn_operations = window.btn_operations

        if len(title) > 30:
            title = f"{title[:20]}..."

        # Set btn_operations visible
        self.window.btn_operations.set_visible(True)

        # Populate widgets data
        self.set_title(title)
        if not cancellable:
            self.btn_cancel.hide()

        self.spinner_task.start()

    def update_status(
            self,
            count=False,
            block_size=False,
            total_size=False,
            completed=False
    ):
        if not self.label_task_status.get_visible():
            self.label_task_status.set_visible(True)

        if total_size == 0:
            self.label_task_status.set_text(_("Calculating..."))
            return

        if not completed:
            percent = int(count * block_size * 100 / total_size)
            self.label_task_status.set_text(f'{str(percent)}%')
        else:
            percent = 100

        if percent == 100:
            self.spinner_task.stop()
            self.remove()

    def remove(self):
        tasks = self.list_tasks.get_children()
        if len(tasks) <= 1:
            if not self.btn_operations.get_active():
                self.btn_operations.set_visible(False)
        self.destroy()


class OperationManager:
    __tasks = {}

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        # Common variables
        self.window = window
        self.list_tasks = window.list_tasks

    def __new_widget(self, title, cancellable=True):
        task_entry = TaskEntry(self.window, title, cancellable)
        self.list_tasks.add(task_entry)
        return task_entry

    def new_task(self, task_id, title, cancellable=True):
        self.__tasks[task_id] = self.__new_widget(title, cancellable)

    def update_task(self,
                    task_id,
                    count=False,
                    block_size=False,
                    total_size=False,
                    completed=False
                    ):
        if self.get_task(task_id):
            self.__tasks[task_id].update_status(
                count, block_size, total_size, completed
            )

    def remove_task(self, task_id):
        if self.get_task(task_id):
            self.__tasks[task_id].remove()
            del self.__tasks[task_id]

    def remove_all_tasks(self):
        for task in self.__tasks:
            self.__tasks[task].remove()
        self.__tasks = {}

    def get_tasks(self):
        return self.__tasks

    def get_task(self, task_id):
        return self.__tasks.get(task_id)

    def get_task_count(self):
        return len(self.__tasks)

    def get_task_ids(self):
        return list(self.__tasks.keys())
