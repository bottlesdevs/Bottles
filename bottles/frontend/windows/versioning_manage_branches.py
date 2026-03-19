# versioning_manage_branches.py
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

from gettext import gettext as _
from gi.repository import Adw, Gtk
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.utils.gtk import GtkUtils

@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-versioning-manage-branches.ui")
class VersioningManageBranchesDialog(Adw.PreferencesDialog):
    __gtype_name__ = "VersioningManageBranchesDialog"

    list_branches = Gtk.Template.Child()

    def __init__(self, parent, versioning_view, **kwargs):
        super().__init__(**kwargs)
        self.versioning_view = versioning_view
        self.manager = versioning_view.manager
        self.config = versioning_view.config
        
        self.refresh_branches()
        
    def refresh_branches(self):
        while self.list_branches.get_first_child():
            self.list_branches.remove(self.list_branches.get_first_child())
            
        def _fetch():
            res = self.manager.versioning_manager.list_states(self.config)
            if not getattr(res, "data", None):
                return [], ""
            branches = res.data.get("branches", [])
            active = res.data.get("active_branch", "")
            return branches, active
            
        @GtkUtils.run_in_main_loop
        def _on_fetched(result, error):
            if error or not result:
                return
            branches, active = result
            for branch in branches:
                row = Adw.ActionRow(title=branch)
                if branch == active:
                    row.set_subtitle(_("Active branch"))
                else:
                    btn = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER)
                    btn.set_tooltip_text(_("Delete Branch"))
                    btn.add_css_class("flat")
                    btn.connect("clicked", self.on_delete_branch, branch)
                    row.add_suffix(btn)
                self.list_branches.append(row)
                
        RunAsync(_fetch, _on_fetched)

    def on_delete_branch(self, button, branch_name):
        button.set_sensitive(False)
        
        @GtkUtils.run_in_main_loop
        def _on_deleted(result, error):
            self.refresh_branches()
            self.versioning_view.update()
            self.versioning_view._refresh_details_badge()
            
        RunAsync(
            task_func=self.manager.versioning_manager.delete_branch,
            callback=_on_deleted,
            config=self.config,
            branch_name=branch_name
        )
