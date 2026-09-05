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

from gi.repository import Gdk, Gio, GLib, Gtk

from bottles.backend.logger import Logger
from bottles.backend.managers.library import LibraryManager
from bottles.backend.managers.thumbnail import ThumbnailManager
from bottles.backend.models.result import Result
from bottles.backend.umu import UmuRepositoryError
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync
from bottles.backend.wine.wineboot import WineBoot
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.winedbg import WineDbg
from bottles.frontend.utils.gtk import GtkUtils
from bottles.frontend.utils.sandbox_guard import guard_sandbox_launch
from bottles.frontend.utils.umu import get_umu_store_title

logging = Logger()


class LibraryEntryInitializationError(Exception):
    """Raised when a library entry cannot be initialized."""

    pass


@Gtk.Template(resource_path="/com/usebottles/bottles/library-add-entry.ui")
class LibraryAddEntry(Gtk.Box):
    __gtype_name__ = "LibraryAddEntry"

    btn_umu = Gtk.Template.Child()
    btn_bottle = Gtk.Template.Child()

    def __init__(self, library, **kwargs):
        super().__init__(**kwargs)
        self.btn_umu.connect("clicked", library.window.show_umu_search)
        self.btn_bottle.connect("clicked", library.show_bottle_programs)


@Gtk.Template(resource_path="/com/usebottles/bottles/library-entry.ui")
class LibraryEntry(Gtk.Box):
    __gtype_name__ = "LibraryEntry"
    __cover_lookups = set()

    # region Widgets
    btn_run = Gtk.Template.Child()
    btn_stop = Gtk.Template.Child()
    btn_launch_steam = Gtk.Template.Child()
    btn_cover = Gtk.Template.Child()
    btn_settings = Gtk.Template.Child()
    btn_umu_actions = Gtk.Template.Child()
    btn_umu_desktop = Gtk.Template.Child()
    btn_umu_steam = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    label_name = Gtk.Template.Child()
    label_bottle = Gtk.Template.Child()
    label_no_cover = Gtk.Template.Child()
    label_source = Gtk.Template.Child()
    img_cover = Gtk.Template.Child()
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
        self.source = entry.get("source")
        self.__pointer_inside = False
        if self.source is None:
            self.source = "steam" if entry.get("steam", False) else "bottle"
        self.is_steam = self.source == "steam"
        self.is_umu = self.source == "umu"
        try:
            self.config = None if self.is_umu else self.__get_config()

            if self.config is None and not self.is_umu:
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
        if self.is_umu:
            self.btn_remove.set_visible(False)
            state_labels = {
                "draft": _("Choose Executable"),
                "installing": _("Installing"),
                "failed": _("Installation Failed"),
                "stopped": _("Installation Stopped"),
            }
            detail = state_labels.get(
                self.game.state,
                get_umu_store_title(self.game.store),
            )
            self.label_bottle.set_text(f"UMU / {detail}")
            self.label_source.set_visible(True)
            self.btn_settings.set_visible(True)
            self.btn_umu_actions.set_visible(True)
            self.btn_umu_actions.set_sensitive(self.game.state == "ready")
            executor = self.manager.get_umu_executor(for_launch=False)
            if executor is not None and executor.is_running(self.game):
                self.btn_remove.set_visible(False)
                self.btn_stop.set_visible(True)
                tracked = executor.is_tracked(self.game)
                self.btn_stop.set_sensitive(tracked)
                if not tracked:
                    self.btn_stop.set_tooltip_text(
                        _("Running outside this Bottles session")
                    )
                self.btn_run.set_visible(False)
            elif self.game.state != "ready":
                self.btn_run.set_visible(False)
        else:
            self.label_bottle.set_text(
                "Steam" if self.is_steam else entry["bottle"]["name"]
            )
        self.label_no_cover.set_label(self.name)

        if self.is_steam:
            self.btn_run.set_visible(False)
            self.btn_launch_steam.set_visible(True)

        if entry.get("thumbnail"):
            path = ThumbnailManager.get_path(self.config, entry["thumbnail"])

            if path is None and not self.is_umu:
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
        elif self.is_umu and self.uuid not in self.__cover_lookups:
            self.__cover_lookups.add(self.uuid)

            def cover_downloaded(result, error=False):
                self.__cover_lookups.discard(self.uuid)
                if not error and result:
                    self.library.update()

            RunAsync(
                task_func=LibraryManager().download_thumbnail,
                callback=cover_downloaded,
                _uuid=self.uuid,
            )

        motion_ctrl = Gtk.EventControllerMotion.new()
        motion_ctrl.connect("enter", self.__on_motion_enter)
        motion_ctrl.connect("leave", self.__on_motion_leave)
        self.overlay.add_controller(motion_ctrl)
        self.btn_run.connect("clicked", self.run_executable)
        self.btn_launch_steam.connect("clicked", self.run_steam)
        self.btn_cover.connect("clicked", self.__choose_cover)
        self.btn_settings.connect("clicked", self.__show_settings)
        self.__umu_actions_popover = self.btn_umu_actions.get_popover()
        self.__umu_actions_popover.connect(
            "notify::visible", self.__on_umu_actions_visible
        )
        self.btn_umu_desktop.connect("clicked", self.__add_umu_desktop_entry)
        self.btn_umu_steam.connect("clicked", self.__add_umu_steam_shortcut)
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
        if self.is_umu:
            try:
                self.game = self.manager.umu_repository.load(self.entry["source_id"])
            except (KeyError, FileNotFoundError, UmuRepositoryError) as error:
                logging.warning(f"Cannot load UMU library entry: {error}")
                self.__remove_from_library()
                return None
            return {
                "id": self.game.library_id,
                "name": self.game.name,
                "path": str(self.game.executable),
                "executable": self.game.executable.name,
            }

        if self.entry.get("steam"):
            return self.entry

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
        library_manager.remove_from_library(self.uuid, getattr(self, "config", None))

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

        self.btn_remove.set_visible(status and not self.is_umu)
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

    def __show_settings(self, *_args):
        self.window.show_umu_game_settings(str(self.game.id))

    def __umu_launcher_data(self):
        return (
            {"Name": f"UMU-{self.game.id}"},
            {
                "name": self.game.name,
                "executable": self.game.executable.name,
                "umu_game": str(self.game.id),
            },
        )

    def __add_umu_desktop_entry(self, *_args):
        config, program = self.__umu_launcher_data()
        self.btn_umu_desktop.set_sensitive(False)

        def complete(result):
            self.btn_umu_desktop.set_sensitive(True)
            if result.ok:
                self.window.show_toast(
                    _('Desktop Entry created for "{0}"').format(self.game.name)
                )
            else:
                self.window.show_toast(
                    _('Could not create a Desktop Entry for "{0}"').format(
                        self.game.name
                    )
                )

        ManagerUtils.create_desktop_entry(
            config,
            program,
            skip_icon=True,
            callback=complete,
        )

    def __add_umu_steam_shortcut(self, *_args):
        self.btn_umu_steam.set_sensitive(False)

        def complete(result, error=False):
            self.btn_umu_steam.set_sensitive(True)
            if not error and result and result.ok:
                self.window.show_toast(
                    _('Added "{0}" to Steam').format(self.game.name)
                )
            else:
                self.window.show_toast(
                    _('Could not add "{0}" to Steam').format(self.game.name)
                )

        RunAsync(
            self.manager.steam_manager.add_umu_shortcut,
            callback=complete,
            game=self.game,
        )

    def __choose_cover(self, *_args):
        def set_cover(dialog, result):
            try:
                file = dialog.open_finish(result)
            except GLib.Error:
                return

            path = file.get_path()
            if path is None:
                self.window.show_toast(_("The cover image could not be opened."))
                return

            try:
                Gdk.Texture.new_from_filename(path)
            except GLib.Error:
                self.window.show_toast(_("The selected file is not a valid image."))
                return

            library_manager = LibraryManager()
            if not library_manager.set_thumbnail(self.uuid, path, self.config):
                self.window.show_toast(_("The cover image could not be saved."))
                return

            self.library.update()
            self.window.show_toast(_("Cover image updated."))

        filters = Gio.ListStore.new(Gtk.FileFilter)
        image_filter = Gtk.FileFilter()
        image_filter.set_name(_("Images"))
        for extension in ("png", "jpg", "jpeg", "webp"):
            image_filter.add_pattern(f"*.{extension}")
            image_filter.add_pattern(f"*.{extension.upper()}")
        filters.append(image_filter)

        dialog = Gtk.FileDialog.new()
        dialog.set_title(_("Select Cover Image"))
        dialog.set_filters(filters)
        dialog.set_default_filter(image_filter)
        pictures = GLib.get_user_special_dir(
            GLib.UserDirectory.DIRECTORY_PICTURES
        )
        if pictures:
            dialog.set_initial_folder(Gio.File.new_for_path(pictures))
        dialog.open(self.window, callback=set_cover)

    def run_executable(self, widget, with_terminal=False):
        if self.is_umu:
            self.__run_umu()
            return

        def proceed(sandbox_override, exec_path):
            program = self.program
            if exec_path and exec_path != self.program.get("path"):
                program = {**self.program, "path": exec_path}
            self.window.show_toast(
                _('Launching "{0}"…').format(self.program["name"])
            )
            RunAsync(
                WineExecutor.run_program,
                callback=self.__reset_buttons,
                config=self.config,
                program=program,
                sandbox_override=sandbox_override,
            )
            self.__reset_buttons()

        guard_sandbox_launch(
            self.window, self.config, self.program.get("path"), proceed
        )

    def __run_umu(self):
        if self.game.state != "ready":
            self.window.show_toast(
                _("Select the installed game executable before launching it.")
            )
            self.window.show_umu_game_settings(str(self.game.id))
            return
        executor = self.manager.get_umu_executor()
        if executor is None:
            self.window.show_umu_unavailable()
            return

        self.window.show_toast(_('Launching "{0}"...').format(self.game.name))

        def run():
            executor.run(self.game)
            return executor.wait(self.game)

        def complete(return_code, error=False):
            self.__reset_buttons(True)
            if error:
                self.window.show_toast(_("The game could not be started."))
            elif return_code:
                self.window.show_toast(
                    _("The game exited with status {0}.").format(return_code)
                )

        RunAsync(run, callback=complete)
        self.btn_remove.set_visible(False)
        self.btn_stop.set_visible(True)
        self.btn_stop.set_sensitive(True)
        self.btn_run.set_visible(False)

    def run_steam(self, widget):
        self.manager.steam_manager.launch_app(self.config.CompatData)

    def stop_process(self, widget):
        self.window.show_toast(_('Stopping "{0}"...').format(self.program["name"]))
        if self.is_umu:
            executor = self.manager.get_umu_executor(for_launch=False)
            if executor is None:
                self.__reset_buttons(True)
                return

            def complete(stopped, error=False):
                running = executor.is_running(self.game)
                self.__reset_buttons(not running)
                if error or (not stopped and running):
                    self.window.show_toast(_("The game could not be stopped."))

            RunAsync(executor.terminate, callback=complete, game_or_process=self.game)
            return

        self.btn_stop.set_sensitive(False)

        def complete(_result=None, error=False):
            self.__reset_buttons(True)
            if error:
                self.window.show_toast(_("The game could not be stopped."))

        RunAsync(
            WineBoot(self.config).kill,
            callback=complete,
            force_if_stalled=True,
        )

    def __on_motion_enter(self, *args):
        self.__pointer_inside = True
        self.__sync_details_revealer()

    def __on_motion_leave(self, *args):
        self.__pointer_inside = False
        self.__sync_details_revealer()

    def __on_umu_actions_visible(self, *_args):
        self.__sync_details_revealer()

    def __sync_details_revealer(self):
        self.revealer_details.set_reveal_child(
            self.__pointer_inside or self.__umu_actions_popover.get_visible()
        )

    # hide() and show() are essentialy workarounds to avoid keeping
    # the empty space of the hidden entry in the GtkFlowBox
    def hide(self):
        self.get_parent().set_visible(False)

    def show(self):
        self.get_parent().set_visible(True)
