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
from datetime import datetime
from gi.repository import Gtk, GLib, Handy

from ..backend.runner import Runner

@Gtk.Template(resource_path='/com/usebottles/bottles/list-entry.ui')
class ListViewEntry(Handy.ActionRow):
    __gtype_name__ = 'ListViewEntry'

    Handy.init()

    # region Widgets
    btn_details = Gtk.Template.Child()
    btn_run = Gtk.Template.Child()
    btn_repair = Gtk.Template.Child()
    btn_run_executable = Gtk.Template.Child()
    label_environment = Gtk.Template.Child()
    label_state = Gtk.Template.Child()
    icon_damaged = Gtk.Template.Child()
    grid_versioning = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, arg_exe, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config[1]
        self.label_environment_context = self.label_environment.get_style_context()
        self.arg_exe = arg_exe

        '''Format update date'''
        update_date = _("N/A")
        if self.config.get("Update_Date"):
            try:
                update_date = datetime.strptime(self.config.get("Update_Date"), "%Y-%m-%d %H:%M:%S.%f")
                update_date = update_date.strftime("%b %d %Y %H:%M:%S")
            except ValueError:
                update_date = _("N/A")

        '''Check runner type by name'''
        if self.config.get("Runner").startswith("lutris"):
            self.runner_type = "wine"
        else:
            self.runner_type = "proton"

        # connect signals
        self.btn_details.connect('pressed', self.show_details)
        self.btn_details.connect('activate', self.show_details)
        self.btn_run.connect('pressed', self.run_executable)
        self.btn_repair.connect('pressed', self.repair)
        self.btn_run_executable.connect('pressed', self.run_executable)

        '''Populate widgets'''
        self.grid_versioning.set_visible(self.config.get("Versioning"))
        self.label_state.set_text(str(self.config.get("State")))
        self.set_title(self.config.get("Name"))
        if self.window.settings.get_boolean("update-date"):
            self.set_subtitle(update_date)
        self.label_environment.set_text(_(self.config.get("Environment")))
        self.label_environment_context.add_class(
            "tag-%s" % self.config.get("Environment").lower())

        '''If config is broken'''
        if self.config.get("Broken"):
            for w in [self.btn_repair,self.icon_damaged]:
                w.set_visible(True)

            for w in [self.btn_details, self.btn_run]:
                w.set_sensitive(False)
        else:
            '''Check for arguments from config'''
            if self.arg_exe:
                logging.info(
                    _("Arguments found for executable: [{executable}].").format(
                        executable = self.arg_exe))

                for w in [self.btn_details, self.btn_run]:
                    w.set_visible(False)
                self.btn_run_executable.set_visible(True)

    '''Repair bottle'''
    def repair(self, widget):
        self.manager.repair_bottle(self.config)

    '''Display file dialog for executable'''
    def run_executable(self, widget):
        if not self.arg_exe:
            '''If executable is not Bottles argument'''
            file_dialog = Gtk.FileChooserNative.new(
                _("Choose a Windows executable file"),
                self.window,
                Gtk.FileChooserAction.OPEN,
                _("Run"),
                _("Cancel")
            )

            response = file_dialog.run()

            if response == -3:
                Runner().run_executable(self.config,
                                           file_dialog.get_filename())

            file_dialog.destroy()
        else:
            '''Use executable provided as bottles argument'''
            Runner().run_executable(self.config, self.arg_exe)
            if self.window.settings.get_boolean("auto-close-bottles"):
                self.window.proper_close()
            self.arg_exe = False
            self.manager.update_bottles()

    '''Show details page'''
    def show_details(self, widget):
        self.window.page_details.update_combo_components()
        self.window.show_details_view(config=self.config)

@Gtk.Template(resource_path='/com/usebottles/bottles/list.ui')
class ListView(Gtk.Box):
    __gtype_name__ = 'ListView'

    # region Widgets
    list_bottles = Gtk.Template.Child()
    clamp_list = Gtk.Template.Child()
    hdy_status = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()
    # endregion

    def __init__(self, window, arg_exe, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.arg_exe = arg_exe

        '''Connect signals'''
        self.btn_create.connect("pressed", self.window.show_add_view)

        '''Populate list_bottles'''
        self.update_bottles()

    '''Find and append bottles to list_bottles'''
    def idle_update_bottles(self):
        for bottle in self.list_bottles.get_children():
            bottle.destroy()

        bottles = self.window.manager.local_bottles.items()

        if len(bottles) == 0:
            self.clamp_list.set_visible(False)
            self.hdy_status.set_visible(True)
        else:
            self.clamp_list.set_visible(True)
            self.hdy_status.set_visible(False)

        for bottle in bottles:
            self.list_bottles.add(ListViewEntry(self.window,
                                                   bottle,
                                                   self.arg_exe))
        self.arg_exe = False

    def update_bottles(self):
        GLib.idle_add(self.idle_update_bottles)
