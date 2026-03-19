# bottle_versioning.py
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

from gi.repository import Adw, GLib, Gtk

from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.utils.common import open_doc_url
from bottles.frontend.utils.gtk import GtkUtils
from bottles.frontend.widgets.state import StateEntry
from bottles.frontend.windows.versioning_branch import VersioningBranchDialog
from bottles.frontend.windows.versioning_commit import VersioningCommitDialog
from bottles.frontend.windows.versioning_manage_branches import VersioningManageBranchesDialog


@Gtk.Template(resource_path="/com/usebottles/bottles/details-versioning.ui")
class VersioningView(Adw.PreferencesPage):
    __gtype_name__ = "DetailsVersioning"
    __registry = []

    # region Widgets
    combo_branch = Gtk.Template.Child()
    btn_add_branch = Gtk.Template.Child()
    btn_manage_branches = Gtk.Template.Child()
    banner_dirty = Gtk.Template.Child()
    list_states = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    status_page = Gtk.Template.Child()
    pref_page = Gtk.Template.Child()
    btn_add = Gtk.Template.Child()
    box_spinner = Gtk.Template.Child()
    spinner = Gtk.Template.Child()
    label_spinner = Gtk.Template.Child()

    # endregion

    def __init__(self, details, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = details.window
        self.details = details
        self.manager = details.window.manager
        self.versioning_manager = details.window.manager.versioning_manager
        self.config = config

        self.btn_add.connect("clicked", self.show_add_state_dialog)
        self.btn_add_branch.connect("clicked", self.show_add_branch_dialog)
        self.btn_manage_branches.connect("clicked", self.show_manage_branches_dialog)
        self.banner_dirty.connect("button-clicked", self.show_add_state_dialog)
        self.combo_branch.connect("notify::selected-item", self.on_branch_changed)
        
        self.connect("map", self._on_mapped)

    def _on_mapped(self, widget):
        self._refresh_dirty_state()

    def _refresh_dirty_state(self):
        if not self.config or self.config.Versioning:
            return
            
        def _fetch():
            res = self.versioning_manager.list_states(self.config, check_dirty=True)
            if res and hasattr(res, "data") and res.data:
                return res.data.get("dirty", False)
            return False
            
        @GtkUtils.run_in_main_loop
        def _apply(dirty, error):
            if not error:
                self.banner_dirty.set_revealed(dirty)
                
        RunAsync(_fetch, _apply)

    def _set_busy(self, busy, label=""):
        self.combo_branch.set_sensitive(not busy)
        self.btn_add.set_sensitive(not busy)
        self.btn_add_branch.set_sensitive(not busy)
        self.list_states.set_sensitive(not busy)
        if label:
            self.label_spinner.set_text(label)
        self.spinner.set_spinning(busy)
        self.box_spinner.set_visible(busy)

    def _refresh_details_badge(self):
        try:
            bottle_view = self.details.view_bottle
            bottle_path = ManagerUtils.get_bottle_path(self.config)
            bottle_view._BottleView__update_fvs2_badge(bottle_path)
        except Exception:
            pass

    def on_branch_changed(self, widget, pspec):
        item = self.combo_branch.get_selected_item()
        if not item:
            return
            
        branch_name = item.get_string()
        self._set_busy(True, _("Switching branch…"))
        
        @GtkUtils.run_in_main_loop
        def cb(result, error):
            self._set_busy(False)
            self.update()
            self._refresh_details_badge()
            
        RunAsync(
            task_func=self.versioning_manager.checkout_branch,
            callback=cb,
            config=self.config,
            branch_name=branch_name
        )

    def show_add_branch_dialog(self, widget):
        dialog = VersioningBranchDialog(parent=self.window, callback=self.create_branch)
        dialog.present(self.window)

    def show_manage_branches_dialog(self, widget):
        dialog = VersioningManageBranchesDialog(parent=self.window, versioning_view=self)
        dialog.present(self.window)

    def create_branch(self, branch_name: str):
        if not branch_name:
            return
        self._set_busy(True, _("Creating branch…"))
            
        @GtkUtils.run_in_main_loop
        def cb(result, error):
            self._set_busy(False)
            self.update()
            self._refresh_details_badge()
            
        RunAsync(
            task_func=self.versioning_manager.create_branch,
            callback=cb,
            config=self.config,
            branch_name=branch_name
        )

    def empty_list(self):
        for r in self.__registry:
            if r.get_parent() is not None:
                r.get_parent().remove(r)
        self.__registry = []

    def update(self, widget=None, config=None, states=None, active=0):
        """
        This function update the states list with the
        ones from the bottle configuration.
        """
        if config is None:
            config = self.config
            
        self.config = config
        self.list_states.set_sensitive(False)

        def _do_update(_states, _active, _branches, _active_branch, _dirty=False, _changed_files=0):
            @GtkUtils.run_in_main_loop
            def _apply():
                if not self.config.Versioning and _branches:
                    self.combo_branch.handler_block_by_func(self.on_branch_changed)
                    
                    # Save the current list of branches in Python to lookup items
                    strings = Gtk.StringList.new(_branches)
                    self.combo_branch.set_model(strings)
                    try:
                        idx = _branches.index(_active_branch)
                        self.combo_branch.set_selected(idx)
                    except ValueError:
                        pass
                    self.combo_branch.handler_unblock_by_func(self.on_branch_changed)

                if self.versioning_manager.needs_migration(self.config):
                    self.btn_add.set_sensitive(False)
                    self.btn_add.set_tooltip_text(
                        _("Please migrate to the new Versioning system to create new states.")
                    )
                else:
                    self.banner_dirty.set_revealed(_dirty)

                def new_state(_state, active):
                    entry = StateEntry(
                        parent=self, config=self.config, state=_state, active=active
                    )
                    self.__registry.append(entry)
                    self.list_states.append(entry)

                def callback(result, error=False):
                    self.status_page.set_visible(not result.status)
                    self.pref_page.set_visible(result.status)
                    self.list_states.set_visible(result.status)
                    self.list_states.set_sensitive(result.status)

                def process_states():
                    GLib.idle_add(self.empty_list)

                    if len(_states) == 0:
                        return Result(False)

                    for state in _states.items():
                        _is_active = str(_active).startswith(str(state[0])) or str(state[0]).startswith(str(_active))
                        GLib.idle_add(new_state, state, _is_active)

                    return Result(True)

                RunAsync(process_states, callback)
            _apply()

        if states is None:
            def _fetch():
                res = self.versioning_manager.list_states(config, check_dirty=False)
                if not self.versioning_manager.needs_migration(config):
                    _act = res.data.get("state_id")
                    _sts = res.data.get("states")
                    _brs = res.data.get("branches", [])
                    _act_br = res.data.get("active_branch", "")
                    _changed_files = res.data.get("changed_files", 0)
                else:
                    _sts = res
                    _act = active
                    _brs = []
                    _act_br = ""
                    _changed_files = 0
                return _sts, _act, _brs, _act_br, False, _changed_files
                
            def _on_fetched(result, error):
                if not error and result:
                    _do_update(result[0], result[1], result[2], result[3], result[4], result[5])
                else:
                    _do_update({}, active, [], "", False, 0)
                    
            RunAsync(_fetch, _on_fetched)
        else:
            _do_update(states, active, [], "", False, 0)
        
        self._refresh_details_badge()

    def show_add_state_dialog(self, widget):
        dialog = VersioningCommitDialog(parent=self.window, callback=self.add_state)
        dialog.present(self.window)

    def add_state(self, message: str):
        if not message:
            return
        self._set_busy(True, _("Creating snapshot…"))

        @GtkUtils.run_in_main_loop
        def update(result, error):
            self._set_busy(False)
            self.update()
            self._refresh_details_badge()

        RunAsync(
            task_func=self.versioning_manager.create_state,
            callback=update,
            config=self.config,
            message=message,
        )

