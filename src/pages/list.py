# list.py
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

from gi.repository import Gtk

import logging

'''
Set the default logging level
'''
logging.basicConfig(level=logging.DEBUG)

from .dialog import BottlesDialog

@Gtk.Template(resource_path='/pm/mirko/bottles/list-entry.ui')
class BottlesListEntry(Gtk.Box):
    __gtype_name__ = 'BottlesListEntry'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    btn_details = Gtk.Template.Child()
    btn_delete = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_run = Gtk.Template.Child()
    btn_backup = Gtk.Template.Child()
    btn_upgrade = Gtk.Template.Child()
    btn_repair = Gtk.Template.Child()
    btn_programs = Gtk.Template.Child()
    btn_run_executable = Gtk.Template.Child()
    label_name = Gtk.Template.Child()
    label_environment = Gtk.Template.Child()
    icon_damaged = Gtk.Template.Child()

    def __init__(self, window, configuration, arg_executable, **kwargs):
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
        self.configuration = configuration[1]
        self.label_environment_context = self.label_environment.get_style_context()
        self.arg_executable = arg_executable

        '''
        Check runner type by name
        '''
        if self.configuration.get("Runner").startswith("lutris"):
            self.runner_type = "wine"
        else:
            self.runner_type = "proton"

        '''
        Connect signals to widgets
        '''
        self.btn_details.connect('pressed', self.show_details)
        self.btn_delete.connect('pressed', self.confirm_delete)
        self.btn_upgrade.connect('pressed', self.upgrade_runner)
        self.btn_run.connect('pressed', self.run_executable)
        self.btn_browse.connect('pressed', self.run_browse)
        self.btn_repair.connect('pressed', self.repair)
        self.btn_programs.connect('pressed', self.show_programs_detail_view)
        self.btn_run_executable.connect('pressed', self.run_executable)

        '''
        Populate widgets with data
        '''
        self.label_name.set_text(self.configuration.get("Name"))
        self.label_environment.set_text(self.configuration.get("Environment"))
        self.label_environment_context.add_class(
            "tag-%s" % self.configuration.get("Environment").lower())

        if self.configuration.get("Runner") != self.runner.get_latest_runner(self.runner_type):
            self.btn_upgrade.set_visible(True)

        if self.configuration.get("Broken"):
            for w in [self.btn_repair,self.icon_damaged]:
                w.set_visible(True)

            for w in [self.btn_details,
                      self.btn_upgrade,
                      self.btn_run,
                      self.btn_browse,
                      self.btn_programs]:
                w.set_sensitive(False)
        else:
            '''
            Check for executable provided as argument
            '''
            if self.arg_executable:
                logging.info("Found executable `%s` provided as argument." % self.arg_executable)

                for w in [self.btn_details,
                          self.btn_upgrade,
                          self.btn_run,
                          self.btn_browse,
                          self.btn_programs,
                          self.btn_delete,
                          self.btn_backup]:
                    w.set_visible(False)
                self.btn_run_executable.set_visible(True)

    def repair(self, widget):
        self.runner.repair_bottle(self.configuration)

    def show_programs_detail_view(self, widget):
        self.show_details(widget, 3)

    '''
    Show a file chooser dialog to choose and run a Windows executable
    '''
    def run_executable(self, widget):
        if not self.arg_executable:
            '''
            If not executable founded as argument, choose from files
            '''
            file_dialog = Gtk.FileChooserDialog("Choose a Windows executable file",
                                                self.window,
                                                Gtk.FileChooserAction.OPEN,
                                                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                                Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

            '''
            Create filter for each allowed file extension
            '''
            filter_exe = Gtk.FileFilter()
            filter_exe.set_name(".exe")
            filter_exe.add_pattern("*.exe")

            filter_msi = Gtk.FileFilter()
            filter_msi.set_name(".msi")
            filter_msi.add_pattern("*.msi")

            file_dialog.add_filter(filter_exe)
            file_dialog.add_filter(filter_msi)

            response = file_dialog.run()

            if response == Gtk.ResponseType.OK:
                self.runner.run_executable(self.configuration,
                                           file_dialog.get_filename())

            file_dialog.destroy()
        else:
            '''
            Else use the one provided
            '''
            self.runner.run_executable(self.configuration, self.arg_executable)
            self.arg_executable = False
            self.window.page_list.update_bottles()

    def run_browse(self, widget):
        self.runner.open_filemanager(self.configuration)

    '''
    Show a confirm dialog to update bottle runner with the latest
    '''
    def upgrade_runner(self, widget):
        dialog_upgrade = BottlesDialog(parent=self.window,
                                      title="Confirm upgrade",
                                      message="This will change the runner from `%s` to `%s`." % (
                                          self.configuration.get("Runner"),
                                          self.runner.get_latest_runner()))
        response = dialog_upgrade.run()

        if response == Gtk.ResponseType.OK:
            logging.info("OK status received")
            self.runner.update_configuration(self.configuration,
                                             "Runner",
                                             self.runner.get_latest_runner())
            self.btn_upgrade.set_visible(False)
        else:
            logging.info("Cancel status received")

        dialog_upgrade.destroy()

    def show_details(self, widget, page=0):
        if page > 0:
            self.window.page_details.set_page(page)
        self.window.page_details.set_configuration(self.configuration)
        self.window.stack_main.set_visible_child_name("page_details")

    '''
    Show a confirm dialog to remove bottle and destroy the widget
    '''
    def confirm_delete(self, widget):
        dialog_delete = BottlesDialog(parent=self.window,
                                      title="Confirm deletion",
                                      message="Are you sure you want to delete this Bottle and all files?")
        response = dialog_delete.run()

        if response == Gtk.ResponseType.OK:
            logging.info("OK status received")
            self.runner.delete_bottle(self.configuration)
            self.destroy()
        else:
            logging.info("Cancel status received")

        dialog_delete.destroy()


@Gtk.Template(resource_path='/pm/mirko/bottles/list.ui')
class BottlesList(Gtk.ScrolledWindow):
    __gtype_name__ = 'BottlesList'

    '''
    Get and assign widgets to variables from
    template childs
    '''
    list_bottles = Gtk.Template.Child()

    def __init__(self, window, arg_executable, **kwargs):
        super().__init__(**kwargs)

        '''
        Initialize template
        '''
        self.init_template()

        '''
        Common variables
        '''
        self.window = window
        self.arg_executable = arg_executable

        '''
        Run methods
        '''
        self.update_bottles()

    '''
    Add bottles to the list_bottles
    '''
    def update_bottles(self):
        for bottle in self.list_bottles.get_children():
            bottle.destroy()

        for bottle in self.window.runner.local_bottles.items():
            self.list_bottles.add(BottlesListEntry(self.window,
                                                   bottle,
                                                   self.arg_executable))
        self.arg_executable = False
