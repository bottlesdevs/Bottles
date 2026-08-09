# program.py
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

import hashlib
import os
import time
import webbrowser
from gettext import gettext as _

from gi.repository import Adw, Gdk, GLib, Gtk

from bottles.backend.managers.data import DataManager, UserDataKeys
from bottles.backend.managers.eagle import EagleManager
from bottles.backend.managers.library import LibraryManager
from bottles.backend.managers.steam import SteamManager
from bottles.backend.models.result import Result
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.uninstaller import Uninstaller
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.wineserver import WineServer
from bottles.frontend.utils.gtk import GtkUtils
from bottles.frontend.utils.playtime import PlaytimeService
from bottles.frontend.utils.sandbox_guard import guard_sandbox_launch
from bottles.frontend.windows.fileassociations import FileAssociationsDialog
from bottles.frontend.windows.launchoptions import LaunchOptionsDialog
from bottles.frontend.windows.playtimegraph import PlaytimeGraphDialog
from bottles.frontend.windows.rename import RenameDialog


# noinspection PyUnusedLocal
@Gtk.Template(resource_path="/com/usebottles/bottles/program-entry.ui")
class ProgramEntry(Adw.ActionRow):
    __gtype_name__ = "ProgramEntry"

    # region Widgets
    btn_menu = Gtk.Template.Child()
    btn_run = Gtk.Template.Child()
    btn_stop = Gtk.Template.Child()
    btn_launch_options = Gtk.Template.Child()
    btn_playtime_stats = Gtk.Template.Child()
    btn_launch_steam = Gtk.Template.Child()
    btn_uninstall = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_hide = Gtk.Template.Child()
    btn_unhide = Gtk.Template.Child()
    btn_rename = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_add_steam = Gtk.Template.Child()
    btn_add_entry = Gtk.Template.Child()
    btn_file_associations = Gtk.Template.Child()
    btn_add_library = Gtk.Template.Child()
    btn_add_steam_library = Gtk.Template.Child()
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
        self.is_steam = is_steam
        self.__desktop_entry_exists = False
        self.__desktop_entry_query_pending = False
        self.__program_icon_job = None
        self.__program_icon_path = None

        self.set_title(GLib.markup_escape_text(self.program["name"]))

        if is_steam:
            self.set_subtitle("Steam")
            for w in [self.btn_run, self.btn_stop, self.btn_menu]:
                w.set_visible(False)
                w.set_sensitive(False)
            self.btn_launch_steam.set_visible(True)
            self.btn_launch_steam.set_sensitive(True)
            self.btn_add_steam_library.set_visible(True)
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

        program_icon = self.program.get("icon", "com.usebottles.bottles-program")
        library_manager = LibraryManager()
        for _uuid, entry in library_manager.get_library().items():
            if entry.get("id") == program.get("id"):
                self.btn_add_library.set_visible(False)
                self.btn_add_steam_library.set_visible(False)
                program_icon = entry.get("icon") or program_icon

        self.img_program = Gtk.Image()
        self.img_program.set_pixel_size(32)
        self.img_program.set_valign(Gtk.Align.CENTER)
        extract_program_icon = False
        program_name = self.program.get("name", "")
        program_path = self.program.get("path")
        if (
            program_icon == "com.usebottles.bottles-program"
            and not is_steam
            and program_name
            and program_path
            and not any(separator in program_name for separator in ("/", "\\"))
        ):
            self.__program_icon_path = os.path.join(
                ManagerUtils.get_bottle_path(self.config),
                "icons",
                f"{program_name}.png",
            )
            if os.path.isfile(self.__program_icon_path):
                program_icon = self.__program_icon_path
                self.program["icon"] = program_icon
            else:
                extract_program_icon = True
        if isinstance(program_icon, str) and os.path.isfile(program_icon):
            self.img_program.set_from_file(program_icon)
        elif isinstance(program_icon, str) and not any(
            separator in program_icon for separator in ("/", "\\")
        ):
            self.img_program.set_from_icon_name(program_icon)
        else:
            self.img_program.set_from_icon_name("com.usebottles.bottles-program")
        self.add_prefix(self.img_program)
        if extract_program_icon:
            self.__program_icon_job = RunAsync(
                ManagerUtils.extract_icon,
                callback=self.__program_icon_ready,
                config=self.config,
                program_name=program_name,
                program_path=program_path,
            )

        external_programs = []
        for v in self.config.External_Programs.values():
            external_programs.append(v["name"])

        """Signal connections"""
        self.btn_run.connect("clicked", self.run_executable)
        self.btn_launch_steam.connect("clicked", self.run_steam)
        self.btn_launch_terminal.connect("clicked", self.run_executable, True)
        self.btn_stop.connect("clicked", self.stop_process)
        self.btn_launch_options.connect("clicked", self.show_launch_options_view)
        self.btn_playtime_stats.connect("clicked", self.show_playtime_stats)
        self.btn_uninstall.connect("clicked", self.uninstall_program)
        self.btn_hide.connect("clicked", self.hide_program)
        self.btn_unhide.connect("clicked", self.hide_program)
        self.btn_rename.connect("clicked", self.rename_program)
        self.btn_browse.connect("clicked", self.browse_program_folder)
        self.btn_add_entry.connect("clicked", self.manage_entry)
        self.btn_file_associations.connect("clicked", self.show_file_associations)
        self.btn_add_library.connect("clicked", self.add_to_library)
        self.btn_add_steam_library.connect("clicked", self.add_to_library)
        self.btn_add_steam.connect("clicked", self.add_to_steam)
        self.btn_remove.connect("clicked", self.remove_program)
        self.pop_actions.connect(
            "notify::visible", self.__refresh_desktop_entry_state
        )

        if not program.get("removed") and not is_steam and check_boot:
            self.__is_alive()

        # Update subtitle with playtime info
        if not is_steam:
            self.__update_subtitle()

    def __program_icon_ready(self, icon, error):
        if error is None and isinstance(icon, str) and os.path.isfile(icon):
            self.program["icon"] = icon
            self.img_program.set_from_file(icon)

    def __update_subtitle(self):
        """Update the subtitle with playtime information."""
        try:
            # Create playtime service if tracking is enabled
            if not hasattr(self.manager, "playtime_service"):
                self.manager.playtime_service = PlaytimeService(self.manager)

            service = self.manager.playtime_service
            if not service.is_enabled():
                return

            # Get bottle path and program path
            bottle_path = ManagerUtils.get_bottle_path(self.config)
            program_path = self.program.get("path", "")

            if not program_path:
                return

            # Fetch playtime data
            record = service.get_program_playtime(
                bottle_id=self.config.Name,
                bottle_path=bottle_path,
                program_name=self.program.get("name", "Unknown"),
                program_path=program_path,
            )

            # Always format subtitle (handles both played and never played cases)
            subtitle = service.format_subtitle(record)
            self.set_subtitle(subtitle)
        except Exception as e:
            # Log error but don't break the UI
            import logging

            logging.debug(f"Failed to update playtime subtitle: {e}")
            pass

    def show_launch_options_view(self, _widget=False):
        def update(_widget, config):
            self.config = config
            self.update_programs()

        dialog = LaunchOptionsDialog(self, self.config, self.program)
        dialog.present()
        dialog.connect("options-saved", update)

    def show_playtime_stats(self, _widget=False):
        """Show the playtime statistics dialog for this program."""
        from bottles.backend.managers.playtime import _compute_program_id
        from bottles.backend.utils.manager import ManagerUtils

        self.pop_actions.popdown()  # Close the menu before opening dialog

        program_path = self.program.get("path", "")
        bottle_path = ManagerUtils.get_bottle_path(self.config)
        program_id = _compute_program_id(self.config.Name, bottle_path, program_path)

        dialog = PlaytimeGraphDialog(
            self,
            program_name=self.program.get("name", "Unknown"),
            program_id=program_id,
            bottle_id=self.config.Name,
        )
        dialog.present()

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

        path = self.program.get("path")
        if (
            not path
            or not os.path.isfile(path)
            or not self.window.settings.get_boolean("eagle-security-scan")
        ):
            # nothing to scan, or scanning disabled in settings; launch directly
            return self.__launch_program(with_terminal)

        # scan for known malware/stealer patterns before launching; the scan
        # runs off the main loop so the UI never freezes
        def check():
            return self.__eagle_security_check(path)

        def after(findings, _error=False):
            if findings:
                self.__show_security_advisory(findings, path, with_terminal)
            else:
                self.__launch_program(with_terminal)

        RunAsync(check, callback=after)

    # below this many seconds, a program that has already exited most likely
    # failed to start (crash / immediate close) rather than being used
    __crash_threshold_seconds = 5

    def __launch_program(self, with_terminal=False):
        def proceed(sandbox_override, exec_path):
            program = self.program
            if exec_path and exec_path != self.program.get("path"):
                program = {**self.program, "path": exec_path}
            timing = {}

            def _run():
                timing["start"] = time.monotonic()
                WineExecutor.run_program(
                    self.config,
                    program,
                    with_terminal,
                    sandbox_override=sandbox_override,
                )
                self.pop_actions.popdown()  # workaround #1640
                return True

            def done(result=False, error=False):
                self.__reset_buttons(result, error)
                start = timing.get("start")
                path = self.program.get("path")
                if (
                    not with_terminal
                    and self.window.settings.get_boolean("eagle-crash-detection")
                    and start is not None
                    and (time.monotonic() - start) < self.__crash_threshold_seconds
                    and path
                    and os.path.isfile(path)
                ):
                    self.__offer_eagle_scan(path)

            self.window.show_toast(_('Launching "{0}"…').format(self.program["name"]))
            RunAsync(_run, callback=done)
            self.__reset_buttons()

        guard_sandbox_launch(
            self.window, self.config, self.program.get("path"), proceed
        )

    def __offer_eagle_scan(self, path):
        dialog = Adw.MessageDialog.new(
            self.window,
            _("Did the app close unexpectedly?"),
            _(
                '"{0}" closed right after starting. Scan it with Eagle to check '
                "for missing dependencies, packers or known threats?"
            ).format(self.program["name"]),
        )

        icon = Gtk.Image.new_from_icon_name("com.usebottles.eagle-symbolic")
        icon.set_pixel_size(48)
        icon.set_margin_top(6)
        dialog.set_extra_child(icon)

        dialog.add_response("dismiss", _("Not Now"))
        dialog.add_response("scan", _("Scan with Eagle"))
        dialog.set_response_appearance("scan", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("scan")

        def on_response(_dialog, response):
            if response == "scan":
                self.view_bottle.analyze_with_eagle(path)

        dialog.connect("response", on_response)
        dialog.present()

    @staticmethod
    def __file_sha256(path):
        digest = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            return None
        return digest.hexdigest()

    def __eagle_security_check(self, path):
        """Worker thread: return Security findings for the program, or [] if it
        is clean (cached by size+mtime) or the user has trusted its hash."""
        try:
            stat = os.stat(path)
        except OSError:
            return []
        signature = {"size": stat.st_size, "mtime": int(stat.st_mtime)}

        cache = self.program.get("eagle_scan") or {}
        if (
            cache.get("clean")
            and cache.get("size") == signature["size"]
            and cache.get("mtime") == signature["mtime"]
        ):
            return []

        findings = EagleManager(self.config).security_scan(path)
        if not findings:
            # remember the clean result so we don't rescan an unchanged file
            self.program["eagle_scan"] = {**signature, "clean": True}
            self.config = self.manager.update_config(
                config=self.config,
                key=self.program["id"],
                value=self.program,
                scope="External_Programs",
            ).data["config"]
            return []

        # flagged: allow silently if the user previously trusted this exact file
        digest = self.__file_sha256(path)
        if digest and digest in (
            DataManager().get(UserDataKeys.TrustedExecutables, []) or []
        ):
            return []
        return findings

    def __show_security_advisory(self, findings, path, with_terminal):
        self.__reset_buttons()
        names = ", ".join(dict.fromkeys(f["name"] for f in findings))

        dialog = Adw.MessageDialog.new(
            self.window,
            _("Potential threat detected"),
            _(
                '"{0}" matches patterns associated with malware ({1}). Bottles '
                "strongly advises against running it."
            ).format(self.program["name"], names),
        )
        dialog.add_response("cancel", _("Do Not Run"))
        dialog.add_response("run", _("Run Anyway"))
        dialog.set_response_appearance("run", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")

        trust_check = Gtk.CheckButton.new_with_label(
            _("Trust this file and do not warn again")
        )
        dialog.set_extra_child(trust_check)

        def on_response(_dialog, response):
            if response != "run":
                return
            if trust_check.get_active():
                digest = self.__file_sha256(path)
                if digest:
                    DataManager().set(
                        UserDataKeys.TrustedExecutables, digest, of_type=list
                    )
            self.__launch_program(with_terminal)

        dialog.connect("response", on_response)
        dialog.present()

    def run_steam(self, _widget):
        self.manager.steam_manager.launch_app(self.config.CompatData)
        self.window.show_toast(
            _('Launching "{0}" with Steam…').format(self.program["name"])
        )
        self.pop_actions.popdown()  # workaround #1640

    def stop_process(self, widget):
        self.window.show_toast(_('Stopping "{0}"…').format(self.program["name"]))
        widget.set_sensitive(False)

        def task():
            if self.config.Parameters.sandbox:
                # winedbg cannot reach processes running inside the dedicated
                # sandbox, so stop the bottle's sandbox launchers instead.
                WineServer(self.config).force_kill()
            else:
                WineDbg(self.config).kill_process(self.executable)

        # run off the main loop so the UI never freezes while the (possibly
        # blocking) stop command runs
        RunAsync(task, callback=self.__reset_buttons)

    @GtkUtils.run_in_main_loop
    def update_programs(self, _result=False, _error=False):
        self.view_bottle.update_programs(config=self.config)

    def uninstall_program(self, _widget):
        uninstaller = Uninstaller(self.config)

        def update(_result=False, _error=False):
            if not _error:
                ManagerUtils.remove_desktop_entry(self.config, self.program)
            self.view_bottle.update_programs(config=self.config, force_update=True)

        RunAsync(
            task_func=uninstaller.from_name,
            callback=update,
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
        if not ManagerUtils.remove_desktop_entry(self.config, self.program):
            self.window.show_toast(
                _('Could not remove the desktop entry for "{0}"').format(
                    self.program["name"]
                )
            )
            return
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

            old_program = dict(self.program)
            had_desktop_entry = ManagerUtils.has_desktop_entry(self.config, old_program)
            if had_desktop_entry is None:
                self.window.show_toast(
                    _('Could not access the desktop entry for "{0}"').format(old_name)
                )
                return

            new_program = dict(self.program)
            new_program["name"] = new_name

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

            def apply_rename():
                self.program = new_program
                self.config = self.manager.update_config(
                    config=self.config,
                    key=self.program["id"],
                    value=self.program,
                    scope="External_Programs",
                ).data["config"]
                RunAsync(async_work, callback=ui_update)

            def desktop_entry_failed():
                self.window.show_toast(
                    _('Could not update the desktop entry for "{0}"').format(old_name)
                )

            if not had_desktop_entry:
                apply_rename()
                return

            def desktop_entry_created():
                if not ManagerUtils.remove_desktop_entry(self.config, old_program):
                    ManagerUtils.remove_desktop_entry(self.config, new_program)
                    desktop_entry_failed()
                    return
                apply_rename()

            ManagerUtils.create_desktop_entry(
                config=self.config,
                program=new_program,
                on_created=desktop_entry_created,
                on_failed=desktop_entry_failed,
                on_cancelled=desktop_entry_failed,
            )

        dialog = RenameDialog(self.window, on_save=func, name=self.program["name"])
        dialog.present()

    def browse_program_folder(self, _widget):
        ManagerUtils.open_filemanager(
            config=self.config, path_type="custom", custom_path=self.program["folder"]
        )
        self.pop_actions.popdown()  # workaround #1640

    def add_entry(self, _widget):
        def _on_desktop_entry_created(data: Result | None = None) -> None:
            if data and data.data and data.data.get("method") == "manual":
                if data.status:
                    self.__set_desktop_entry_state(True)
                ProgramEntry.__show_desktop_entry_fallback(self, data)
                return
            if not data or not data.status:
                self.window.show_toast(
                    _('Could not create a Desktop Entry for "{0}"').format(
                        self.program["name"]
                    )
                )
                return
            self.__set_desktop_entry_state(True)
            self.window.show_toast(
                _('Desktop Entry created for "{0}"').format(self.program["name"])
            )

        ManagerUtils.create_desktop_entry(
            config=self.config,
            program=self.program,
            callback=_on_desktop_entry_created,
        )

    def manage_entry(self, widget):
        if self.__desktop_entry_exists:
            self.remove_entry(widget)
            return
        self.add_entry(widget)

    def remove_entry(self, _widget):
        self.btn_add_entry.set_sensitive(False)
        RunAsync(
            lambda: ManagerUtils.remove_desktop_entry(self.config, self.program),
            callback=self.__desktop_entry_removed,
        )

    def __desktop_entry_removed(self, removed, error):
        if error is not None or not removed:
            self.btn_add_entry.set_sensitive(True)
            self.window.show_toast(
                _('Could not remove the desktop entry for "{0}"').format(
                    self.program["name"]
                )
            )
            return

        self.__set_desktop_entry_state(False)
        self.window.show_toast(
            _('Desktop Entry removed for "{0}"').format(self.program["name"])
        )

    def __desktop_entry_state_ready(self, exists, error):
        self.__desktop_entry_query_pending = False
        if error is not None or exists is None:
            self.btn_add_entry.set_sensitive(True)
            return
        self.__set_desktop_entry_state(exists)

    def __refresh_desktop_entry_state(self, popover, _property=None):
        if (
            self.is_steam
            or self.__desktop_entry_query_pending
            or not popover.get_visible()
        ):
            return
        self.__desktop_entry_query_pending = True
        self.btn_add_entry.set_sensitive(False)
        RunAsync(
            lambda: ManagerUtils.has_desktop_entry(self.config, self.program),
            callback=self.__desktop_entry_state_ready,
        )

    def __set_desktop_entry_state(self, exists):
        self.__desktop_entry_exists = exists
        label = _("Remove Desktop Entry") if exists else _("Add Desktop Entry")
        self.btn_add_entry.set_property("text", label)
        self.btn_add_entry.set_sensitive(True)

    def __show_desktop_entry_fallback(self, result: Result) -> None:
        title, description, command = ProgramEntry.__desktop_entry_fallback_content(
            result, os.environ.get("FLATPAK_ID")
        )

        dialog = Adw.MessageDialog.new(self.window, title, description)
        if command:
            command_box = Gtk.Box(spacing=6)
            command_box.set_margin_top(6)

            command_entry = Gtk.Entry()
            command_entry.set_editable(False)
            command_entry.set_hexpand(True)
            command_entry.set_text(command)
            command_entry.add_css_class("monospace")

            copy_button = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
            copy_button.set_tooltip_text(_("Copy command"))

            def copy_command(*_args):
                display = Gdk.Display.get_default()
                if display:
                    display.get_clipboard().set_content(
                        Gdk.ContentProvider.new_for_value(command)
                    )

            copy_button.connect("clicked", copy_command)
            command_box.append(command_entry)
            command_box.append(copy_button)
            dialog.set_extra_child(command_box)

        dialog.add_response("close", _("_Close"))
        dialog.present()

    @staticmethod
    def __desktop_entry_fallback_content(
        result: Result, app_id: str | None
    ) -> tuple[str, str, str | None]:
        if result.status:
            title = _("Desktop Entry Created Manually")
            if app_id:
                description = _(
                    "The desktop portal was unavailable, so Bottles used its "
                    "manual fallback. If the entry does not appear, close "
                    "Bottles, run the command below, reopen Bottles and try again."
                )
            else:
                description = _(
                    "The desktop portal was unavailable, so Bottles used its "
                    "manual fallback. If the entry does not appear, check the "
                    "permissions of your desktop entry folders and try again."
                )
        else:
            title = _("Desktop Entry Could Not Be Created")
            if app_id:
                description = _(
                    "The desktop portal and the manual fallback both failed. "
                    "Close Bottles, run the command below, reopen Bottles and "
                    "try again."
                )
            else:
                description = _(
                    "The desktop portal and the manual fallback both failed. "
                    "Check that your desktop entry folders are writable and "
                    "try again."
                )

        command = None
        if app_id:
            command = (
                "flatpak override --user "
                "--filesystem=xdg-data/applications:create "
                f"--filesystem=xdg-desktop:create {app_id}"
            )
        return title, description, command

    def show_file_associations(self, _widget):
        self.pop_actions.popdown()

        def save(extensions):
            program = dict(self.program)
            program["file_extensions"] = extensions

            def on_created():
                self.program = program
                self.config = self.save_program()
                self.window.show_toast(
                    _('File associations updated for "{0}"').format(
                        self.program["name"]
                    )
                )

            def on_failed():
                self.window.show_toast(
                    _('Could not update file associations for "{0}"').format(
                        self.program["name"]
                    )
                )

            ManagerUtils.create_desktop_entry(
                config=self.config,
                program=program,
                on_created=on_created,
                on_failed=on_failed,
                on_cancelled=on_failed,
            )

        dialog = FileAssociationsDialog(
            self.window,
            self.program.get("file_extensions", []),
            save,
        )
        dialog.present()

    def add_to_library(self, _widget):
        def update(_result, _error=False):
            self.window.update_library()
            self.window.show_toast(
                _('"{0}" added to your library').format(self.program["name"])
            )

        def add_to_library():
            library_manager = LibraryManager()
            data = {
                "bottle": {"name": self.config.Name, "path": self.config.Path},
                "name": self.program["name"],
                "id": str(self.program["id"]),
            }

            if self.is_steam:
                data["bottle"]["name"] = self.config.CompatData
                data["steam"] = True
            else:
                self.save_program()
                icon_job = getattr(self, "_ProgramEntry__program_icon_job", None)
                if icon_job is not None:
                    icon_job.join()
                icon = self.program.get("icon")
                icon_path = getattr(self, "_ProgramEntry__program_icon_path", None)
                if not (isinstance(icon, str) and os.path.isfile(icon)):
                    if icon_path and os.path.isfile(icon_path):
                        icon = icon_path
                    else:
                        icon = ManagerUtils.extract_icon(
                            self.config, self.program["name"], self.program["path"]
                        )
                data["icon"] = icon

            library_manager.add_to_library(data, self.config)

        self.btn_add_library.set_visible(False)
        self.btn_add_steam_library.set_visible(False)
        RunAsync(add_to_library, update)

    def add_to_steam(self, _widget):
        def update(result, _error=False):
            if result.ok:
                self.window.show_toast(
                    _('"{0}" added to your Steam library').format(self.program["name"])
                )

        steam_manager = SteamManager(self.config)
        RunAsync(
            steam_manager.add_shortcut,
            update,
            program_name=self.program["name"],
            program_path=self.program["path"],
        )

    def update_playtime(self, playtime_service):
        """
        Update the program subtitle with playtime information.

        Args:
            playtime_service: Instance of PlaytimeService to fetch and format data.
        """
        if not playtime_service or not playtime_service.is_enabled():
            return

        program_path = self.program.get("path", "")
        if not program_path:
            return

        try:
            # Use bottle name as bottle_id, matching what backend uses
            bottle_id = self.config.Name
            bottle_path = self.config.Path

            record = playtime_service.get_program_playtime(
                bottle_id, bottle_path, self.program["name"], program_path
            )
            subtitle = playtime_service.format_subtitle(record)
            self.set_subtitle(subtitle)
        except Exception as e:
            from bottles.backend.logger import Logger

            logging = Logger()
            logging.error(
                f"Failed to update playtime for {self.program['name']}: {e}", exc=e
            )
