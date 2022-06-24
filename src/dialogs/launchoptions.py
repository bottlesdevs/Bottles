# launchoptions.py
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
from gi.repository import Gtk, GLib, Adw

from bottles.dialogs.filechooser import FileChooser  # pyright: reportMissingImports=false
from bottles.backend.utils.manager import ManagerUtils


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-launch-options.ui')
class LaunchOptionsDialog(Adw.Window):
    __gtype_name__ = 'LaunchOptionsDialog'

    # region Widgets
    entry_arguments = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    btn_script = Gtk.Template.Child()
    btn_script_reset = Gtk.Template.Child()
    btn_cwd = Gtk.Template.Child()
    btn_cwd_reset = Gtk.Template.Child()
    action_script = Gtk.Template.Child()
    switch_dxvk = Gtk.Template.Child()
    switch_vkd3d = Gtk.Template.Child()
    switch_nvapi = Gtk.Template.Child()
    action_dxvk = Gtk.Template.Child()
    action_vkd3d = Gtk.Template.Child()
    action_nvapi = Gtk.Template.Child()
    action_cwd = Gtk.Template.Child()

    # endregion

    __default_script_msg = _("Choose a script which should be executed after run.")
    __default_cwd_msg = _("Choose from where start the program.")
    __msg_disabled = _("{0} is already disabled for this bottle.")
    __msg_override = _("This setting is different from the bottle's default.")

    def __init__(self, parent, config, program, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.parent = parent
        self.window = parent.window
        self.manager = parent.window.manager
        self.config = config
        self.program = program

        self.set_transient_for(self.window)

        # set widget defaults
        self.entry_arguments.set_text(program.get("arguments", ""))

        # connect signals
        self.btn_cancel.connect("clicked", self.__close_window, False)
        self.btn_save.connect("clicked", self.__save_options)
        self.btn_script.connect("clicked", self.__choose_script)
        self.btn_script_reset.connect("clicked", self.__reset_script)
        self.btn_cwd.connect("clicked", self.__choose_cwd)
        self.btn_cwd_reset.connect("clicked", self.__reset_cwd)
        self.entry_arguments.connect("activate", self.__save_options)
        self.switch_dxvk.connect(
            "state-set",
            self.__check_override,
            config["Parameters"].get("dxvk"),
            self.action_dxvk
        )
        self.switch_vkd3d.connect(
            "state-set",
            self.__check_override,
            config["Parameters"].get("vkd3d"),
            self.action_vkd3d
        )
        self.switch_nvapi.connect(
            "state-set",
            self.__check_override,
            config["Parameters"].get("dxvk_nvapi"),
            self.action_nvapi
        )

        if program.get("script") not in ["", None]:
            self.action_script.set_subtitle(program["script"])
            self.action_script.set_visible(True)

        if program.get("folder") != ManagerUtils.get_exe_parent_dir(self.config, self.program["path"]):
            self.action_cwd.set_subtitle(program["folder"])
            self.action_cwd.set_visible(True)

        # set overrides status
        dxvk = config["Parameters"].get("dxvk")
        vkd3d = config["Parameters"].get("vkd3d")
        nvapi = config["Parameters"].get("dxvk_nvapi")

        if not dxvk:
            self.action_dxvk.set_subtitle(self.__msg_disabled.format("DXVK"))
            self.switch_dxvk.set_sensitive(False)
        if not vkd3d:
            self.action_vkd3d.set_subtitle(self.__msg_disabled.format("VKD3D"))
            self.switch_vkd3d.set_sensitive(False)
        if not nvapi:
            self.action_nvapi.set_subtitle(self.__msg_disabled.format("DXVK-Nvapi"))
            self.switch_nvapi.set_sensitive(False)

        if dxvk != self.program["dxvk"]:
            self.action_dxvk.set_subtitle(self.__msg_override)
        if vkd3d != self.program["vkd3d"]:
            self.action_vkd3d.set_subtitle(self.__msg_override)
        if nvapi != self.program["dxvk_nvapi"]:
            self.action_nvapi.set_subtitle(self.__msg_override)

        if "dxvk" in self.program:
            dxvk = self.program["dxvk"]
        if "vkd3d" in self.program:
            vkd3d = self.program["vkd3d"]
        if "dxvk_nvapi" in self.program:
            nvapi = self.program["dxvk_nvapi"]

        self.switch_dxvk.set_active(dxvk)
        self.switch_vkd3d.set_active(vkd3d)
        self.switch_nvapi.set_active(nvapi)

    def __check_override(self, widget, state, value, action):
        if state != value:
            action.set_subtitle(self.__msg_override)
        else:
            action.set_subtitle("")

    def __close_window(self, widget=None, save=True):
        if save:
            self.parent.page_details.set_config(self.config, rebuild_pages=False)
        self.destroy()

    def __save_options(self, widget):
        dxvk = self.switch_dxvk.get_state()
        vkd3d = self.switch_vkd3d.get_state()
        nvapi = self.switch_nvapi.get_state()

        self.program["dxvk"] = dxvk
        self.program["vkd3d"] = vkd3d
        self.program["dxvk_nvapi"] = nvapi

        self.program["arguments"] = self.entry_arguments.get_text()
        self.config = self.manager.update_config(
            config=self.config,
            key=self.program["id"],
            value=self.program,
            scope="External_Programs"
        ).data["config"]
        GLib.idle_add(self.__close_window)

    def __choose_script(self, _widget):
        def set_path(_dialog, response, _file_dialog):
            if response == -3:
                _file = _file_dialog.get_file()
                self.program["script"] = _file.get_path()
                self.action_script.set_subtitle(_file.get_path())
                return

            self.action_script.set_subtitle(self.__default_script_msg)

        FileChooser(
            parent=self.window,
            title=_("Choose the script"),
            action=Gtk.FileChooserAction.OPEN,
            buttons=(_("Cancel"), _("Select")),
            callback=set_path
        )

    def __reset_script(self, _widget):
        self.program["script"] = ""
        self.action_script.set_subtitle(self.__default_script_msg)

    def __choose_cwd(self, _widget):
        def set_path(_dialog, response, _file_dialog):
            if response == -3:
                _file = _file_dialog.get_file()
                self.program["folder"] = _file.get_path()
                self.action_cwd.set_subtitle(_file.get_path())
                return

            self.action_cwd.set_subtitle(self.__default_cwd_msg)

        FileChooser(
            parent=self.window,
            title=_("Choose the Working Directory"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=(_("Cancel"), _("Select")),
            callback=set_path
        )

    def __reset_cwd(self, _widget):
        """
        This function reset the script path.
        """
        self.program["folder"] = ManagerUtils.get_exe_parent_dir(self.config, self.program["path"])
        self.action_script.set_subtitle(self.__default_cwd_msg)
