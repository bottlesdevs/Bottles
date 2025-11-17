# library.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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

from gettext import gettext as _

from gi.repository import Gdk, Gtk

from bottles.backend.logger import Logger
from bottles.backend.managers.library import LibraryManager
from bottles.backend.managers.thumbnail import ThumbnailManager
from bottles.backend.models.result import Result
from bottles.backend.utils.threading import RunAsync
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.winedbg import WineDbg
from bottles.frontend.utils.gtk import GtkUtils

logging = Logger()


class LibraryEntryInitializationError(Exception):
    """Raised when a library entry cannot be initialized."""

    pass


@Gtk.Template(resource_path="/com/usebottles/bottles/library-entry.ui")
class LibraryEntry(Gtk.Box):
    __gtype_name__ = "LibraryEntry"

    # region Widgets
    btn_run = Gtk.Template.Child()
    btn_stop = Gtk.Template.Child()
    btn_launch_steam = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    label_name = Gtk.Template.Child()
    label_bottle = Gtk.Template.Child()
    label_no_cover = Gtk.Template.Child()
    img_cover = Gtk.Template.Child()
    revealer_run = Gtk.Template.Child()
    revealer_details = Gtk.Template.Child()
    overlay = Gtk.Template.Child()

    # endregion

    def __init__(self, library, uuid, entry, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.library = library
        self.window = library.window
        self.manager = library.window.manager
        self.name = entry["name"]
        self.uuid = uuid
        self.entry = entry
        try:
            self.config = self.__get_config()

            if self.config is None:
                raise LibraryEntryInitializationError(
                    _(
                        'The bottle for "{0}" is no longer available. Removing it from the library.'
                    ).format(self.name)
                )

            self.program = self.__get_program()

            if self.program is None:
                raise LibraryEntryInitializationError(
                    _(
                        'The program "{0}" is no longer available. Removing it from the library.'
                    ).format(self.name)
                )

        except LibraryEntryInitializationError as error:
            self.__handle_initialization_failure(str(error))
            raise

        if len(entry["name"]) >= 15:
            name = entry["name"][:13] + "…"
        else:
            name = entry["name"]

        self.label_name.set_text(name)
        self.label_bottle.set_text(entry["bottle"]["name"])
        self.label_no_cover.set_label(self.name)

        if entry.get("thumbnail"):
            path = ThumbnailManager.get_path(self.config, entry["thumbnail"])

            if path is None:
                # redownloading *should* never fail as it was successfully downloaded before
                logging.info("Redownloading grid image...")
                library_manager = LibraryManager()
                result = library_manager.download_thumbnail(self.uuid, self.config)
                if result:
                    entry = library_manager.get_library().get(uuid)
                    path = ThumbnailManager.get_path(self.config, entry["thumbnail"])

            if path is not None:
                # Gtk.Picture.set_pixbuf deprecated in GTK 4.12
                texture = Gdk.Texture.new_from_filename(path)
                self.img_cover.set_paintable(texture)
                self.img_cover.set_visible(True)
                self.label_no_cover.set_visible(False)

        motion_ctrl = Gtk.EventControllerMotion.new()
        motion_ctrl.connect("enter", self.__on_motion_enter)
        motion_ctrl.connect("leave", self.__on_motion_leave)
        self.overlay.add_controller(motion_ctrl)
        self.btn_run.connect("clicked", self.run_executable)
        self.btn_launch_steam.connect("clicked", self.run_steam)
        self.btn_stop.connect("clicked", self.stop_process)
        self.btn_remove.connect("clicked", self.__remove_entry)

    def __get_config(self):
        bottles = self.manager.local_bottles
        bottle_name = self.entry["bottle"]["name"]

        if bottle_name in bottles:
            return bottles[bottle_name]

        self.__remove_from_library()
        return None

    def __get_program(self):
        programs = self.manager.get_programs(self.config)
        programs = [
            p
            for p in programs
            if p["id"] == self.entry["id"] or p["name"] == self.entry["name"]
        ]
        if len(programs) == 0:
            self.__remove_from_library()
            return None
        return programs[0]

    def __remove_from_library(self):
        library_manager = LibraryManager()
        library_manager.remove_from_library(self.uuid)

    def __handle_initialization_failure(self, message: str):
        logging.warning(message, jn=False)

        if hasattr(self.window, "show_toast"):
            self.window.show_toast(message)

    @GtkUtils.run_in_main_loop
    def __reset_buttons(self, result: Result | bool = None, error=False):
        match result:
            case Result():
                status = result.status
            case bool():
                status = result
            case _:
                logging.error(
                    f"result should be Result or bool, but it was {type(result)}"
                )
                status = False

        self.btn_remove.set_visible(status)
        self.btn_stop.set_visible(not status)
        self.btn_run.set_visible(status)

    def __is_alive(self):
        winedbg = WineDbg(self.config)

        @GtkUtils.run_in_main_loop
        def set_watcher(result=False, error=False):
            nonlocal winedbg
            self.__reset_buttons()

            RunAsync(
                winedbg.wait_for_process,
                callback=self.__reset_buttons,
                name=self.program["executable"],
                timeout=5,
            )

        RunAsync(
            winedbg.is_process_alive,
            callback=set_watcher,
            name=self.program["executable"],
        )

    def __remove_entry(self, *args):
        self.library.remove_entry(self)

    def run_executable(self, widget, with_terminal=False):
        self.window.show_toast(_('Launching "{0}"…').format(self.program["name"]))
        RunAsync(
            WineExecutor.run_program,
            callback=self.__reset_buttons,
            config=self.config,
            program=self.program,
        )
        self.__reset_buttons()

    def run_steam(self, widget):
        self.manager.steam_manager.launch_app(self.config.CompatData)

    def stop_process(self, widget):
        self.window.show_toast(_('Stopping "{0}"…').format(self.program["name"]))
        winedbg = WineDbg(self.config)
        winedbg.kill_process(name=self.program["executable"])
        self.__reset_buttons(True)

    def __on_motion_enter(self, *args):
        self.revealer_run.set_reveal_child(True)
        self.revealer_details.set_reveal_child(True)

    def __on_motion_leave(self, *args):
        self.revealer_run.set_reveal_child(False)
        self.revealer_details.set_reveal_child(False)

    # hide() and show() are essentialy workarounds to avoid keeping
    # the empty space of the hidden entry in the GtkFlowBox
    def hide(self):
        self.get_parent().set_visible(False)

    def show(self):
        self.get_parent().set_visible(True)
