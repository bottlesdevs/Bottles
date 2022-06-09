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

from bottles.backend.runner import Runner  # pyright: reportMissingImports=false
from bottles.backend.wine.executor import WineExecutor
from bottles.utils.threading import RunAsync

@Gtk.Template(resource_path='/com/usebottles/bottles/new.ui')
class NewView(Adw.Window):
    __gtype_name__ = 'NewView'

    # region Widgets
    entry_name = Gtk.Template.Child()
    stack_create = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    btn_choose_env = Gtk.Template.Child()
    btn_choose_path = Gtk.Template.Child()
    #btn_pref_runners = Gtk.Template.Child()
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

        entry_name_ev = Gtk.EventControllerKey.new()
        entry_name_ev.connect("key-pressed", self.check_entry_name)
        self.entry_name.add_controller(entry_name_ev)

        # connect signals
        self.btn_cancel.connect("clicked", self.__close_window)
        self.btn_close.connect("clicked", self.__close_window)
        self.btn_create.connect("clicked", self.create_bottle)
        self.btn_choose_env.connect("clicked", self.choose_env_recipe)
        self.btn_choose_path.connect("clicked", self.choose_path)
        self.list_envs.connect('row-selected', self.set_active_env)
        self.entry_name.connect('activate', self.create_bottle)
        #self.btn_pref_runners.connect("clicked", self.window.show_prefs_view)

        # populate combo_runner with runner versions from the manager
        for runner in self.manager.runners_available:
            self.combo_runner.append(runner, runner)

        self.combo_arch.set_selected(0)

        # if running under Flatpak, hide row_sandbox
        if "FLATPAK_ID" in os.environ:
             self.row_sandbox.set_visible(False)

        # focus on the entry_name
        self.entry_name.grab_focus()

    def set_active_env(self, widget, row):
        """
        This function set the active environment on row selection.
        """
        self.selected_env = row.get_buildable_id()

    def check_entry_name(self, widget, event_key, state=None, data=None):
        """
        This function checks if the name of the bottle is valid. So it
        checks if the name is not empty and if it contains special
        characters. Then it toggles the error style according to the result.
        """
        regex = re.compile('[\\\@!#$%^&*()<>?/|}{~:.;,\'"]')
        name = self.entry_name.get_text()

        if (regex.search(name) is None) and name != "" and not name.isspace():
            self.btn_create.set_sensitive(True)
            self.entry_name.remove_css_class("error")
        else:
            self.btn_create.set_sensitive(False)
            self.entry_name.add_css_class("error")

    def choose_env_recipe(self, widget):
        file_dialog = Gtk.FileChooserNative.new(
            _("Choose a recipe file"),
            self.window,
            Gtk.FileChooserAction.OPEN
        )

        filter_yaml = Gtk.FileFilter()
        filter_yaml.set_name(".yml")
        filter_yaml.add_pattern("*yml")
        filter_yaml.add_pattern("*yaml")
        file_dialog.add_filter(filter_yaml)

        response = file_dialog.run()

        if response == -3:
            self.env_recipe_path = file_dialog.get_filename()

        file_dialog.destroy()

    def choose_path(self, widget):
        file_dialog = Gtk.FileChooserDialog(
            _("Choose where to store the bottle"),
            self.window,
            Gtk.FileChooserAction.SELECT_FOLDER,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        )

        response = file_dialog.run()

        if response == Gtk.ResponseType.OK:
            self.custom_path = file_dialog.get_filename()
            print(self.custom_path)

        file_dialog.destroy()

    '''Create the bottle'''

    def create_bottle(self, widget):
        # set widgets states
        self.btn_cancel.set_visible(False)
        self.btn_create.set_visible(False)
        self.page_create.set_visible(False)
        self.title.set_visible(False)
        self.headerbar.get_style_context().add_class("flat")
        self.stack_create.set_visible_child_name("page_creating")

        '''
        Check if versioning and sandbox are enabled and get the selected runner. 
        If the selected env. is not "Custom", the runner is taken from the
        runners available list, else it is taken from the user selection.
        '''
        versioning_state = self.switch_versioning.get_state()
        sandbox_state = self.switch_sandbox.get_state()
        if self.selected_env == "Custom":
            runner = self.combo_runner.get_active_id()
        else:
            rc = [
                i for i in self.manager.runners_available if i.startswith('caffe')
            ]
            rv = [
                i for i in self.manager.runners_available if i.startswith('vaniglia')
            ]
            rl = [
                i for i in self.manager.runners_available if i.startswith('lutris')
            ]
            rs = [
                i for i in self.manager.runners_available if i.startswith('sys-')
            ]

            if len(rc) > 0:  # use the latest from caffe
                runner = rc[0]
            elif len(rv) > 0:  # use the latest from vaniglia
                runner = rv[0]
            elif len(rl) > 0:  # use the latest from lutris
                runner = rl[0]
            elif len(rs) > 0:  # use the latest from system
                runner = rs[0]
            else:  # use any other runner available
                runner = self.manager.runners_available[0]

        if self.combo_arch == 0:
            arch = "win64"
        else:
            arch = "win32"

        RunAsync(
            task_func=self.manager.create_bottle,
            callback=self.finish,
            name=self.entry_name.get_text(),
            path=self.custom_path,
            environment=self.selected_env,
            runner=runner,
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
        if result is None or error is not None:
            self.update_output(_("There was an error creating the bottle."))
            self.btn_cancel.set_visible(False)
            self.btn_close.set_visible(True)
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

    def __close_window(self, widget):
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
