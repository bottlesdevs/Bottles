# program.py
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
import webbrowser
from gi.repository import Gtk, Handy

from ..utils import RunAsync
from ..dialogs.launchoptions import LaunchOptionsDialog
from ..backend.runner import Runner
from ..backend.manager_utils import ManagerUtils


@Gtk.Template(resource_path='/com/usebottles/bottles/program-entry.ui')
class ProgramEntry(Handy.ActionRow):
    __gtype_name__ = 'ProgramEntry'

    # region Widgets
    btn_run = Gtk.Template.Child()
    btn_winehq = Gtk.Template.Child()
    btn_protondb = Gtk.Template.Child()
    btn_forum = Gtk.Template.Child()
    btn_issues = Gtk.Template.Child()
    btn_launch_options = Gtk.Template.Child()
    btn_uninstall = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_add_entry = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, program, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.view_programs = window.page_details.view_programs
        self.view_bottle = window.page_details.view_bottle
        self.manager = window.manager
        self.config = config
        self.arguments = ""
        self.program_name = program[0]
        self.program_executable = program[1].split("\\")[-1]
        self.program_executable_path = program[1]
        self.program_folder = program[3]

        # populate widgets
        self.set_title(self.program_name)
        self.set_icon_name(program[2])

        if "FLATPAK_ID" in os.environ:
            '''
            Disable the btn_add_entry button since the flatpak has no access
            to the user .loocal directory, so the entry cannot be created.
            '''
            self.btn_add_entry.set_visible(False)

        if self.program_name not in self.config["External_Programs"]:
            # hide remove button if program is not added by user
            self.btn_remove.set_visible(False)

        '''Signal connections'''
        self.btn_run.connect('pressed', self.run_executable)
        self.btn_winehq.connect('pressed', self.open_search_url, "winehq")
        self.btn_protondb.connect('pressed', self.open_search_url, "protondb")
        self.btn_forum.connect('pressed', self.open_search_url, "forum")
        self.btn_issues.connect('pressed', self.open_search_url, "issues")
        self.btn_launch_options.connect(
            'pressed', self.show_launch_options_view)
        self.btn_uninstall.connect('pressed', self.uninstall_program)
        self.btn_remove.connect('pressed', self.remove_program)
        self.btn_browse.connect('pressed', self.browse_program_folder)
        self.btn_add_entry.connect('pressed', self.add_entry)

        '''Populate entry_arguments by config'''
        if self.program_executable in self.config["Programs"]:
            self.arguments = self.config["Programs"][self.program_executable]

    '''Show dialog for launch options'''

    def show_launch_options_view(self, widget=False):
        new_window = LaunchOptionsDialog(
            self.window,
            self.config,
            self.program_executable,
            self.arguments
        )
        new_window.present()
        self.update_programs()

    def run_executable(self, widget):
        if self.program_executable in self.config["Programs"]:
            arguments = self.config["Programs"][self.program_executable]
        else:
            arguments = False
        Runner.run_executable(
            self.config,
            self.program_executable_path,
            arguments,
            cwd=self.program_folder
        )

    def update_programs(self, result=False, error=False):
        self.view_programs.update(config=self.config)
        self.view_bottle.update_programs()

    def uninstall_program(self, widget):
        RunAsync(
            task_func=self.manager.remove_program,
            callback=self.update_programs,
            config=self.config,
            program_name=self.program_name
        )

    def remove_program(self, widget):
        self.manager.update_config(
            config=self.config,
            key=self.program_name,
            value=False,
            remove=True,
            scope="External_Programs"
        )
        self.update_programs()

    def browse_program_folder(self, widget):
        ManagerUtils.open_filemanager(
            config=self.config,
            path_type="custom",
            custom_path=self.program_folder
        )
    
    def add_entry(self, widget):
        ManagerUtils.create_desktop_entry(
            config=self.config,
            program={
                "name": self.program_name,
                "executable": self.program_executable
            }
        )

    def open_search_url(self, widget, site):
        query = self.program_name.replace(" ", "+")
        sites = {
            "winehq": f"https://www.winehq.org/search?q={query}",
            "protondb": f"https://www.protondb.com/search?q={query}",
            "forum": f"https://forums.usebottles.com/?q={query}",
            "issues": f"https://github.com/bottlesdevs/Bottles/issues?q=is:issue{query}"
        }
        webbrowser.open_new_tab(sites[site])
