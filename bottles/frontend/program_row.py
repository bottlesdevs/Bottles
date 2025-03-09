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

from bottles.backend.managers.library import LibraryManager
from bottles.backend.managers.steam import SteamManager
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
    btn_launch_steam = Gtk.Template.Child()
    btn_uninstall = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_hide = Gtk.Template.Child()
    btn_unhide = Gtk.Template.Child()
    btn_rename = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_add_steam = Gtk.Template.Child()
    btn_add_entry = Gtk.Template.Child()
    btn_add_library = Gtk.Template.Child()
    btn_launch_terminal = Gtk.Template.Child()
    pop_actions = Gtk.Template.Child()

    # endregion

    def __init__(
        self, window, config, program, is_steam=False, check_boot=True, **kwargs
    ):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.view_bottle = window.page_details.details_view_subpage.view_bottle
        self.manager = window.manager
        self.config = config
        self.program = program

        self.set_title(self.program["name"])

        if is_steam:
            self.set_subtitle("Steam")
            for w in [self.btn_run, self.btn_stop, self.btn_menu]:
                w.set_visible(False)
                w.set_sensitive(False)
            self.btn_launch_steam.set_visible(True)
            self.btn_launch_steam.set_sensitive(True)
            self.set_activatable_widget(self.btn_launch_steam)
        else:
            self.executable = program.get("executable", "")

        if program.get("removed"):
            self.add_css_class("removed")

        if program.get("auto_discovered"):
            self.btn_remove.set_visible(False)

        self.btn_hide.set_visible(not program.get("removed"))
        self.btn_unhide.set_visible(program.get("removed"))

        if self.manager.steam_manager.is_steam_supported:
            self.btn_add_steam.set_visible(True)

        library_manager = LibraryManager()
        for _uuid, entry in library_manager.get_library().items():
            if entry.get("id") == program.get("id"):
                self.btn_add_library.set_visible(False)

        external_programs = []
        for v in self.config.External_Programs.values():
            external_programs.append(v["name"])

        """Signal connections"""
        self.btn_run.connect("clicked", self.run_executable)
        self.btn_launch_steam.connect("clicked", self.run_steam)
        self.btn_launch_terminal.connect("clicked", self.run_executable, True)
        self.btn_stop.connect("clicked", self.stop_process)
        self.btn_launch_options.connect("clicked", self.show_launch_options_view)
        self.btn_uninstall.connect("clicked", self.uninstall_program)
        self.btn_hide.connect("clicked", self.hide_program)
        self.btn_unhide.connect("clicked", self.hide_program)
        self.btn_rename.connect("clicked", self.rename_program)
        self.btn_browse.connect("clicked", self.browse_program_folder)
        self.btn_add_entry.connect("clicked", self.add_entry)
        self.btn_add_library.connect("clicked", self.add_to_library)
        self.btn_add_steam.connect("clicked", self.add_to_steam)
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

    def run_steam(self, _widget):
        self.manager.steam_manager.launch_app(self.config.CompatData)
        self.window.show_toast(
            _('Launching "{0}" with Steam…').format(self.program["name"])
        )
        self.pop_actions.popdown()  # workaround #1640

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

            def async_work():
                library_manager = LibraryManager()
                entries = library_manager.get_library()

                for uuid, entry in entries.items():
                    if entry.get("id") == self.program["id"]:
                        entries[uuid]["name"] = new_name
                        library_manager.download_thumbnail(uuid, self.config)
                        break

                library_manager.__library = entries
                library_manager.save_library()

            @GtkUtils.run_in_main_loop
            def ui_update(_result, _error):
                self.window.page_library.update()
                self.window.show_toast(
                    _('"{0}" renamed to "{1}"').format(old_name, new_name)
                )
                self.update_programs()

            RunAsync(async_work, callback=ui_update)

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

    def add_to_library(self, _widget):
        def update(_result, _error=False):
            self.window.update_library()
            self.window.show_toast(
                _('"{0}" added to your library').format(self.program["name"])
            )

        def add_to_library():
            self.save_program()  # we need to store it in the bottle configuration to keep the reference
            library_manager = LibraryManager()
            library_manager.add_to_library(
                {
                    "bottle": {"name": self.config.Name, "path": self.config.Path},
                    "name": self.program["name"],
                    "id": str(self.program["id"]),
                    "icon": ManagerUtils.extract_icon(
                        self.config, self.program["name"], self.program["path"]
                    ),
                },
                self.config,
            )

        self.btn_add_library.set_visible(False)
        RunAsync(add_to_library, update)

    def add_to_steam(self, _widget):
        def update(result, _error=False):
            if result.ok:
                self.window.show_toast(
                    _('"{0}" added to your Steam library').format(self.program["name"])
                )
            else:
                self.window.show_toast(
                    _('"{0}" failed adding to your Steam library').format(
                        self.program["name"]
                    )
                )

        steam_manager = SteamManager(self.config)
        RunAsync(
            steam_manager.add_shortcut,
            update,
            program_name=self.program["name"],
            program_path=self.program["path"],
        )
