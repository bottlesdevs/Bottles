# bottle_details.py
#
# Copyright 2022 brombinmirko <send@mirko.pm>
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

import os
import re
import webbrowser
from datetime import datetime
from gettext import gettext as _
from gi.repository import Gtk, Adw, Gdk

from bottles.frontend.utils.threading import RunAsync  # pyright: reportMissingImports=false
from bottles.frontend.utils.common import open_doc_url

from bottles.backend.runner import Runner
from bottles.backend.managers.backup import BackupManager
from bottles.backend.utils.terminal import TerminalUtils
from bottles.backend.utils.manager import ManagerUtils

from bottles.frontend.widgets.executable import ExecButton

from bottles.frontend.windows.filechooser import FileChooser
from bottles.frontend.windows.runargs import RunArgsDialog
from bottles.frontend.windows.generic import MessageDialog
from bottles.frontend.windows.duplicate import DuplicateDialog
from bottles.frontend.windows.upgradeversioning import UpgradeVersioningDialog

from bottles.backend.wine.uninstaller import Uninstaller
from bottles.backend.wine.winecfg import WineCfg
from bottles.backend.wine.winedbg import WineDbg
from bottles.backend.wine.wineboot import WineBoot
from bottles.backend.wine.cmd import CMD
from bottles.backend.wine.taskmgr import Taskmgr
from bottles.backend.wine.control import Control
from bottles.backend.wine.regedit import Regedit
from bottles.backend.wine.explorer import Explorer
from bottles.backend.wine.executor import WineExecutor


