# launch_options_dialog.py
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

from gi.repository import Gtk, GLib, GObject, Adw

from bottles.backend.utils.manager import ManagerUtils
import logging
from gettext import gettext as _


@Gtk.Template(resource_path="/com/usebottles/bottles/launch-options-dialog.ui")
class LaunchOptionsDialog(Adw.Window):
    __gtype_name__ = "LaunchOptionsDialog"
    __gsignals__ = {
        "options-saved": (GObject.SIGNAL_RUN_FIRST, None, (object,)),
    }

    # region Widgets
    entry_arguments = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    btn_pre_script = Gtk.Template.Child()
    btn_pre_script_reset = Gtk.Template.Child()
    btn_post_script = Gtk.Template.Child()
    btn_post_script_reset = Gtk.Template.Child()
    btn_cwd = Gtk.Template.Child()
    btn_cwd_reset = Gtk.Template.Child()
    btn_reset_defaults = Gtk.Template.Child()
    action_pre_script = Gtk.Template.Child()
    action_post_script = Gtk.Template.Child()
    switch_dxvk = Gtk.Template.Child()
    switch_vkd3d = Gtk.Template.Child()
    switch_nvapi = Gtk.Template.Child()
    switch_fsr = Gtk.Template.Child()
    switch_gamescope = Gtk.Template.Child()
    switch_virt_desktop = Gtk.Template.Child()
    action_dxvk = Gtk.Template.Child()
    action_vkd3d = Gtk.Template.Child()
    action_nvapi = Gtk.Template.Child()
    action_fsr = Gtk.Template.Child()
    action_gamescope = Gtk.Template.Child()
    action_cwd = Gtk.Template.Child()
    action_virt_desktop = Gtk.Template.Child()
    # endregion

    __default_pre_script_msg = _("Choose a script which should be executed before run.")
    __default_post_script_msg = _("Choose a script which should be executed after run.")
    __default_cwd_msg = _("Choose from where start the program.")
    __msg_disabled = _("{0} is disabled globally for this bottle.")
    __msg_override = _("This setting overrides the bottle's global setting.")

    def __set_disabled_switches(self):
        if not self.global_dxvk:
            self.action_dxvk.set_subtitle(self.__msg_disabled.format("DXVK"))
            self.switch_dxvk.set_sensitive(False)
        if not self.global_vkd3d:
            self.action_vkd3d.set_subtitle(self.__msg_disabled.format("VKD3D"))
            self.switch_vkd3d.set_sensitive(False)
        if not self.global_nvapi:
            self.action_nvapi.set_subtitle(self.__msg_disabled.format("DXVK-NVAPI"))
            self.switch_nvapi.set_sensitive(False)

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
        if program.get("arguments") not in ["", None]:
            self.entry_arguments.set_text(program.get("arguments"))

        # keeps track of toggled switches
        self.toggled = {}
        self.toggled["dxvk"] = False
        self.toggled["vkd3d"] = False
        self.toggled["dxvk_nvapi"] = False
        self.toggled["fsr"] = False
        self.toggled["gamescope"] = False
        self.toggled["virtual_desktop"] = False

        # connect signals
        self.btn_save.connect("clicked", self.__save)
        self.btn_pre_script.connect("clicked", self.__choose_pre_script)
        self.btn_pre_script_reset.connect("clicked", self.__reset_pre_script)
        self.btn_post_script.connect("clicked", self.__choose_post_script)
        self.btn_post_script_reset.connect("clicked", self.__reset_post_script)
        self.btn_cwd.connect("clicked", self.__choose_cwd)
        self.btn_cwd_reset.connect("clicked", self.__reset_cwd)
        self.btn_reset_defaults.connect("clicked", self.__reset_defaults)
        self.entry_arguments.connect("activate", self.__save)

        # set overrides status
        self.global_dxvk = program_dxvk = config.Parameters.dxvk
        self.global_vkd3d = program_vkd3d = config.Parameters.vkd3d
        self.global_nvapi = program_nvapi = config.Parameters.dxvk_nvapi
        self.global_fsr = program_fsr = config.Parameters.fsr
        self.global_gamescope = program_gamescope = config.Parameters.gamescope
        self.global_virt_desktop = program_virt_desktop = (
            config.Parameters.virtual_desktop
        )

        if self.program.get("dxvk") is not None:
            program_dxvk = self.program.get("dxvk")
            self.action_dxvk.set_subtitle(self.__msg_override)
        if self.program.get("vkd3d") is not None:
            program_vkd3d = self.program.get("vkd3d")
            self.action_vkd3d.set_subtitle(self.__msg_override)
        if self.program.get("dxvk_nvapi") is not None:
            program_nvapi = self.program.get("dxvk_nvapi")
            self.action_nvapi.set_subtitle(self.__msg_override)
        if self.program.get("fsr") is not None:
            program_fsr = self.program.get("fsr")
            self.action_fsr.set_subtitle(self.__msg_override)
        if self.program.get("gamescope") is not None:
            program_gamescope = self.program.get("gamescope")
            self.action_gamescope.set_subtitle(self.__msg_override)
        if self.program.get("virtual_desktop") is not None:
            program_virt_desktop = self.program.get("virtual_desktop")
            self.action_virt_desktop.set_subtitle(self.__msg_override)

        self.switch_dxvk.set_active(program_dxvk)
        self.switch_vkd3d.set_active(program_vkd3d)
        self.switch_nvapi.set_active(program_nvapi)
        self.switch_fsr.set_active(program_fsr)
        self.switch_gamescope.set_active(program_gamescope)
        self.switch_virt_desktop.set_active(program_virt_desktop)

        self.switch_dxvk.connect(
            "state-set", self.__check_override, self.action_dxvk, "dxvk"
        )
        self.switch_vkd3d.connect(
            "state-set", self.__check_override, self.action_vkd3d, "vkd3d"
        )
        self.switch_nvapi.connect(
            "state-set", self.__check_override, self.action_nvapi, "dxvk_nvapi"
        )
        self.switch_fsr.connect(
            "state-set", self.__check_override, self.action_fsr, "fsr"
        )
        self.switch_gamescope.connect(
            "state-set", self.__check_override, self.action_gamescope, "gamescope"
        )
        self.switch_virt_desktop.connect(
            "state-set",
            self.__check_override,
            self.action_virt_desktop,
            "virtual_desktop",
        )

        if program.get("pre_script") not in ("", None):
            self.action_pre_script.set_subtitle(program["pre_script"])
            self.btn_pre_script_reset.set_visible(True)

        if program.get("post_script") not in ("", None):
            self.action_post_script.set_subtitle(program["post_script"])
            self.btn_post_script_reset.set_visible(True)

        if program.get("folder") not in (
            "",
            None,
            ManagerUtils.get_exe_parent_dir(self.config, self.program["path"]),
        ):
            self.action_cwd.set_subtitle(program["folder"])
            self.btn_cwd_reset.set_visible(True)

        self.__set_disabled_switches()

    def __check_override(self, widget, state, action, name):
        self.toggled[name] = True
        action.set_subtitle(self.__msg_override)

    def get_config(self):
        return self.config

    def __set_override(self, name, program_value, global_value):
        # Special reset value
        if self.toggled[name] is None and name in self.program:
            del self.program[name]
        if self.toggled[name]:
            self.program[name] = program_value

    def __idle_save(self, *_args):
        program_dxvk = self.switch_dxvk.get_state()
        program_vkd3d = self.switch_vkd3d.get_state()
        program_nvapi = self.switch_nvapi.get_state()
        program_fsr = self.switch_fsr.get_state()
        program_gamescope = self.switch_gamescope.get_state()
        program_virt_desktop = self.switch_virt_desktop.get_state()

        self.__set_override("dxvk", program_dxvk, self.global_dxvk)
        self.__set_override("vkd3d", program_vkd3d, self.global_vkd3d)
        self.__set_override("dxvk_nvapi", program_nvapi, self.global_nvapi)
        self.__set_override("fsr", program_fsr, self.global_fsr)
        self.__set_override("gamescope", program_gamescope, self.global_gamescope)
        self.__set_override(
            "virtual_desktop", program_virt_desktop, self.global_virt_desktop
        )
        self.program["arguments"] = self.entry_arguments.get_text()

        self.config = self.manager.update_config(
            config=self.config,
            key=self.program["id"],
            value=self.program,
            scope="External_Programs",
        ).data["config"]

        self.emit("options-saved", self.config)
        self.close()
        return

    def __save(self, *_args):
        GLib.idle_add(self.__idle_save)

    def __choose_pre_script(self, *_args):
        def set_path(dialog, result):
            try:
                file = dialog.open_finish(result)

                if file is None:
                    self.action_pre_script.set_subtitle(self.__default_pre_script_msg)
                    return

                file_path = file.get_path()

                self.program["pre_script"] = file_path
                self.action_pre_script.set_subtitle(file_path)
                self.btn_pre_script_reset.set_visible(True)

            except GLib.Error as error:
                # also thrown when dialog has been cancelled
                if error.code == 2:
                    # error 2 seems to be 'dismiss' or 'cancel'
                    if self.program.get("pre_script") in (None, ""):
                        self.action_pre_script.set_subtitle(
                            self.__default_pre_script_msg
                        )
                else:
                    # something else happened...
                    logging.warning("Error selecting pre-run script: %s" % error)

        dialog = Gtk.FileDialog.new()
        dialog.set_title("Select Pre-run Script")
        dialog.set_modal(True)
        dialog.open(parent=self.window, callback=set_path)

    def __choose_post_script(self, *_args):
        def set_path(dialog, result):
            try:
                file = dialog.open_finish(result)

                if file is None:
                    self.action_post_script.set_subtitle(self.__default_post_script_msg)
                    return

                file_path = file.get_path()
                self.program["post_script"] = file_path
                self.action_post_script.set_subtitle(file_path)
                self.btn_post_script_reset.set_visible(True)
            except GLib.Error as error:
                # also thrown when dialog has been cancelled
                if error.code == 2:
                    # error 2 seems to be 'dismiss' or 'cancel'
                    if self.program.get("post_script") in (None, ""):
                        self.action_pre_script.set_subtitle(
                            self.__default_pre_script_msg
                        )
                else:
                    # something else happened...
                    logging.warning("Error selecting post-run script: %s" % error)

        dialog = Gtk.FileDialog.new()
        dialog.set_title("Select Post-run Script")
        dialog.set_modal(True)
        dialog.open(parent=self.window, callback=set_path)

    def __reset_pre_script(self, *_args):
        self.program["pre_script"] = None
        self.action_pre_script.set_subtitle(self.__default_pre_script_msg)
        self.btn_pre_script_reset.set_visible(False)

    def __reset_post_script(self, *_args):
        self.program["post_script"] = None
        self.action_post_script.set_subtitle(self.__default_post_script_msg)
        self.btn_post_script_reset.set_visible(False)

    def __choose_cwd(self, *_args):
        def set_path(dialog, result):
            try:
                directory = dialog.select_folder_finish(result)

                if directory is None:
                    self.action_cwd.set_subtitle(self.__default_cwd_msg)
                    return

                directory_path = directory.get_path()
                self.program["folder"] = directory_path
                self.action_cwd.set_subtitle(directory_path)
                self.btn_cwd_reset.set_visible(True)
            except GLib.Error as error:
                # also thrown when dialog has been cancelled
                if error.code == 2:
                    # error 2 seems to be 'dismiss' or 'cancel'
                    if self.program.get("folder") in (None, ""):
                        self.action_cwd.set_subtitle(self.__default_cwd_msg)
                else:
                    # something else happened...
                    logging.warning("Error selecting folder: %s" % error)
                    raise

        dialog = Gtk.FileDialog.new()
        dialog.set_title(_("Select Working Directory"))
        dialog.set_modal(True)
        dialog.select_folder(parent=self.window, callback=set_path)

    def __reset_cwd(self, *_args):
        """
        This function reset the script path.
        """
        self.program["folder"] = ManagerUtils.get_exe_parent_dir(
            self.config, self.program["path"]
        )
        self.action_cwd.set_subtitle(self.__default_cwd_msg)
        self.btn_cwd_reset.set_visible(False)

    def __reset_defaults(self, *_args):
        self.switch_dxvk.set_active(self.global_dxvk)
        self.switch_vkd3d.set_active(self.global_vkd3d)
        self.switch_nvapi.set_active(self.global_nvapi)
        self.switch_fsr.set_active(self.global_fsr)
        self.switch_gamescope.set_active(self.global_gamescope)
        self.switch_virt_desktop.set_active(self.global_virt_desktop)
        self.action_dxvk.set_subtitle("")
        self.action_vkd3d.set_subtitle("")
        self.action_nvapi.set_subtitle("")
        self.action_fsr.set_subtitle("")
        self.action_gamescope.set_subtitle("")
        self.action_virt_desktop.set_subtitle("")
        self.__set_disabled_switches()
        for name in self.toggled:
            self.toggled[name] = None
