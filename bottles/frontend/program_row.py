# program_row.py
#
# Copyright 2025 The Bottles Contributors
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

import webbrowser
from gettext import gettext as _

from gi.repository import Gtk, Adw

from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.uninstaller import Uninstaller
from bottles.backend.wine.winedbg import WineDbg
from bottles.frontend.gtk import GtkUtils
from bottles.frontend.launch_options_dialog import LaunchOptionsDialog
from bottles.frontend.rename_program_dialog import RenameProgramDialog


# noinspection PyUnusedLocal
@Gtk.Template(resource_path="/com/usebottles/bottles/program-row.ui")
class ProgramRow(Adw.ActionRow):
    __gtype_name__ = "ProgramRow"

    # region Widgets
    btn_menu = Gtk.Template.Child()
    btn_run = Gtk.Template.Child()
    btn_stop = Gtk.Template.Child()
    btn_launch_options = Gtk.Template.Child()
    btn_uninstall = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_hide = Gtk.Template.Child()
    btn_unhide = Gtk.Template.Child()
    btn_rename = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_add_steam = Gtk.Template.Child()
    btn_add_entry = Gtk.Template.Child()
    btn_launch_terminal = Gtk.Template.Child()
    pop_actions = Gtk.Template.Child()

    # endregion

    def __init__(
        self, window, config, program, is_steam=False, check_boot=True, **kwargs
    ):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.view_bottle = window.page_details.view_bottle
        self.manager = window.manager
        self.config = config
        self.program = program

        self.set_title(self.program["name"])

        self.executable = program.get("executable", "")

        if program.get("removed"):
            self.add_css_class("removed")

        if program.get("auto_discovered"):
            self.btn_remove.set_visible(False)

        self.btn_hide.set_visible(not program.get("removed"))
        self.btn_unhide.set_visible(program.get("removed"))

        external_programs = []
        for v in self.config.External_Programs.values():
            external_programs.append(v["name"])

        """Signal connections"""
        self.btn_run.connect("clicked", self.run_executable)
        self.btn_launch_terminal.connect("clicked", self.run_executable, True)
        self.btn_stop.connect("clicked", self.stop_process)
        self.btn_launch_options.connect("clicked", self.show_launch_options_view)
        self.btn_uninstall.connect("clicked", self.uninstall_program)
        self.btn_hide.connect("clicked", self.hide_program)
        self.btn_unhide.connect("clicked", self.hide_program)
        self.btn_rename.connect("clicked", self.rename_program)
        self.btn_browse.connect("clicked", self.browse_program_folder)
        self.btn_add_entry.connect("clicked", self.add_entry)
        self.btn_remove.connect("clicked", self.remove_program)

        if not program.get("removed") and not is_steam and check_boot:
            self.__is_alive()

    def show_launch_options_view(self, _widget=False):
        def update(_widget, config):
            self.config = config
            self.update_programs()

        dialog = LaunchOptionsDialog(self, self.config, self.program)
        dialog.present()
        dialog.connect("options-saved", update)

    @GtkUtils.run_in_main_loop
    def __reset_buttons(self, result: bool | Result = False, _error=False):
        status = False
        if isinstance(result, Result):
            status = result.status
        elif isinstance(result, bool):
            status = result
            if not isinstance(result, bool):
                status = result.status
        else:
            raise NotImplementedError(
                "Invalid data type, expect bool or Result, but it was %s" % type(result)
            )

        self.btn_run.set_visible(status)
        self.btn_stop.set_visible(not status)
        self.btn_run.set_sensitive(status)
        self.btn_stop.set_sensitive(not status)

    def __is_alive(self):
        winedbg = WineDbg(self.config)

        @GtkUtils.run_in_main_loop
        def set_watcher(_result=False, _error=False):
            nonlocal winedbg
            self.__reset_buttons()

            RunAsync(
                winedbg.wait_for_process,
                callback=self.__reset_buttons,
                name=self.executable,
                timeout=5,
            )

        RunAsync(winedbg.is_process_alive, callback=set_watcher, name=self.executable)

    def run_executable(self, _widget, with_terminal=False):
        self.pop_actions.popdown()  # workaround #1640

        def _run():
            WineExecutor.run_program(self.config, self.program, with_terminal)
            self.pop_actions.popdown()  # workaround #1640
            return True

        self.window.show_toast(_('Launching "{0}"…').format(self.program["name"]))
        RunAsync(_run, callback=self.__reset_buttons)
        self.__reset_buttons()

    def stop_process(self, widget):
        self.window.show_toast(_('Stopping "{0}"…').format(self.program["name"]))
        winedbg = WineDbg(self.config)
        widget.set_sensitive(False)
        winedbg.kill_process(self.executable)
        self.__reset_buttons(True)

    @GtkUtils.run_in_main_loop
    def update_programs(self, _result=False, _error=False):
        self.view_bottle.update_programs(config=self.config)

    def uninstall_program(self, _widget):
        uninstaller = Uninstaller(self.config)
        RunAsync(
            task_func=uninstaller.from_name,
            callback=self.update_programs,
            name=self.program["name"],
        )

    def hide_program(self, _widget=None, update=True):
        status = not self.program.get("removed")
        msg = _('"{0}" hidden').format(self.program["name"])
        if not status:
            msg = _('"{0}" showed').format(self.program["name"])

        self.program["removed"] = status
        self.save_program()
        self.btn_hide.set_visible(not status)
        self.btn_unhide.set_visible(status)
        self.window.show_toast(msg)
        if update:
            self.update_programs()

    def save_program(self):
        return self.manager.update_config(
            config=self.config,
            key=self.program["id"],
            value=self.program,
            scope="External_Programs",
        ).data["config"]

    def remove_program(self, _widget=None):
        self.config = self.manager.update_config(
            config=self.config,
            key=self.program["id"],
            scope="External_Programs",
            value=None,
            remove=True,
        ).data["config"]
        self.window.show_toast(_('"{0}" removed').format(self.program["name"]))
        self.update_programs()

    def rename_program(self, _widget):
        def func(new_name):
            if new_name == self.program["name"]:
                return
            old_name = self.program["name"]
            self.program["name"] = new_name
            self.manager.update_config(
                config=self.config,
                key=self.program["id"],
                value=self.program,
                scope="External_Programs",
            )

            self.window.page_library.update()
            self.window.show_toast(
                _('"{0}" renamed to "{1}"').format(old_name, new_name)
            )
            self.update_programs()

        dialog = RenameProgramDialog(
            self.window, on_save=func, name=self.program["name"]
        )
        dialog.present()

    def browse_program_folder(self, _widget):
        ManagerUtils.open_filemanager(
            config=self.config, path_type="custom", custom_path=self.program["folder"]
        )
        self.pop_actions.popdown()  # workaround #1640

    def add_entry(self, _widget):
        @GtkUtils.run_in_main_loop
        def update(result, _error=False):
            if not result:
                webbrowser.open("https://docs.usebottles.com/bottles/programs#flatpak")
                return

            self.window.show_toast(
                _('Desktop Entry created for "{0}"').format(self.program["name"])
            )

        RunAsync(
            ManagerUtils.create_desktop_entry,
            callback=update,
            config=self.config,
            program={
                "name": self.program["name"],
                "executable": self.program["executable"],
                "path": self.program["path"],
            },
        )
