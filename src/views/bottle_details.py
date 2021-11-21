# bottle_details.py
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
import re
import webbrowser
from datetime import datetime
from gettext import gettext as _
from gi.repository import Gtk

from ..utils import RunAsync, GtkUtils

from ..backend.runner import Runner
from ..backend.backup import BackupManager
from ..backend.manager_utils import ManagerUtils

from ..widgets.program import ProgramEntry
from ..widgets.executable import ExecButton

from ..dialogs.runargs import RunArgsDialog
from ..dialogs.generic import MessageDialog
from ..dialogs.duplicate import DuplicateDialog


@Gtk.Template(resource_path='/com/usebottles/bottles/details-bottle.ui')
class BottleView(Gtk.ScrolledWindow):
    __gtype_name__ = 'DetailsBottle'

    # region Widgets
    label_runner = Gtk.Template.Child()
    label_state = Gtk.Template.Child()
    label_environment = Gtk.Template.Child()
    label_arch = Gtk.Template.Child()
    btn_rename = Gtk.Template.Child()
    btn_winecfg = Gtk.Template.Child()
    btn_debug = Gtk.Template.Child()
    btn_execute = Gtk.Template.Child()
    btn_run_args = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_cmd = Gtk.Template.Child()
    btn_taskmanager = Gtk.Template.Child()
    btn_controlpanel = Gtk.Template.Child()
    btn_uninstaller = Gtk.Template.Child()
    btn_regedit = Gtk.Template.Child()
    btn_shutdown = Gtk.Template.Child()
    btn_reboot = Gtk.Template.Child()
    btn_killall = Gtk.Template.Child()
    btn_backup_config = Gtk.Template.Child()
    btn_backup_full = Gtk.Template.Child()
    btn_duplicate = Gtk.Template.Child()
    btn_delete = Gtk.Template.Child()
    btn_flatpak_doc = Gtk.Template.Child()
    btn_flatpak_doc_home = Gtk.Template.Child()
    btn_flatpak_doc_expose = Gtk.Template.Child()
    btn_flatpak_doc_upgrade = Gtk.Template.Child()
    btn_help_debug = Gtk.Template.Child()
    box_run_extra = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    grid_versioning = Gtk.Template.Child()
    group_programs = Gtk.Template.Child()
    row_uninstaller = Gtk.Template.Child()
    row_regedit = Gtk.Template.Child()
    row_browse = Gtk.Template.Child()
    # endregion

    def __init__(self, window, config, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.config = config

        self.entry_name.connect('key-release-event', self.__check_entry_name)

        self.btn_rename.connect('toggled', self.__toggle_rename)

        self.btn_winecfg.connect('activate', self.run_winecfg)
        self.btn_debug.connect('activate', self.run_debug)
        self.btn_execute.connect('activate', self.run_executable)
        self.btn_run_args.connect('activate', self.__run_executable_with_args)
        self.btn_browse.connect('activate', self.run_browse)
        self.btn_cmd.connect('activate', self.run_cmd)
        self.btn_taskmanager.connect('activate', self.run_taskmanager)
        self.btn_controlpanel.connect('activate', self.run_controlpanel)
        self.btn_uninstaller.connect('activate', self.run_uninstaller)
        self.btn_regedit.connect('activate', self.run_regedit)

        self.btn_winecfg.connect('pressed', self.run_winecfg)
        self.btn_debug.connect('pressed', self.run_debug)
        self.btn_execute.connect('pressed', self.run_executable)
        self.btn_run_args.connect('pressed', self.__run_executable_with_args)
        self.btn_browse.connect('pressed', self.run_browse)
        self.btn_cmd.connect('pressed', self.run_cmd)
        self.btn_taskmanager.connect('pressed', self.run_taskmanager)
        self.btn_controlpanel.connect('pressed', self.run_controlpanel)
        self.btn_uninstaller.connect('pressed', self.run_uninstaller)
        self.btn_regedit.connect('pressed', self.run_regedit)
        self.btn_delete.connect('pressed', self.__confirm_delete)
        self.btn_shutdown.connect('pressed', self.run_shutdown)
        self.btn_reboot.connect('pressed', self.run_reboot)
        self.btn_killall.connect('pressed', self.run_killall)
        self.btn_backup_config.connect('pressed', self.__backup, "config")
        self.btn_backup_full.connect('pressed', self.__backup, "full")
        self.btn_duplicate.connect('pressed', self.__duplicate)
        self.btn_help_debug.connect(
            'pressed',
            GtkUtils.open_doc_url,
            "utilities/logs-and-debugger#wine-debugger"
        )
        self.btn_flatpak_doc_home.connect(
            'pressed',
            GtkUtils.open_doc_url,
            "flatpak/expose-directories/use-system-home"
        )
        self.btn_flatpak_doc_expose.connect(
            'pressed',
            GtkUtils.open_doc_url,
            "flatpak/expose-directories"
        )
        self.btn_flatpak_doc_upgrade.connect(
            'pressed',
            GtkUtils.open_doc_url,
            "flatpak/migrate-bottles-to-flatpak"
        )

        if "FLATPAK_ID" in os.environ:
            '''
            If Flatpak, show the btn_flatpak_doc widget to reach
            the documentation on how to expose directories
            '''
            self.btn_flatpak_doc.set_visible(True)

        self.__update_by_env()
        self.__update_latest_executables()

    def set_config(self, config):
        self.config = config

        # set update_date
        update_date = datetime.strptime(
            self.config.get("Update_Date"),
            "%Y-%m-%d %H:%M:%S.%f"
        )
        update_date = update_date.strftime("%b %d %Y %H:%M:%S")
        self.entry_name.set_tooltip_text(_("Updated: %s" % update_date))

        # set arch
        arch = _("64-bit")
        if self.config.get("Arch") == "win32":
            arch = _("32-bit")
        self.label_arch.set_text(arch)

        # set name and runner
        self.entry_name.set_text(self.config.get("Name"))
        self.label_runner.set_text(self.config.get("Runner"))

        # set environment
        self.label_environment.set_text(
            _(self.config.get("Environment"))
        )
        env_cxt = self.label_environment.get_style_context()
        for cls in env_cxt.list_classes():
            env_cxt.remove_class(cls)
        env_cxt.add_class("tag")
        env_cxt.add_class(
            f"tag-{self.config.get('Environment').lower()}"
        )

        # set versioning
        self.grid_versioning.set_visible(self.config.get("Versioning"))
        self.label_state.set_text(str(self.config.get("State")))


    def __check_entry_name(self, widget, event_key):
        '''
        This function check if the entry name is valid, looking
        for special characters. It also toggle the widget icon
        and the save button sensitivity according to the result.
        '''
        regex = re.compile('[@!#$%^&*()<>?/\|}{~:.;,]')
        name = widget.get_text()

        if(regex.search(name) is None) and name != "":
            self.btn_rename.set_sensitive(True)
            widget.set_icon_from_icon_name(1, "")
        else:
            self.btn_rename.set_sensitive(False)
            widget.set_icon_from_icon_name(1, "dialog-warning-symbolic")

    def __toggle_rename(self, widget):
        '''
        This function toggle the entry_name editability. It will
        also update the bottle configuration with the new bottle name
        if the entry_name status is False (not editable).
        '''
        status = widget.get_active()
        self.entry_name.set_editable(status)

        if status:
            self.entry_name.grab_focus()
        else:
            self.manager.update_config(
                config=self.config,
                key="Name",
                value=self.entry_name.get_text()
            )

    def update_programs(self, widget=False):
        '''
        This function update the programs lists. The list in the
        details page is limited to 5 items.
        '''
        for w in self.group_programs:
            w.destroy()

        programs = self.manager.get_programs(self.config)

        if len(programs) == 0:
            self.group_programs.set_visible(False)
            return

        self.group_programs.set_visible(True)

        i = 0
        # append first 5 entries to group_programs
        for program in programs:
            if i < 5:
                self.group_programs.add(ProgramEntry(
                    self.window, self.config, program))
            i = + 1

    def __run_executable_with_args(self, widget):
        '''
        This function pop up the dialog to run an executable with
        custom arguments.
        '''
        new_window = RunArgsDialog(self)
        new_window.present()

    def run_executable(self, widget, args=False):
        '''
        This function pop up the dialog to run an executable.
        The file will be executed by the runner after the
        user confirmation.
        '''
        file_dialog = Gtk.FileChooserNative.new(
            _("Choose a Windows executable file"),
            self.window,
            Gtk.FileChooserAction.OPEN,
            _("Run"),
            _("Cancel")
        )

        response = file_dialog.run()
        _execs = self.config.get("Latest_Executables")

        if response == -3:
            if args:
                Runner.run_executable(
                    config=self.config,
                    file_path=file_dialog.get_filename(),
                    arguments=args
                )
                self.manager.update_config(
                    config=self.config,
                    key="Latest_Executables",
                    value=_execs+[{
                        "name": file_dialog.get_filename().split("/")[-1],
                        "file": file_dialog.get_filename(),
                        "args": args
                    }]
                )
            else:
                Runner.run_executable(
                    config=self.config,
                    file_path=file_dialog.get_filename()
                )
                self.manager.update_config(
                    config=self.config,
                    key="Latest_Executables",
                    value=_execs+[{
                        "name": file_dialog.get_filename().split("/")[-1],
                        "file": file_dialog.get_filename(),
                        "args": ""
                    }]
                )

        self.__update_latest_executables()

        file_dialog.destroy()

    def __update_latest_executables(self):
        '''
        This function update the latest executables list.
        '''
        for w in self.box_run_extra.get_children():
            if w != self.btn_run_args:
                w.destroy()

        _execs = self.config.get("Latest_Executables", [])[-5:]
        for exe in _execs:
            _btn = ExecButton(
                data=exe,
                config=self.config
            )
            self.box_run_extra.add(_btn)

    def __backup(self, widget, backup_type):
        '''
        This function pop up the a file chooser where the user
        can select the path where to export the bottle backup.
        Use the backup_type param to export config or full.
        '''
        title = _("Select the location where to save the backup config")
        hint = f"backup_{self.config.get('Path')}.yml"

        if backup_type == "full":
            title = _("Select the location where to save the backup archive")
            hint = f"backup_{self.config.get('Path')}.tar.gz"

        file_dialog = Gtk.FileChooserNative.new(
            title,
            self.window,
            Gtk.FileChooserAction.SAVE,
            _("Export"), _("Cancel")
        )
        file_dialog.set_current_name(hint)
        response = file_dialog.run()
        if response == -3:
            RunAsync(
                task_func=BackupManager.export_backup,
                window=self.window,
                config=self.config,
                scope=backup_type,
                path=file_dialog.get_filename()
            )

        file_dialog.destroy()

    def __duplicate(self, widget):
        '''
        This function pop up the duplicate dialog, so the user can
        choose the new bottle name and perform duplication.
        '''
        new_window = DuplicateDialog(self)
        new_window.present()

    def __confirm_delete(self, widget):
        '''
        This function pop up the delete confirm dialog. If user confirm
        it will ask the manager to delete the bottle and will return
        to the bottles list.
        '''
        dialog_delete = MessageDialog(
            parent=self.window,
            title=_("Confirm deletion"),
            message=_(
                "Are you sure you want to delete this Bottle and all files?"
            )
        )
        response = dialog_delete.run()

        if response == Gtk.ResponseType.OK:
            RunAsync(
                task_func=self.manager.delete_bottle,
                config=self.config
            )
            self.window.go_back()

        dialog_delete.destroy()

    def __update_by_env(self):
        widgets = [
            self.row_uninstaller,
            self.row_regedit,
            self.row_browse
        ]
        for widget in widgets:
            if self.config.get("Environment") == "Layered":
                widget.set_visible(False)
            else:
                widget.set_visible(True)

    '''
    The following functions are used like wrappers for the
    runner utilities.
    '''

    def run_winecfg(self, widget):
        Runner.run_winecfg(self.config)

    def run_debug(self, widget):
        Runner.run_debug(self.config)

    def run_browse(self, widget):
        ManagerUtils.open_filemanager(self.config)

    def run_cmd(self, widget):
        Runner.run_cmd(self.config)

    def run_taskmanager(self, widget):
        Runner.run_taskmanager(self.config)

    def run_controlpanel(self, widget):
        Runner.run_controlpanel(self.config)

    def run_uninstaller(self, widget):
        Runner.run_uninstaller(self.config)

    def run_regedit(self, widget):
        Runner.run_regedit(self.config)

    def run_shutdown(self, widget):
        Runner.wineboot(self.config, status=2, silent=False)

    def run_reboot(self, widget):
        Runner.wineboot(self.config, status=1, silent=False)

    def run_killall(self, widget):
        Runner.wineboot(self.config, status=0, silent=False)

    '''
    The following methods open resources (URLs) in the
    system browser.
    '''
    @staticmethod
    def open_report_url(widget):
        webbrowser.open_new_tab(
            "https://github.com/bottlesdevs/dependencies/issues/new/choose")