@Gtk.Template(resource_path='/com/usebottles/bottles/details-bottle.ui')
class BottleView(Adw.PreferencesPage):
    __gtype_name__ = 'DetailsBottle'
    __registry = []

    # region Widgets
    label_runner = Gtk.Template.Child()
    label_state = Gtk.Template.Child()
    label_environment = Gtk.Template.Child()
    label_arch = Gtk.Template.Child()
    btn_execute = Gtk.Template.Child()
    btn_run_args = Gtk.Template.Child()
    row_winecfg = Gtk.Template.Child()
    row_debug = Gtk.Template.Child()
    row_explorer = Gtk.Template.Child()
    row_cmd = Gtk.Template.Child()
    row_taskmanager = Gtk.Template.Child()
    row_controlpanel = Gtk.Template.Child()
    row_uninstaller = Gtk.Template.Child()
    row_regedit = Gtk.Template.Child()
    btn_shutdown = Gtk.Template.Child()
    btn_reboot = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_killall = Gtk.Template.Child()
    btn_backup_config = Gtk.Template.Child()
    btn_backup_full = Gtk.Template.Child()
    btn_duplicate = Gtk.Template.Child()
    btn_delete = Gtk.Template.Child()
    btn_flatpak_doc = Gtk.Template.Child()
    box_history = Gtk.Template.Child()
    check_terminal = Gtk.Template.Child()
    label_name = Gtk.Template.Child()
    grid_versioning = Gtk.Template.Child()
    group_programs = Gtk.Template.Child()
    extra_separator = Gtk.Template.Child()
    actions = Gtk.Template.Child()
    row_no_programs = Gtk.Template.Child()
    pop_run = Gtk.Template.Child()
    # endregion

    content = Gdk.ContentFormats.new_for_gtype(Gdk.FileList)
    target = Gtk.DropTarget(formats=content, actions=Gdk.DragAction.COPY)

    def __init__(self, details, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = details.window
        self.manager = details.window.manager
        self.config = config

        self.target.connect('drop', self.on_drop)
        self.window.add_controller(self.target)
        #self.target.connect('enter', on_enter)
        #self.target.connect('leave', on_leave)

        self.btn_execute.connect("clicked", self.run_executable)
        self.btn_run_args.connect("clicked", self.__run_executable_with_args)
        self.row_winecfg.connect("activated", self.run_winecfg)
        self.row_debug.connect("activated", self.run_debug)
        self.row_explorer.connect("activated", self.run_explorer)
        self.row_cmd.connect("activated", self.run_cmd)
        self.row_taskmanager.connect("activated", self.run_taskmanager)
        self.row_controlpanel.connect("activated", self.run_controlpanel)
        self.row_uninstaller.connect("activated", self.run_uninstaller)
        self.row_regedit.connect("activated", self.run_regedit)
        self.btn_browse.connect("clicked", self.run_browse)
        self.btn_delete.connect("clicked", self.__confirm_delete)
        self.btn_shutdown.connect("clicked", self.wineboot, 2)
        self.btn_reboot.connect("clicked", self.wineboot, 1)
        self.btn_killall.connect("clicked", self.wineboot, 0)
        self.btn_backup_config.connect("clicked", self.__backup, "config")
        self.btn_backup_full.connect("clicked", self.__backup, "full")
        self.btn_duplicate.connect("clicked", self.__duplicate)
        self.btn_flatpak_doc.connect(
            "clicked",
            open_doc_url,
            "flatpak/black-screen-or-silent-crash"
        )

        if "FLATPAK_ID" in os.environ:
            '''
            If Flatpak, show the btn_flatpak_doc widget to reach
            the documentation on how to expose directories
            '''
            self.btn_flatpak_doc.set_visible(True)

        self.__update_latest_executables()

    def on_drop(self, drop_target, value: Gdk.FileList, x, y, user_data=None):
        files: List[Gio.File] = value.get_files()
        args=""
        # Loop through the files and print their names.
        for file in files:
            print(file.get_path())
        file=files[0]
        print(file.get_path())
        print(file.get_basename())
        executor = WineExecutor(
            self.config,
            exec_path=file.get_path(),
            args=args,
            terminal=self.check_terminal.get_active(),
        )
        RunAsync(executor.run, self.do_update_programs)
        self.manager.update_config(
            config=self.config,
            key="Latest_Executables",
            value=_execs + [{
                "name": file.get_basename().split("/")[-1],
                "file": file.get_path(),
                "args": args
            }]
        )

        self.__update_latest_executables()

    def set_config(self, config):
        self.config = config
        self.__update_by_env()

        # set update_date
        update_date = datetime.strptime(self.config.get("Update_Date"), "%Y-%m-%d %H:%M:%S.%f")
        update_date = update_date.strftime("%b %d %Y %H:%M:%S")
        self.label_name.set_tooltip_text(_("Updated: %s" % update_date))

        # set arch
        self.label_arch.set_text(self.config.get("Arch", "n/a").capitalize())

        # set name and runner
        self.label_name.set_text(self.config.get("Name"))
        self.label_runner.set_text(self.config.get("Runner"))

        # set environment
        self.label_environment.set_text(_(self.config.get("Environment")))

        # set versioning
        self.grid_versioning.set_visible(self.config.get("Versioning"))
        self.label_state.set_text(str(self.config.get("State")))

        self.__set_steam_rules()

        # check for old versioning system enabled
        if config["Versioning"]:
            self.__upgrade_versioning()

    def update_programs(self, widget=False, config=None):
        if config is None:
            config = self.config

        self.window.page_details.update_programs(config)

    def add_program(self, widget):
        self.__registry.append(widget)
        self.group_programs.add(widget)

    def empty_list(self):
        """
        This function empty the programs list.
        """
        for r in self.__registry:
            self.group_programs.remove(r)
        self.__registry = []

    def __run_executable_with_args(self, widget):
        """
        This function pop up the dialog to run an executable with
        custom arguments.
        """
        new_window = RunArgsDialog(self)
        new_window.present()

    def run_executable(self, widget, args=False):
        """
        This function pop up the dialog to run an executable.
        The file will be executed by the runner after the
        user confirmation.
        """
        def show_chooser(*_args):
            self.window.settings.set_boolean("show-sandbox-warning", False)
            FileChooser(
                parent=self.window,
                title=_("Choose a Windows executable file"),
                action=Gtk.FileChooserAction.OPEN,
                buttons=(_("Cancel"), _("Run")),
                callback=self.__execute
            )

        if "FLATPAK_ID" in os.environ and self.window.settings.get_boolean("show-sandbox-warning"):
            dialog = Adw.MessageDialog.new(
                self.window,
                _("Be Aware of Sandbox"),
                _("Bottles is running in a sandbox, a restricted permission environment needed to keep you safe. If the program won't run, consider moving inside the bottle (3 dots icon on the top), then launch from there.")
            )
            dialog.add_response("ok", _("Ok"))
            dialog.connect("response", show_chooser)
            dialog.present()
        else:
            show_chooser()

    def do_update_programs(result, error=False):
        self.window.page_details.update_programs()

    def __execute(self, _dialog, response, file_dialog, args=""):

        if response == -3:
            _execs = self.config.get("Latest_Executables", [])
            _file = file_dialog.get_file()
            if not _file:
                return  # workaround #1653
            executor = WineExecutor(
                self.config,
                exec_path=_file.get_path(),
                args=args,
                terminal=self.check_terminal.get_active(),
            )
            RunAsync(executor.run, self.do_update_programs)
            self.manager.update_config(
                config=self.config,
                key="Latest_Executables",
                value=_execs + [{
                    "name": _file.get_basename().split("/")[-1],
                    "file": _file.get_path(),
                    "args": args
                }]
            )

        self.__update_latest_executables()

    def __update_latest_executables(self):
        """
        This function update the latest executables list.
        """
        while self.box_history.get_first_child() is not None:
            self.box_history.remove(self.box_history.get_first_child())

        _execs = self.config.get("Latest_Executables", [])[-5:]
        for exe in _execs:
            self.box_history.append(ExecButton(
                parent=self,
                data=exe,
                config=self.config
            ))

    def __backup(self, widget, backup_type):
        """
        This function pop up the file chooser where the user
        can select the path where to export the bottle backup.
        Use the backup_type param to export config or full.
        """
        title = _("Select the location where to save the backup config")
        hint = f"backup_{self.config.get('Path')}.yml"

        if backup_type == "full":
            title = _("Select the location where to save the backup archive")
            hint = f"backup_{self.config.get('Path')}.tar.gz"

        def finish(result, error=False):
            if result.status:
                self.window.show_toast(_("Backup created for '{0}'.").format(self.config["Name"]))
            else:
                self.window.show_toast(_("Backup failed for '{0}'.").format(self.config["Name"]))

        def set_path(_dialog, response, _file_dialog):
            if response == -3:
                _file = _file_dialog.get_file()
                RunAsync(
                    task_func=BackupManager.export_backup,
                    callback=finish,
                    window=self.window,
                    config=self.config,
                    scope=backup_type,
                    path=_file.get_path()
                )

        FileChooser(
            parent=self.window,
            title=title,
            action=Gtk.FileChooserAction.SAVE,
            buttons=(_("Cancel"), _("Export")),
            hint=hint,
            callback=set_path
        )

    def __duplicate(self, widget):
        """
        This function pop up the duplicate dialog, so the user can
        choose the new bottle name and perform duplication.
        """
        new_window = DuplicateDialog(self)
        new_window.present()

    def __upgrade_versioning(self):
        """
        This function pop up the upgrade versioning dialog, so the user can
        upgrade the versioning system from old Bottles built-in to FVS.
        """
        new_window = UpgradeVersioningDialog(self)
        new_window.present()

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
            _("Confirm"),
            _("Are you sure you want to delete this Bottle and all files?")
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("ok", _("Confirm"))
        dialog.connect("response", handle_response)
        dialog.present()

    def __update_by_env(self):
        widgets = [self.row_uninstaller, self.row_regedit]
        if self.config.get("Environment") == "Layered":
            for widget in widgets:
                widget.set_visible(False)
        else:
            for widget in widgets:
                widget.set_visible(True)

    '''
    The following functions are used like wrappers for the
    runner utilities.
    '''

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
        def reset(result=None, error=False):
            widget.set_sensitive(True)

        def handle_response(_widget, response_id):
            if response_id == "ok":
                RunAsync(wineboot.send_status, reset, status)
            else:
                reset()
            _widget.destroy()

        wineboot = WineBoot(self.config)
        widget.set_sensitive(False)

        if status == 0:
            dialog = Adw.MessageDialog.new(
                self.window,
                _("Confirm"),
                _("Are you sure you want to terminate all processes?\nThis can cause data loss.")
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("ok", _("Confirm"))
            dialog.connect("response", handle_response)
            dialog.present()

    def __set_steam_rules(self):
        status = False if self.config.get("Environment") == "Steam" else True

        for w in [self.btn_delete, self.btn_backup_full, self.btn_duplicate]:
            w.set_visible(status)
            w.set_sensitive(status)
