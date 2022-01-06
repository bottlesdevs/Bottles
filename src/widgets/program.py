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
from gi.repository import Gtk, GLib, Handy

from ..utils import RunAsync
from ..dialogs.launchoptions import LaunchOptionsDialog
from ..dialogs.rename import RenameDialog
from ..backend.runner import Runner
from ..backend.manager_utils import ManagerUtils


@Gtk.Template(resource_path='/com/usebottles/bottles/program-entry.ui')
class ProgramEntry(Handy.ActionRow):
    __gtype_name__ = 'ProgramEntry'

    # region Widgets
    btn_run = Gtk.Template.Child()
    btn_stop = Gtk.Template.Child()
    btn_winehq = Gtk.Template.Child()
    btn_protondb = Gtk.Template.Child()
    btn_forum = Gtk.Template.Child()
    btn_issues = Gtk.Template.Child()
    btn_launch_options = Gtk.Template.Child()
    btn_uninstall = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_rename = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_add_entry = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, program, is_layer=False, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.view_programs = window.page_details.view_programs
        self.view_bottle = window.page_details.view_bottle
        self.manager = window.manager
        self.config = config
        self.arguments = ""
        self.program = program
        self.is_layer = is_layer
        
        # populate widgets
        self.set_title(self.program["name"])
        self.set_icon_name(program["icon"])

        if "FLATPAK_ID" in os.environ:
            '''
            Disable the btn_add_entry button since the flatpak has no access
            to the user .loocal directory, so the entry cannot be created.
            '''
            self.btn_add_entry.set_visible(False)

        if self.program["name"] not in self.config["External_Programs"]:
            # hide remove button if program is not added by user
            self.btn_remove.set_visible(False)

        '''Signal connections'''
        self.btn_run.connect("pressed", self.run_executable)
        self.btn_stop.connect("pressed", self.stop_process)
        self.btn_winehq.connect("pressed", self.open_search_url, "winehq")
        self.btn_protondb.connect("pressed", self.open_search_url, "protondb")
        self.btn_forum.connect("pressed", self.open_search_url, "forum")
        self.btn_issues.connect("pressed", self.open_search_url, "issues")
        self.btn_launch_options.connect(
            "pressed", self.show_launch_options_view)
        self.btn_uninstall.connect("pressed", self.uninstall_program)
        self.btn_remove.connect("pressed", self.remove_program)
        self.btn_rename.connect("pressed", self.rename_program)
        self.btn_browse.connect("pressed", self.browse_program_folder)
        self.btn_add_entry.connect("pressed", self.add_entry)

        '''
        Populate entry_arguments by config
        TODO: improve this without taking executable by path
        '''
        if not is_layer:
            _executable = self.program["path"].split("\\")[-1] # win path
            if len(_executable) == 0:
                _executable = self.program["path"].split("/")[-1] # unix path
            if _executable in self.config["Programs"]:
                self.arguments = self.config["Programs"][_executable]
        else:
            _executable = self.program["exec_name"]
            self.arguments = self.program["exec_args"]
        self.executable = _executable

        self.__is_alive()

    '''Show dialog for launch options'''

    def show_launch_options_view(self, widget=False):
        new_window = LaunchOptionsDialog(
            self.window,
            self.config,
            self.executable,
            self.arguments
        )
        new_window.present()
        self.update_programs()

    def __reset_buttons(self, result=False, error=False):
        status = False
        if result:
            status = result
            if not isinstance(result, bool):
                status = result.status
        self.btn_run.set_visible(status)
        self.btn_stop.set_visible(not status)
    
    def __is_alive(self):
        def set_watcher(result=False, error=False):
            self.__reset_buttons()
            RunAsync(
                Runner.wait_for_process,
                callback=self.__reset_buttons,
                config=self.config,
                name=self.executable,
                timeout=5
            )

        RunAsync(
            Runner.is_process_alive,
            callback=set_watcher,
            config=self.config,
            name=self.executable
        )

    def run_executable(self, widget):
        if self.is_layer:
            RunAsync(
                self.manager.launch_layer_program,
                callback=self.__reset_buttons,
                config=self.config, 
                layer=self.program
            )
        else:
            RunAsync(
                Runner.run_executable,
                callback=self.__reset_buttons,
                config=self.config,
                file_path=self.program["path"],
                arguments=self.arguments,
                cwd=self.program["folder"],
                no_async=True
            )
        self.__reset_buttons()
    
    def stop_process(self, widget):
        Runner.kill_process(self.config, name=self.executable)
        self.__reset_buttons(True)

    def update_programs(self, result=False, error=False):
        GLib.idle_add(self.view_programs.update, config=self.config)
        GLib.idle_add(self.view_bottle.update_programs)

    def uninstall_program(self, widget):
        RunAsync(
            task_func=self.manager.remove_program,
            callback=self.update_programs,
            config=self.config,
            program_name=self.program["name"]
        )

    def remove_program(self, widget=None, update=True):
        self.manager.update_config(
            config=self.config,
            key=self.program["executable"],
            value=False,
            remove=True,
            scope="External_Programs"
        )
        if update:
            self.update_programs()

    def rename_program(self, widget):
        def func(new_name):
            self.program["name"] = new_name
            self.manager.update_config(
                config=self.config,
                key=self.program["executable"],
                value=self.program,
                scope="External_Programs"
            )
            self.update_programs()
        
        RenameDialog(self.window, on_save=func, name=self.program["name"])

    def browse_program_folder(self, widget):
        ManagerUtils.open_filemanager(
            config=self.config,
            path_type="custom",
            custom_path=self.program["folder"]
        )
    
    def add_entry(self, widget):
        ManagerUtils.create_desktop_entry(
            config=self.config,
            program={
                "name": self.program["name"],
                "executable": self.program["executable"]
            }
        )

    def open_search_url(self, widget, site):
        query = self.program["name"].replace(" ", "+")
        sites = {
            "winehq": f"https://www.winehq.org/search?q={query}",
            "protondb": f"https://www.protondb.com/search?q={query}",
            "forum": f"https://forums.usebottles.com/?q={query}",
            "issues": f"https://github.com/bottlesdevs/Bottles/issues?q=is:issue{query}"
        }
        webbrowser.open_new_tab(sites[site])
