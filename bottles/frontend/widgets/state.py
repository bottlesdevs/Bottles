# state.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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

from datetime import datetime
from gettext import gettext as _

from gi.repository import Adw, Gtk

import os
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.utils.gtk import GtkUtils
from bottles.backend.managers.manager import ManagerUtils
from bottles.backend.models.config import BottleConfig


@Gtk.Template(resource_path="/com/usebottles/bottles/state-entry.ui")
class StateEntry(Adw.ActionRow):
    __gtype_name__ = "StateEntry"

    # region Widgets
    label_hash = Gtk.Template.Child()
    label_branch = Gtk.Template.Child()
    label_date = Gtk.Template.Child()
    label_comment = Gtk.Template.Child()
    btn_restore = Gtk.Template.Child()
    spinner = Gtk.Template.Child()
    # endregion

    def __init__(self, parent, config, state, active, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.parent = parent
        self.window = parent.window
        self.manager = parent.window.manager
        self.queue = parent.window.page_details.queue
        self.state = state

        hash_id = str(state[0])[:7] if len(str(state[0])) > 7 else str(state[0])
        self.label_hash.set_text(hash_id)

        branch_name = state[1].get("Branch", "")
        if branch_name:
            self.label_branch.set_text(branch_name)
            self.label_branch.set_visible(True)

        if config.Versioning:
            date_str = datetime.strptime(
                state[1]["Creation_Date"], "%Y-%m-%d %H:%M:%S.%f"
            ).strftime("%d %B %Y, %H:%M")

            self.label_date.set_text(date_str)
            self.label_comment.set_text(state[1].get("Comment", ""))
            
            if str(state[0]) == str(config.State):
                self.add_css_class("current-state")
        else:
            date_str = datetime.fromtimestamp(state[1]["timestamp"]).strftime(
                "%d %B %Y, %H:%M"
            )
            self.label_date.set_text(date_str)
            self.label_comment.set_text(state[1].get("message", ""))
            
            if active:
                self.add_css_class("current-state")
        self.config = config
        self.versioning_manager = self.manager.versioning_manager

        # connect signals
        self.btn_restore.connect("clicked", self.set_state)

    def set_state(self, widget):
        """
        Set the bottle state to this one.
        """

        def handle_response(dialog, response_id):
            if response_id == "ok":
                self.queue.add_task()
                
                versioning_view = getattr(self.window.page_details, "view_versioning", None)
                if versioning_view and hasattr(versioning_view, "_set_busy"):
                    versioning_view._set_busy(True, _("Restoring state..."))
                else:
                    self.parent.set_sensitive(False)
                    self.spinner.show()
                    self.spinner.start()

                def _after():
                    if versioning_view and hasattr(versioning_view, "update"):
                        versioning_view.update()
                    self.manager.update_bottles()

                RunAsync(
                    task_func=self.versioning_manager.set_state,
                    callback=self.set_completed,
                    config=self.config,
                    state_id=self.state[0],
                    after=_after,
                )
            dialog.destroy()

        dialog = Adw.MessageDialog.new(
            self.window,
            _("Are you sure you want to restore this state?"),
            _(
                "Restoring this state will overwrite the current configuration and cannot be undone."
            ),
        )
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("ok", _("_Restore"))
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", handle_response)
        dialog.present()

    @GtkUtils.run_in_main_loop
    def set_completed(self, result, error=False):
        """
        Set completed status to the widget.
        """
        if not self.config.Versioning and result.message:
            self.window.show_toast(result.message)
            
        versioning_view = getattr(self.window.page_details, "view_versioning", None)
        if versioning_view and hasattr(versioning_view, "_set_busy"):
            versioning_view._set_busy(False)
        else:
            self.spinner.stop()
            self.spinner.hide()
            self.parent.set_sensitive(True)
            
        self.btn_restore.set_visible(False)
        self.queue.end_task()
        
        bottle_config_path = os.path.join(ManagerUtils.get_bottle_path(self.config), "bottle.yml")
        config_load = BottleConfig.load(bottle_config_path)
        if config_load.status:
            self.manager.local_bottles[self.config.Name] = config_load.data
            self.window.page_details.set_config(config_load.data)
