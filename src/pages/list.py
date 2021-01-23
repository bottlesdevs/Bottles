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

import logging
from gi.repository import Gtk, Handy

from .dialog import BottlesMessageDialog
from bottles.empty import BottlesEmpty

@Gtk.Template(resource_path='/com/usebottles/bottles/list-entry.ui')
class BottlesListEntry(Handy.ActionRow):
    __gtype_name__ = 'BottlesListEntry'

    Handy.init()

    '''Get widgets from template'''
    btn_details = Gtk.Template.Child()
    btn_delete = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_run = Gtk.Template.Child()
    btn_upgrade = Gtk.Template.Child()
    btn_repair = Gtk.Template.Child()
    btn_programs = Gtk.Template.Child()
    btn_run_executable = Gtk.Template.Child()
    label_environment = Gtk.Template.Child()
    label_state = Gtk.Template.Child()
    icon_damaged = Gtk.Template.Child()
    grid_versioning = Gtk.Template.Child()

    def __init__(self, window, configuration, arg_executable, **kwargs):
        super().__init__(**kwargs)

        '''Init template'''
        self.init_template()

        '''Common variables'''
        self.window = window
        self.runner = window.runner
        self.configuration = configuration[1]
        self.label_environment_context = self.label_environment.get_style_context()
        self.arg_executable = arg_executable

        '''Check runner type by name'''
        if self.configuration.get("Runner").startswith("lutris"):
            self.runner_type = "wine"
        else:
            self.runner_type = "proton"

        '''Signal connections'''
        self.btn_details.connect('pressed', self.show_details)
        self.btn_details.connect('activate', self.show_details)
        self.btn_delete.connect('pressed', self.confirm_delete)
        self.btn_upgrade.connect('pressed', self.upgrade_runner)
        self.btn_run.connect('pressed', self.run_executable)
        self.btn_browse.connect('pressed', self.run_browse)
        self.btn_repair.connect('pressed', self.repair)
        self.btn_run_executable.connect('pressed', self.run_executable)

        '''Populate widgets'''
        self.grid_versioning.set_visible(self.configuration.get("Versioning"))
        self.label_state.set_text(str(self.configuration.get("State")))
        self.set_title(self.configuration.get("Name"))
        self.label_environment.set_text(self.configuration.get("Environment"))
        self.label_environment_context.add_class(
            "tag-%s" % self.configuration.get("Environment").lower())

        '''Toggle btn_upgrade'''
        if self.configuration.get("Runner") != self.runner.get_latest_runner(self.runner_type):
            self.btn_upgrade.set_visible(True)

        '''If configuration is broken'''
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
            '''Check for arguments from configuration'''
            if self.arg_executable:
                logging.info(
                    _("Arguments found for executable: [{executable}].").format(
                        executable = self.arg_executable))

                for w in [self.btn_details,
                          self.btn_upgrade,
                          self.btn_run,
                          self.btn_browse,
                          self.btn_programs,
                          self.btn_delete]:
                    w.set_visible(False)
                self.btn_run_executable.set_visible(True)

    '''Repair bottle'''
    def repair(self, widget):
        self.runner.repair_bottle(self.configuration)

    '''Display file dialog for executable'''
    def run_executable(self, widget):
        if not self.arg_executable:
            '''If executable is not Bottles argument'''
            file_dialog = Gtk.FileChooserDialog(_("Choose a Windows executable file"),
                                                self.window,
                                                Gtk.FileChooserAction.OPEN,
                                                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                                Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

            '''Create filters for allowed extensions'''
            filter_exe = Gtk.FileFilter()
            filter_exe.set_name(".exe")
            filter_exe.add_pattern("*.exe")

            filter_msi = Gtk.FileFilter()
            filter_msi.set_name(".msi")
            filter_msi.add_pattern("*.msi")

            filter_bat = Gtk.FileFilter()
            filter_bat.set_name(".bat")
            filter_bat.add_pattern("*.bat")

            file_dialog.add_filter(filter_exe)
            file_dialog.add_filter(filter_msi)
            file_dialog.add_filter(filter_bat)

            response = file_dialog.run()

            if response == Gtk.ResponseType.OK:
                self.runner.run_executable(self.configuration,
                                           file_dialog.get_filename())

            file_dialog.destroy()
        else:
            '''Use executable provided as bottles argument'''
            self.runner.run_executable(self.configuration, self.arg_executable)
            self.arg_executable = False
            self.runner.update_bottles()

    '''Browse bottle drive_c files'''
    def run_browse(self, widget):
        self.runner.open_filemanager(self.configuration)

    '''Show dialog to confirm runner upgrade'''
    def upgrade_runner(self, widget):
        dialog_upgrade = BottlesMessageDialog(
            parent=self.window,
            title=_("Confirm upgrade"),
            message=_("This will change the runner from {0} to {1}.").format(
                self.configuration.get("Runner"),
                self.runner.get_latest_runner(self.runner_type)))
        response = dialog_upgrade.run()

        if response == Gtk.ResponseType.OK:
            self.runner.update_configuration(self.configuration,
                                             "Runner",
                                             self.runner.get_latest_runner())
            self.btn_upgrade.set_visible(False)

        dialog_upgrade.destroy()

    '''Show details page'''
    def show_details(self, widget):
        self.window.show_details_view(configuration=self.configuration)

    '''Show dialog to confirm bottle deletion'''
    def confirm_delete(self, widget):
        dialog_delete = BottlesMessageDialog(parent=self.window,
                                      title=_("Confirm deletion"),
                                      message=_("Are you sure you want to delete this Bottle and all files?"))
        response = dialog_delete.run()

        if response == Gtk.ResponseType.OK:
            self.runner.delete_bottle(self.configuration)
            self.destroy()

        dialog_delete.destroy()


@Gtk.Template(resource_path='/com/usebottles/bottles/list.ui')
class BottlesList(Gtk.Box):
    __gtype_name__ = 'BottlesList'

    '''Get widgets from template'''
    list_bottles = Gtk.Template.Child()
    clamp_list = Gtk.Template.Child()
    grid_empty = Gtk.Template.Child()

    def __init__(self, window, arg_executable, **kwargs):
        super().__init__(**kwargs)

        '''Init template'''
        self.init_template()

        '''Common variables'''
        self.window = window
        self.arg_executable = arg_executable

        '''Populate list_bottles'''
        self.update_bottles()

    '''Find and append bottles to list_bottles'''
    def update_bottles(self):
        for bottle in self.list_bottles.get_children():
            bottle.destroy()

        bottles = self.window.runner.local_bottles.items()

        if len(bottles) == 0:
            self.clamp_list.set_visible(False)
            self.grid_empty.set_visible(True)
        else:
            self.clamp_list.set_visible(True)
            self.grid_empty.set_visible(False)

        for bottle in bottles:
            self.list_bottles.add(BottlesListEntry(self.window,
                                                   bottle,
                                                   self.arg_executable))
        self.arg_executable = False
