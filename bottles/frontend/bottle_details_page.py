# bottle_details_page.py
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

import uuid
from datetime import datetime
from gettext import gettext as _

from gi.repository import Gtk, Gio, Adw, Gdk, GLib, Xdp

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.terminal import TerminalUtils
from bottles.backend.utils.threading import RunAsync
from bottles.backend.wine.cmd import CMD
from bottles.backend.wine.control import Control
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.explorer import Explorer
from bottles.backend.wine.regedit import Regedit
from bottles.backend.wine.taskmgr import Taskmgr
from bottles.backend.wine.uninstaller import Uninstaller
from bottles.backend.wine.wineboot import WineBoot
from bottles.backend.wine.winecfg import WineCfg
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.wineserver import WineServer
from bottles.frontend.common import open_doc_url
from bottles.frontend.filters import add_executable_filters, add_all_filters
from bottles.frontend.gtk import GtkUtils
from bottles.frontend.program_row import ProgramRow


@Gtk.Template(resource_path="/com/usebottles/bottles/bottle-details-page.ui")
class BottleDetailsPage(Adw.PreferencesPage):
    __gtype_name__ = "BottleDetailsPage"
    __registry = []

    # region Widgets
    label_runner = Gtk.Template.Child()
    label_state = Gtk.Template.Child()
    label_environment = Gtk.Template.Child()
    label_arch = Gtk.Template.Child()
    install_programs = Gtk.Template.Child()
    add_shortcuts = Gtk.Template.Child()
    btn_execute = Gtk.Template.Child()
    popover_exec_settings = Gtk.Template.Child()
    exec_arguments = Gtk.Template.Child()
    exec_terminal = Gtk.Template.Child()
    row_winecfg = Gtk.Template.Child()
    row_preferences = Gtk.Template.Child()
    row_dependencies = Gtk.Template.Child()
    row_taskmanager = Gtk.Template.Child()
    row_debug = Gtk.Template.Child()
    row_explorer = Gtk.Template.Child()
    row_cmd = Gtk.Template.Child()
    row_taskmanager_legacy = Gtk.Template.Child()
    row_controlpanel = Gtk.Template.Child()
    row_uninstaller = Gtk.Template.Child()
    row_regedit = Gtk.Template.Child()
    btn_shutdown = Gtk.Template.Child()
    btn_reboot = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_forcestop = Gtk.Template.Child()
    btn_nv_forcestop = Gtk.Template.Child()
    btn_update = Gtk.Template.Child()
    btn_toggle_removed = Gtk.Template.Child()
    btn_delete = Gtk.Template.Child()
    btn_flatpak_doc = Gtk.Template.Child()
    label_name = Gtk.Template.Child()
    dot_versioning = Gtk.Template.Child()
    grid_versioning = Gtk.Template.Child()
    group_programs = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    row_no_programs = Gtk.Template.Child()
    bottom_bar = Gtk.Template.Child()
    drop_overlay = Gtk.Template.Child()
    # endregion

    content = Gdk.ContentFormats.new_for_gtype(Gdk.FileList)
    target = Gtk.DropTarget(formats=content, actions=Gdk.DragAction.COPY)

    style_provider = Gtk.CssProvider()

    def __init__(self, details, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = details.window
        self.manager = details.window.manager
        self.stack_bottle = details.stack_bottle
        self.leaflet = details.leaflet
        self.details = details
        self.config = config
        self.show_hidden = False

        self.target.connect("drop", self.on_drop)
        self.add_controller(self.target)
        self.target.connect("enter", self.on_enter)
        self.target.connect("leave", self.on_leave)

        self.add_shortcuts.connect("clicked", self.add)
        self.install_programs.connect("clicked", self.__change_page, "installers")
        self.btn_execute.connect("clicked", self.run_executable)
        self.popover_exec_settings.connect("closed", self.__run_executable_with_args)
        self.row_preferences.connect("activated", self.__change_page, "preferences")
        self.row_dependencies.connect("activated", self.__change_page, "dependencies")
        self.row_taskmanager.connect("activated", self.__change_page, "taskmanager")
        self.row_winecfg.connect("activated", self.run_winecfg)
        self.row_debug.connect("activated", self.run_debug)
        self.row_explorer.connect("activated", self.run_explorer)
        self.row_cmd.connect("activated", self.run_cmd)
        self.row_taskmanager_legacy.connect("activated", self.run_taskmanager)
        self.row_controlpanel.connect("activated", self.run_controlpanel)
        self.row_uninstaller.connect("activated", self.run_uninstaller)
        self.row_regedit.connect("activated", self.run_regedit)
        self.btn_browse.connect("clicked", self.run_browse)
        self.btn_delete.connect("clicked", self.__confirm_delete)
        self.btn_shutdown.connect("clicked", self.wineboot, 2)
        self.btn_reboot.connect("clicked", self.wineboot, 1)
        self.btn_forcestop.connect("clicked", self.wineboot, 0)
        self.btn_nv_forcestop.connect("clicked", self.wineboot, -2)
        self.btn_update.connect("clicked", self.__scan_programs)
        self.btn_toggle_removed.connect("clicked", self.__toggle_removed)
        self.btn_flatpak_doc.connect(
            "clicked", open_doc_url, "flatpak/black-screen-or-silent-crash"
        )

    def __change_page(self, _widget, page_name):
        """
        This function try to change the page based on user choice, if
        the page is not available, it will show the "bottle" page.
        """
        if page_name == "taskmanager":
            self.details.view_taskmanager.update(config=self.config)
        try:
            self.stack_bottle.set_visible_child_name(page_name)
            self.leaflet.navigate(Adw.NavigationDirection.FORWARD)
        except:  # pylint: disable=bare-except
            pass

    def on_drop(self, drop_target, value: Gdk.FileList, x, y, user_data=None):
        self.drop_overlay.set_visible(False)
        files: list[Gio.File] = value.get_files()
        args = ""
        file = files[0]
        if (
            ".exe" in file.get_basename().split("/")[-1]
            or ".msi" in file.get_basename().split("/")[-1]
        ):
            executor = WineExecutor(
                self.config,
                exec_path=file.get_path(),
                args=args,
                terminal=self.config.run_in_terminal,
            )

            def callback(a, b):
                self.update_programs()

            RunAsync(executor.run, callback)

        else:
            self.window.show_toast(
                _('File "{0}" is not a .exe or .msi file').format(
                    file.get_basename().split("/")[-1]
                )
            )

    def on_enter(self, drop_target, x, y):
        self.drop_overlay.set_visible(True)
        return Gdk.DragAction.COPY

    def on_leave(self, drop_target):
        self.drop_overlay.set_visible(False)

    def set_config(self, config: BottleConfig):
        self.config = config
        self.__update_by_env()

        # set update_date
        update_date = datetime.strptime(self.config.Update_Date, "%Y-%m-%d %H:%M:%S.%f")
        update_date = update_date.strftime("%b %d %Y %H:%M:%S")
        self.label_name.set_tooltip_text(_("Updated: %s" % update_date))

        # set arch
        self.label_arch.set_text((self.config.Arch or "n/a").capitalize())

        # set name and runner
        self.label_name.set_text(self.config.Name)
        self.label_runner.set_text(self.config.Runner)

        # set environment
        self.label_environment.set_text(_(self.config.Environment))

        # set versioning
        self.dot_versioning.set_visible(self.config.Versioning)
        self.grid_versioning.set_visible(self.config.Versioning)
        self.label_state.set_text(str(self.config.State))

        if (
            config.Runner not in self.manager.runners_available
            and not self.config.Environment == "Steam"
        ):
            self.__alert_missing_runner()

        # update programs list
        self.update_programs()

    def add(self, widget=False):
        """
        This function popup the add program dialog to the user. It
        will also update the bottle configuration, appending the
        path to the program picked by the user.
        The file chooser path is set to the bottle path by default.
        """

        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            path = dialog.get_file().get_path()
            basename = dialog.get_file().get_basename()

            _uuid = str(uuid.uuid4())
            _program = {
                "executable": basename,
                "name": basename[:-4],
                "path": path,
                "id": _uuid,
                "folder": ManagerUtils.get_exe_parent_dir(self.config, path),
            }
            self.config = self.manager.update_config(
                config=self.config,
                key=_uuid,
                value=_program,
                scope="External_Programs",
                fallback=True,
            ).data["config"]
            self.update_programs(config=self.config, force_add=_program)
            self.window.show_toast(_('"{0}" added').format(basename[:-4]))

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Executable"),
            action=Gtk.FileChooserAction.OPEN,
            parent=self.window,
            accept_label=_("Add"),
        )

        add_executable_filters(dialog)
        add_all_filters(dialog)
        dialog.set_modal(True)
        dialog.set_current_folder(
            Gio.File.new_for_path(ManagerUtils.get_bottle_path(self.config))
        )
        dialog.connect("response", set_path)
        dialog.show()

    def update_programs(
        self, config: BottleConfig | None = None, force_add: dict = None
    ):
        """
        This function update the programs lists.
        """
        if config:
            if not isinstance(config, BottleConfig):
                raise TypeError(
                    "config param need BottleConfig type, but it was %s" % type(config)
                )
            self.config = config

        if not force_add:
            GLib.idle_add(self.empty_list)

        def new_program(
            _program, check_boot=None, is_steam=False, wineserver_status=False
        ):
            if check_boot is None:
                check_boot = wineserver_status

            self.add_program(
                ProgramRow(
                    self.window,
                    self.config,
                    _program,
                    is_steam=is_steam,
                    check_boot=check_boot,
                )
            )

        if force_add:
            wineserver_status = WineServer(self.config).is_alive()
            new_program(force_add, None, False, wineserver_status)
            return

        def process_programs():
            wineserver_status = WineServer(self.config).is_alive()
            programs = self.manager.get_programs(self.config)
            programs = sorted(programs, key=lambda p: p.get("name", "").lower())
            handled = 0

            if self.config.Environment == "Steam":
                GLib.idle_add(new_program, {"name": self.config.Name}, None, True)
                handled += 1

            for program in programs:
                if program.get("removed"):
                    if self.show_hidden:
                        GLib.idle_add(
                            new_program, program, None, False, wineserver_status
                        )
                        handled += 1
                    continue
                GLib.idle_add(new_program, program, None, False, wineserver_status)
                handled += 1

            self.row_no_programs.set_visible(handled == 0)

        process_programs()

    def add_program(self, widget):
        self.__registry.append(widget)
        self.group_programs.remove(self.bottom_bar)  # Remove the bottom_bar
        self.group_programs.add(widget)
        self.group_programs.add(
            self.bottom_bar
        )  # Add the bottom_bar back to the bottom

    def __toggle_removed(self, widget=False):
        """
        This function toggle the show_hidden variable.
        """
        if self.show_hidden:
            self.btn_toggle_removed.set_property("text", _("Show Hidden Programs"))
        else:
            self.btn_toggle_removed.set_property("text", _("Hide Hidden Programs"))
        self.show_hidden = not self.show_hidden
        self.update_programs(config=self.config)

    def __scan_programs(self, widget=False):
        self.update_programs(config=self.config)

    def empty_list(self):
        """
        This function empty the programs list.
        """
        for r in self.__registry:
            self.group_programs.remove(r)
        self.__registry = []

    def __run_executable_with_args(self, widget):
        """
        This function saves updates the run arguments for the current session.
        """
        args = self.exec_arguments.get_text()
        self.config.session_arguments = args
        self.config.run_in_terminal = self.exec_terminal.get_active()

    def run_executable(self, widget, args=False):
        """
        This function pop up the dialog to run an executable.
        The file will be executed by the runner after the
        user confirmation.
        """

        def show_chooser(*_args):
            self.window.settings.set_boolean("show-sandbox-warning", False)

            def execute(_dialog, response):
                if response != Gtk.ResponseType.ACCEPT:
                    return

                self.window.show_toast(
                    _('Launching "{0}"…').format(dialog.get_file().get_basename())
                )

                executor = WineExecutor(
                    self.config,
                    exec_path=dialog.get_file().get_path(),
                    args=self.config.get("session_arguments"),
                    terminal=self.config.get("run_in_terminal"),
                )

                def callback(a, b):
                    self.update_programs()

                RunAsync(executor.run, callback)

            dialog = Gtk.FileChooserNative.new(
                title=_("Select Executable"),
                action=Gtk.FileChooserAction.OPEN,
                parent=self.window,
                accept_label=_("Run"),
            )

            add_executable_filters(dialog)
            add_all_filters(dialog)
            dialog.set_modal(True)
            dialog.connect("response", execute)
            dialog.show()

        if Xdp.Portal.running_under_sandbox():
            if self.window.settings.get_boolean("show-sandbox-warning"):
                dialog = Adw.MessageDialog.new(
                    self.window,
                    _("Be Aware of Sandbox"),
                    _(
                        "Bottles is running in a sandbox, a restricted permission environment needed to keep you safe. If the program won't run, consider moving inside the bottle (3 dots icon on the top), then launch from there."
                    ),
                )
                dialog.add_response("dismiss", _("_Dismiss"))
                dialog.connect("response", show_chooser)
                dialog.present()
            else:
                show_chooser()

    def __confirm_delete(self, widget):
        """
        This function pop up to delete confirm dialog. If user confirm
        it will ask the manager to delete the bottle and will return
        to the bottles list.
        """

        def handle_response(_widget, response_id):
            if response_id == "ok":
                RunAsync(self.manager.delete_bottle, config=self.config)
                self.window.page_list.disable_bottle(self.config)
            _widget.destroy()

        dialog = Adw.MessageDialog.new(
            self.window,
            _(
                'Are you sure you want to permanently delete "{}"?'.format(
                    self.config["Name"]
                )
            ),
            _(
                "This will permanently delete all programs and settings associated with it."
            ),
        )
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("ok", _("_Delete"))
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", handle_response)
        dialog.present()

    def __alert_missing_runner(self):
        """
        This function pop up a dialog which alert the user that the runner
        specified in the bottle configuration is missing.
        """

        def handle_response(_widget, response_id):
            _widget.destroy()

        dialog = Adw.MessageDialog.new(
            self.window,
            _("Missing Runner"),
            _(
                "The runner requested by this bottle is missing. Install it through \
the Bottles preferences or choose a new one to run applications."
            ),
        )
        dialog.add_response("ok", _("_Dismiss"))
        dialog.connect("response", handle_response)
        dialog.present()

    def __update_by_env(self):
        widgets = [self.row_uninstaller, self.row_regedit]
        for widget in widgets:
            widget.set_visible(True)

    """
    The following functions are used like wrappers for the
    runner utilities.
    """

    def run_winecfg(self, widget):
        program = WineCfg(self.config)
        RunAsync(program.launch)

    def run_debug(self, widget):
        program = WineDbg(self.config)
        RunAsync(program.launch_terminal)

    def run_browse(self, widget):
        ManagerUtils.open_filemanager(self.config)

    def run_explorer(self, widget):
        program = Explorer(self.config)
        RunAsync(program.launch)

    def run_cmd(self, widget):
        program = CMD(self.config)
        RunAsync(program.launch_terminal)

    @staticmethod
    def run_snake(widget, event):
        if event.button == 2:
            RunAsync(TerminalUtils().launch_snake)

    def run_taskmanager(self, widget):
        program = Taskmgr(self.config)
        RunAsync(program.launch)

    def run_controlpanel(self, widget):
        program = Control(self.config)
        RunAsync(program.launch)

    def run_uninstaller(self, widget):
        program = Uninstaller(self.config)
        RunAsync(program.launch)

    def run_regedit(self, widget):
        program = Regedit(self.config)
        RunAsync(program.launch)

    def wineboot(self, widget, status):
        @GtkUtils.run_in_main_loop
        def reset(result=None, error=False):
            widget.set_sensitive(True)

        def handle_response(_widget, response_id):
            if response_id == "ok":
                RunAsync(wineboot.send_status, callback=reset, status=status)
            else:
                reset()
            _widget.destroy()

        wineboot = WineBoot(self.config)
        widget.set_sensitive(False)

        if status in [-2, 0]:
            dialog = Adw.MessageDialog.new(
                self.window,
                _("Are you sure you want to force stop all processes?"),
                _("This can cause data loss, corruption, and programs to malfunction."),
            )
            dialog.add_response("cancel", _("_Cancel"))
            dialog.add_response("ok", _("Force _Stop"))
            dialog.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.connect("response", handle_response)
            dialog.present()
