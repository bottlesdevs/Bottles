# new.py
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

import os
import re
from gettext import gettext as _
from gi.repository import Gtk, Adw

from bottles.dialogs.filechooser import FileChooser  # pyright: reportMissingImports=false
from bottles.utils.threading import RunAsync
from bottles.utils.gtk import GtkUtils

from bottles.backend.runner import Runner
from bottles.backend.wine.executor import WineExecutor


@Gtk.Template(resource_path='/com/usebottles/bottles/new.ui')
class NewView(Adw.Window):
    __gtype_name__ = 'NewView'

    # region Widgets
    entry_name = Gtk.Template.Child()
    stack_create = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    btn_close_pill = Gtk.Template.Child()
    btn_choose_env = Gtk.Template.Child()
    btn_choose_path = Gtk.Template.Child()
    list_envs = Gtk.Template.Child()
    page_create = Gtk.Template.Child()
    page_creating = Gtk.Template.Child()
    created = Gtk.Template.Child()
    switch_versioning = Gtk.Template.Child()
    switch_sandbox = Gtk.Template.Child()
    label_output = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    combo_arch = Gtk.Template.Child()
    row_sandbox = Gtk.Template.Child()
    title = Gtk.Template.Child()
    headerbar = Gtk.Template.Child()
    ev_controller = Gtk.EventControllerKey.new()

    # endregion

    def __init__(self, window, arg_exe=None, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)
        # common variables and references
        self.window = window
        self.manager = window.manager
        self.arg_exe = arg_exe
        self.selected_env = "gaming"
        self.env_recipe_path = None
        self.new_bottle_config = {}
        self.custom_path = ""
        self.runner = None

        # connect signals
        self.entry_name.add_controller(self.ev_controller)
        self.btn_cancel.connect("clicked", self.__close_window)
        self.btn_close.connect("clicked", self.__close_window)
        self.btn_close_pill.connect("clicked", self.__close_window)
        self.btn_create.connect("clicked", self.create_bottle)
        self.btn_choose_env.connect("clicked", self.choose_env_recipe)
        self.btn_choose_path.connect("clicked", self.choose_path)
        self.list_envs.connect('row-selected', self.set_active_env)
        self.ev_controller.connect("key-released", self.__check_entry_name)

        # populate combo_runner with runner versions from the manager
        for runner in self.manager.runners_available:
            self.combo_runner.append(runner, runner)

        rc = [i for i in self.manager.runners_available if i.startswith('caffe')]
        rv = [i for i in self.manager.runners_available if i.startswith('vaniglia')]
        rl = [i for i in self.manager.runners_available if i.startswith('lutris')]
        rs = [i for i in self.manager.runners_available if i.startswith('sys-')]

        if len(rc) > 0:  # use the latest from caffe
            self.runner = rc[0]
        elif len(rv) > 0:  # use the latest from vaniglia
            self.runner = rv[0]
        elif len(rl) > 0:  # use the latest from lutris
            self.runner = rl[0]
        elif len(rs) > 0:  # use the latest from system
            self.runner = rs[0]
        else:  # use any other runner available
            self.runner = self.manager.runners_available[0]

        self.combo_runner.set_active_id(self.runner)
        self.combo_arch.set_selected(0)

        # if running under Flatpak, hide row_sandbox
        if "FLATPAK_ID" in os.environ:
            self.row_sandbox.set_visible(False)

        # focus on the entry_name
        self.entry_name.grab_focus()

        # select first row
        self.list_envs.select_row(self.list_envs.get_first_child())

    def set_active_env(self, widget, row):
        """
        This function set the active environment on row selection.
        """
        self.selected_env = row.get_buildable_id()

    def __check_entry_name(self, *args):
        result = GtkUtils.validate_entry(self.entry_name)
        self.btn_create.set_sensitive(result)

    def choose_env_recipe(self, *args):
        def set_path(_dialog, response, _file_dialog):
            if response == -3:
                _file = _file_dialog.get_file()
                self.env_recipe_path = _file.get_path()

        FileChooser(
            parent=self.window,
            title=_("Choose a recipe file"),
            action=Gtk.FileChooserAction.OPEN,
            buttons=(_("Cancel"), _("Select")),
            filters=["yml"],
            callback=set_path
        )

    def choose_path(self, *args):
        def set_path(_dialog, response, _file_dialog):
            if response == Gtk.ResponseType.OK:
                _file = _file_dialog.get_file()
                self.custom_path = _file.get_path()
            _file_dialog.destroy()

        FileChooser(
            parent=self.window,
            title=_("Choose where to store the bottle"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=(_("Cancel"), _("Select")),
            native=False,
            callback=set_path
        )

    def create_bottle(self, *args):
        # set widgets states
        self.btn_cancel.set_visible(False)
        self.btn_create.set_visible(False)
        self.page_create.set_visible(False)
        self.title.set_visible(False)
        self.headerbar.add_css_class("flat")
        self.stack_create.set_visible_child_name("page_creating")

        # avoid giant/empty window
        self.set_default_size(450, 430)

        versioning_state = self.switch_versioning.get_state()
        sandbox_state = self.switch_sandbox.get_state()
        if self.selected_env == "Custom":
            self.runner = self.combo_runner.get_active_id()

        if self.combo_arch.get_selected() == 0:
            arch = "win64"
        else:
            arch = "win32"

        RunAsync(
            task_func=self.manager.create_bottle,
            callback=self.finish,
            name=self.entry_name.get_text(),
            path=self.custom_path,
            environment=self.selected_env,
            runner=self.runner,
            arch=arch,
            dxvk=self.manager.dxvk_available[0],
            versioning=versioning_state,
            sandbox=sandbox_state,
            fn_logger=self.update_output,
            custom_environment=self.env_recipe_path
        )

    def update_output(self, text):
        """
        This function update the label_output with the given text.
        It will be concatenated with the previous one.
        """
        current_text = self.label_output.get_text()
        text = f"{current_text}{text}\n"
        self.label_output.set_text(text)

    def finish(self, result, error=None):
        if not result or not result.status or error:
            self.update_output(_("There was an error creating the bottle."))
            self.btn_cancel.set_visible(False)
            self.btn_close.set_visible(True)
            self.headerbar.remove_css_class("flat")
            return

        self.new_bottle_config = result.data.get("config")
        self.created.set_description(
            _("A bottle named “{0}” was created successfully").format(
                self.entry_name.get_text()
            )
        )
        self.btn_cancel.set_visible(False)
        self.stack_create.set_visible_child_name("page_created")

        '''
        Ask the manager to check for new bottles, then update the
        user bottles list. 
        '''
        self.manager.check_bottles()
        self.window.page_list.update_bottles()

    def __close_window(self, *args):
        """
        This function check if an executable was passed to Bottles as
        a command line argument. If so, it will be launched in the new
        bottles and will close the bottle creation dialog. If there is
        no arguments, it will simply close the dialog.
        """
        if self.arg_exe:
            executor = WineExecutor(
                self.new_bottle_config,
                exec_path=self.arg_exe
            )
            RunAsync(executor.run)

        self.destroy()
