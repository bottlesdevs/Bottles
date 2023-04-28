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
from typing import Dict
from uuid import UUID

import gi

from bottles.backend.models.result import Result
from bottles.backend.state import TaskManager

gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw


@Gtk.Template(resource_path='/com/usebottles/bottles/task-entry.ui')
class TaskEntry(Adw.ActionRow):
    __gtype_name__ = 'TaskEntry'

    # region Widgets
    btn_cancel = Gtk.Template.Child()

    # endregion

    def __init__(self, window, title, cancellable=True, **kwargs):
        super().__init__(**kwargs)

        self.window = window

        if len(title) > 30:
            title = f"{title[:20]}…"

        # Populate widgets data
        self.set_title(title)
        if not cancellable:
            self.btn_cancel.hide()

    def update(self, subtitle: str):
        self.set_subtitle(subtitle)


class TaskSyncer:
    """Keep task list updated with backend TaskManager"""
    _TASK_WIDGETS: Dict[UUID, TaskEntry] = {}

    def __init__(self, window):
        self.window = window

    def _new_widget(self, title, cancellable=True) -> TaskEntry:
        """create TaskEntry widget & add to task list"""
        task_entry = TaskEntry(self.window, title, cancellable)
        self.window.page_details.list_tasks.append(task_entry)
        return task_entry

    def _set_task_btn_visible(self, visible: bool):
        self.window.page_details.btn_operations.set_visible(visible)

    def task_added_handler(self, res: Result):
        """handler for Signals.TaskAdded"""
        task_id: UUID = res.data
        task = TaskManager.get(task_id)
        self._TASK_WIDGETS[task_id] = self._new_widget(task.title, task.cancellable)
        self._set_task_btn_visible(True)

    def task_updated_handler(self, res: Result):
        """handler for Signals.TaskUpdated"""
        task_id: UUID = res.data
        if task_id not in self._TASK_WIDGETS:
            return

        self._TASK_WIDGETS[task_id].update(subtitle=TaskManager.get(task_id).subtitle)

    def task_removed_handler(self, res: Result):
        """handler for Signals.TaskRemoved"""
        task_id: UUID = res.data
        if task_id not in self._TASK_WIDGETS:
            return

        self.window.page_details.list_tasks.remove(self._TASK_WIDGETS[task_id])
        del self._TASK_WIDGETS[task_id]

        if len(self._TASK_WIDGETS) == 0:
            self._set_task_btn_visible(False)
