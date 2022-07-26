# operation.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# pylint: disable=import-error,missing-docstring

import gi
from gettext import gettext as _

gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw


@Gtk.Template(resource_path='/com/usebottles/bottles/task-entry.ui')
class TaskEntry(Adw.ActionRow):
    __gtype_name__ = 'TaskEntry'

    # region Widgets
    btn_cancel = Gtk.Template.Child()

    # endregion

    def __init__(self, op_manager, title, cancellable=True, **kwargs):
        super().__init__(**kwargs)

        self.op_manager = op_manager
        self.window = op_manager.window

        if len(title) > 30:
            title = f"{title[:20]}…"

        # Populate widgets data
        self.set_title(title)
        if not cancellable:
            self.btn_cancel.hide()

    def update_status(self, count=False, block_size=False, total_size=False, completed=False):
        if total_size == 0:
            self.set_subtitle(_("Calculating…"))
            return

        if not completed:
            percent = int(count * block_size * 100 / total_size)
            self.set_subtitle(f'{str(percent)}%')
        else:
            percent = 100

        if percent == 100:
            self.op_manager.remove_task(self)

    def remove(self):
        self.window.page_details.list_tasks.remove(self)


class OperationManager:
    __tasks = {}

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        # Common variables
        self.window = window

    def __new_widget(self, title, cancellable=True):
        task_entry = TaskEntry(self, title, cancellable)
        self.window.page_details.list_tasks.append(task_entry)
        return task_entry

    def new_task(self, task_id, title, cancellable=True):
        self.__tasks[task_id] = self.__new_widget(title, cancellable)
        self.window.page_details.btn_operations.set_visible(True)

    def update_task(self, task_id, count=False, block_size=False, total_size=False, completed=False):
        if self.get_task(task_id):
            self.__tasks[task_id].update_status(
                count, block_size, total_size, completed
            )

    def remove_task(self, task_id):
        if self.get_task(task_id):
            self.__tasks[task_id].remove()
            del self.__tasks[task_id]

        if self.get_task_count() == 0:
            self.window.page_details.btn_operations.set_visible(False)

    def remove_all_tasks(self):
        for task in self.__tasks:
            self.__tasks[task].remove()
        self.__tasks = {}
        self.window.page_details.btn_operations.set_visible(False)

    def get_tasks(self):
        return self.__tasks

    def get_task(self, task_id):
        return self.__tasks.get(task_id)

    def get_task_count(self):
        return len(self.__tasks)

    def get_task_ids(self):
        return list(self.__tasks.keys())
