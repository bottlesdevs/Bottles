# add.py
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

import re

from gi.repository import Gtk

from bottles.utils import UtilsTerminal, UtilsLogger

logging = UtilsLogger()

@Gtk.Template(resource_path='/com/usebottles/bottles/add-details.ui')
class BottlesAddDetails(Gtk.Box):
    __gtype_name__ = 'BottlesAddDetails'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    label_env_name = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    entry_path = Gtk.Template.Child()
    check_path = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    expander_advanced = Gtk.Template.Child()

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        '''
        Common variables
        '''
        self.window = window
        self.runner = window.runner
        self.environment = self.window.env_active
        self.custom_runner = False

        '''
        Connect signals to widgets
        '''
        self.btn_cancel.connect('pressed', self.show_add_view)
        self.btn_save.connect('pressed', self.create_bottle)
        self.check_path.connect('toggled', self.toggle_entry_path)
        self.entry_name.connect('key-release-event', self.check_entry_name)
        self.combo_runner.connect('changed', self.set_runner)

        '''
        Populate combo_runner with installed runners
        '''
        for runner in self.runner.runners_available:
            self.combo_runner.append(runner, runner)

        self.combo_runner.set_active(0)

    def set_runner(self, widget):
        self.custom_runner = widget.get_active_id()

    '''
    Get selected environment
    if custom show advanced settings
    '''
    def update_environment(self):
        self.expander_advanced.set_visible(False)
        self.environment = self.window.env_active
        if self.environment == "Custom":
            self.custom_runner = self.combo_runner.get_active_id()
            self.expander_advanced.set_visible(True)

    '''
    Check for not allowed characters in entry_name
    '''
    def check_entry_name(self, widget, event_key):
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:.;,]')
        name = widget.get_text()

        if(regex.search(name) == None):
            self.btn_save.set_sensitive(True)
            widget.set_icon_from_icon_name(1, "")
        else:
            self.btn_save.set_sensitive(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")

    def show_add_view(self, widget):
        self.window.stack_main.set_visible_child_name("page_add")

    def create_bottle(self, widget):
        custom_path = self.entry_path.get_text()

        '''
        TODO: Custom bottle paths must be saved to be found when listing bottles
        '''

        self.window.stack_main.set_visible_child_name("page_create")
        self.runner.create_bottle(name=self.entry_name.get_text(),
                                  path=custom_path,
                                  environment=self.window.env_active,
                                  runner=self.custom_runner)

    def toggle_entry_path(self, widget):
        self.entry_path.set_sensitive(widget.get_active())

@Gtk.Template(resource_path='/com/usebottles/bottles/add.ui')
class BottlesAdd(Gtk.Box):
    __gtype_name__ = 'BottlesAdd'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    btn_env_gaming = Gtk.Template.Child()
    btn_env_software = Gtk.Template.Child()
    btn_env_custom = Gtk.Template.Child()
    btn_add_details = Gtk.Template.Child()
    btn_import = Gtk.Template.Child()
    label_env_description = Gtk.Template.Child()

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        '''
        Common variables
        '''
        self.window = window

        '''
        Set default environment
        '''
        self.set_software_env(self.btn_env_software)

        '''
        Connect signals to widgets
        '''
        self.btn_import.connect('pressed', self.window.show_importer_view)
        self.btn_add_details.connect('pressed', self.show_add_details_view)
        self.btn_env_gaming.connect('pressed', self.set_gaming_env)
        self.btn_env_software.connect('pressed', self.set_software_env)
        self.btn_env_custom.connect('pressed', self.set_custom_env)

    def choose_backup(self, widget):
        file_dialog = Gtk.FileChooserDialog("Choose a backup",
                                            self.window,
                                            Gtk.FileChooserAction.OPEN,
                                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                            Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

        '''
        Create filter for each allowed backup extension
        '''
        filter_json = Gtk.FileFilter()
        filter_json.set_name(".json backup")
        filter_json.add_pattern("*.json")

        filter_gz = Gtk.FileFilter()
        filter_gz.set_name(".tar.gz backup")
        filter_gz.add_pattern("*.tag.gz")

        file_dialog.add_filter(filter_json)
        file_dialog.add_filter(filter_gz)

        response = file_dialog.run()

        if response == Gtk.ResponseType.OK:
            print("Backup selected")

        file_dialog.destroy()

    def set_gaming_env(self, widget):
        self.label_env_description.set_text("The gaming environment has everything needed to run modern Windows games on Linux")
        self.window.env_active = self.window.envs[0]
        self.set_active_env(widget)

    def set_software_env(self, widget):
        self.label_env_description.set_text("The software environment includes dependencies commonly used by modern software.")
        self.window.env_active = self.window.envs[1]
        self.set_active_env(widget)

    def set_custom_env(self, widget):
        self.label_env_description.set_text("A clean environment, without any optimization.")
        self.window.env_active = self.window.envs[2]
        self.set_active_env(widget)

    def set_active_env(self, widget):
        '''
        Log the selected environment
        '''
        logging.info("Selected env is: %s" % self.window.env_active)

        '''
        For each environment button, remove the active class and
        set only to the last pressed
        '''
        for w in [self.btn_env_gaming,
                  self.btn_env_software,
                  self.btn_env_custom]:
            w_context = w.get_style_context()
            w_context.remove_class("btn_env_active")

        context = widget.get_style_context()
        context.add_class("btn_env_active")

    def show_add_details_view(self, widget):
        self.window.page_add_details.update_environment()
        self.window.stack_main.set_visible_child_name("page_add_details")
