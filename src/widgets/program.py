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

from bottles.utils.threading import RunAsync  # pyright: reportMissingImports=false

from bottles.dialogs.launchoptions import LaunchOptionsDialog
from bottles.dialogs.rename import RenameDialog

from bottles.backend.globals import user_apps_dir
from bottles.backend.managers.steam import SteamManager
from bottles.backend.managers.library import LibraryManager

from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.executor import WineExecutor


# noinspection PyUnusedLocal
@Gtk.Template(resource_path='/com/usebottles/bottles/program-entry.ui')
class ProgramEntry(Handy.ActionRow):
    __gtype_name__ = 'ProgramEntry'

    # region Widgets
    sep = Gtk.Template.Child()
    btn_menu = Gtk.Template.Child()
    btn_run = Gtk.Template.Child()
    btn_stop = Gtk.Template.Child()
    btn_winehq = Gtk.Template.Child()
    btn_protondb = Gtk.Template.Child()
    btn_forum = Gtk.Template.Child()
    btn_launch_options = Gtk.Template.Child()
    btn_launch_steam = Gtk.Template.Child()
    btn_uninstall = Gtk.Template.Child()
    btn_hide = Gtk.Template.Child()
    btn_unhide = Gtk.Template.Child()
    btn_rename = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_add_entry = Gtk.Template.Child()
    btn_add_library = Gtk.Template.Child()
    btn_launch_terminal = Gtk.Template.Child()

    # endregion

    def __init__(self, window, config, program, is_layer=False, is_steam=False, check_boot=True, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.page_details = window.page_details
        self.manager = window.manager
        self.config = config
        self.program = program
        self.is_layer = is_layer

        self.set_title(self.program["name"])
        self.set_icon_name(program.get("icon", ""))

        if is_layer:
            self.executable = program["exec_name"]
        elif is_steam:
            self.set_subtitle(_("This is a Steam application"))
            for w in [
                self.btn_run,
                self.btn_stop,
                self.btn_menu,
                self.sep
            ]:
                w.set_visible(False)
                w.set_sensitive(False)
            self.btn_launch_steam.set_visible(True)
            self.btn_launch_steam.set_sensitive(True)
        else:
            self.executable = program.get("executable", "")

        if program.get("removed"):
            self.get_style_context().add_class("removed")
        self.btn_hide.set_visible(not program.get("removed"))
        self.btn_unhide.set_visible(program.get("removed"))

        if not user_apps_dir:
            '''
            Disable the btn_add_entry button if the user apps dir is
            not accessible.
            '''
            self.btn_add_entry.set_visible(False)

        if window.settings.get_boolean("experiments-library"):
            self.btn_add_library.set_visible(True)

        external_programs = []
        for p in self.config.get("External_Programs"):
            _p = self.config["External_Programs"][p]["name"]
            external_programs.append(_p)

        '''Signal connections'''
        self.btn_run.connect("clicked", self.run_executable)
        self.btn_launch_steam.connect("clicked", self.run_steam)
        self.btn_launch_terminal.connect("clicked", self.run_executable, True)
        self.btn_stop.connect("clicked", self.stop_process)
        self.btn_winehq.connect("clicked", self.open_search_url, "winehq")
        self.btn_protondb.connect("clicked", self.open_search_url, "protondb")
        self.btn_forum.connect("clicked", self.open_search_url, "forum")
        self.btn_launch_options.connect("clicked", self.show_launch_options_view)
        self.btn_uninstall.connect("clicked", self.uninstall_program)
        self.btn_hide.connect("clicked", self.hide_program)
        self.btn_unhide.connect("clicked", self.hide_program)
        self.btn_rename.connect("clicked", self.rename_program)
        self.btn_browse.connect("clicked", self.browse_program_folder)
        self.btn_add_entry.connect("clicked", self.add_entry)
        self.btn_add_library.connect("clicked", self.add_to_library)

        if not program.get("removed") and not is_steam and check_boot:
            self.__is_alive()

    '''Show dialog for launch options'''

    def show_launch_options_view(self, widget=False):
        new_window = LaunchOptionsDialog(
            self.window,
            self.config,
            self.program
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
        winedbg = WineDbg(self.config)

        def set_watcher(result=False, error=False):
            nonlocal winedbg
            self.__reset_buttons()

            RunAsync(
                winedbg.wait_for_process,
                callback=self.__reset_buttons,
                name=self.executable,
                timeout=5
            )

        RunAsync(
            winedbg.is_process_alive,
            callback=set_watcher,
            name=self.executable
        )

    def run_executable(self, widget, with_terminal=False):
        if self.is_layer:
            RunAsync(
                self.manager.launch_layer_program,
                callback=self.__reset_buttons,
                config=self.config,
                layer=self.program
            )
        else:
            executor = WineExecutor(
                self.config,
                exec_path=self.program["path"],
                args=self.program["arguments"],
                cwd=self.program["folder"],
                post_script=self.program.get("script", None),
                terminal=with_terminal
            )
            RunAsync(executor.run, callback=self.__reset_buttons)

        self.__reset_buttons()

    def run_steam(self, widget):
        SteamManager.launch_app(self.config["CompatData"])

    def stop_process(self, widget):
        winedbg = WineDbg(self.config)
        winedbg.kill_process(name=self.executable)
        self.__reset_buttons(True)

    def update_programs(self, result=False, error=False):
        GLib.idle_add(self.page_details.update_programs, config=self.config)

    def uninstall_program(self, widget):
        RunAsync(
            task_func=self.manager.remove_program,
            callback=self.update_programs,
            config=self.config,
            program_name=self.program["name"]
        )

    def hide_program(self, widget=None, update=True):
        status = not self.program.get("removed")
        self.program["removed"] = status
        self.config = self.manager.update_config(
            config=self.config,
            key=self.program["executable"],
            value=self.program,
            scope="External_Programs"
        )
        self.btn_hide.set_visible(not status)
        self.btn_unhide.set_visible(status)
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
                "executable": self.program["executable"],
                "path": self.program["path"],
            }
        )

    def add_to_library(self, widget):
        LibraryManager().add_to_library({
            "bottle": {"name": self.config["Name"], "path": self.config["Path"]},
            "name": self.program["name"],
        })
        self.window.update_library()

    def open_search_url(self, widget, site):
        query = self.program["name"].replace(" ", "+")
        sites = {
            "winehq": f"https://www.winehq.org/search?q={query}",
            "protondb": f"https://www.protondb.com/search?q={query}",
            "forum": f"https://forums.usebottles.com/?q={query}",
            "issues": f"https://github.com/bottlesdevs/Bottles/issues?q=is:issue{query}"
        }
        webbrowser.open_new_tab(sites[site])
