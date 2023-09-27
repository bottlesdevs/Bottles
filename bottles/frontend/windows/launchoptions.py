# launchoptions.py
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

from gi.repository import Gtk, GLib, GObject, Adw

from bottles.backend.utils.manager import ManagerUtils
from gettext import gettext as _


@Gtk.Template(resource_path='/com/usebottles/bottles/dialog-launch-options.ui')
class LaunchOptionsDialog(Adw.Window):
    __gtype_name__ = 'LaunchOptionsDialog'
    __gsignals__ = {
        "options-saved": (GObject.SIGNAL_RUN_FIRST, None, (object,)),
    }

    # region Widgets
    entry_arguments = Gtk.Template.Child()
    btn_save = Gtk.Template.Child()
    btn_script = Gtk.Template.Child()
    btn_script_reset = Gtk.Template.Child()
    btn_cwd = Gtk.Template.Child()
    btn_cwd_reset = Gtk.Template.Child()
    btn_reset_defaults = Gtk.Template.Child()
    action_script = Gtk.Template.Child()
    switch_dxvk = Gtk.Template.Child()
    switch_vkd3d = Gtk.Template.Child()
    switch_nvapi = Gtk.Template.Child()
    switch_fsr = Gtk.Template.Child()
    switch_virt_desktop = Gtk.Template.Child()
    action_dxvk = Gtk.Template.Child()
    action_vkd3d = Gtk.Template.Child()
    action_nvapi = Gtk.Template.Child()
    action_fsr = Gtk.Template.Child()
    action_cwd = Gtk.Template.Child()
    action_virt_desktop = Gtk.Template.Child()
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
        self.btn_save.connect("clicked", self.__save)
        self.btn_script.connect("clicked", self.__choose_script)
        self.btn_script_reset.connect("clicked", self.__reset_script)
        self.btn_cwd.connect("clicked", self.__choose_cwd)
        self.btn_cwd_reset.connect("clicked", self.__reset_cwd)
        self.btn_reset_defaults.connect("clicked", self.__reset_defaults)
        self.entry_arguments.connect("activate", self.__save)
        self.switch_dxvk.connect(
            "state-set",
            self.__check_override,
            config.Parameters.dxvk,
            self.action_dxvk
        )
        self.switch_vkd3d.connect(
            "state-set",
            self.__check_override,
            config.Parameters.vkd3d,
            self.action_vkd3d
        )
        self.switch_nvapi.connect(
            "state-set",
            self.__check_override,
            config.Parameters.dxvk_nvapi,
            self.action_nvapi
        )
        self.switch_fsr.connect(
            "state-set",
            self.__check_override,
            config.Parameters.fsr,
            self.action_fsr
        )
        self.switch_virt_desktop.connect(
            "state-set",
            self.__check_override,
            config.Parameters.virtual_desktop,
            self.action_virt_desktop
        )

        if program.get("script") not in ["", None]:
            self.action_script.set_subtitle(program["script"])
            self.btn_script_reset.set_visible(True)

        if program.get("folder") not in ["", None, ManagerUtils.get_exe_parent_dir(self.config, self.program["path"])]:
            self.action_cwd.set_subtitle(program["folder"])
            self.btn_cwd_reset.set_visible(True)

        # set overrides status
        dxvk = config.Parameters.dxvk
        vkd3d = config.Parameters.vkd3d
        nvapi = config.Parameters.dxvk_nvapi
        fsr = config.Parameters.fsr
        virt_desktop = config.Parameters.virtual_desktop

        if not dxvk:
            self.action_dxvk.set_subtitle(self.__msg_disabled.format("DXVK"))
            self.switch_dxvk.set_sensitive(False)
        if not vkd3d:
            self.action_vkd3d.set_subtitle(self.__msg_disabled.format("VKD3D"))
            self.switch_vkd3d.set_sensitive(False)
        if not nvapi:
            self.action_nvapi.set_subtitle(self.__msg_disabled.format("DXVK-Nvapi"))
            self.switch_nvapi.set_sensitive(False)

        if dxvk != self.program.get("dxvk"):
            self.action_dxvk.set_subtitle(self.__msg_override)
        if vkd3d != self.program.get("vkd3d"):
            self.action_vkd3d.set_subtitle(self.__msg_override)
        if nvapi != self.program.get("dxvk_nvapi"):
            self.action_nvapi.set_subtitle(self.__msg_override)
        if fsr != self.program.get("fsr"):
            self.action_fsr.set_subtitle(self.__msg_override)
        if virt_desktop != self.program.get("virtual_desktop"):
            self.action_virt_desktop.set_subtitle(self.__msg_override)

        if "dxvk" in self.program:
            dxvk = self.program["dxvk"]
        if "vkd3d" in self.program:
            vkd3d = self.program["vkd3d"]
        if "dxvk_nvapi" in self.program:
            nvapi = self.program["dxvk_nvapi"]
        if "fsr" in self.program:
            fsr = self.program["fsr"]
        if "virtual_desktop" in self.program:
            virt_desktop = self.program["virtual_desktop"]

        self.switch_dxvk.set_active(dxvk)
        self.switch_vkd3d.set_active(vkd3d)
        self.switch_nvapi.set_active(nvapi)
        self.switch_fsr.set_active(fsr)
        self.switch_virt_desktop.set_active(virt_desktop)

    def __check_override(self, widget, state, value, action):
        if state != value:
            action.set_subtitle(self.__msg_override)
        else:
            action.set_subtitle("")

    def get_config(self):
        return self.config

    def __idle_save(self, *_args):
        dxvk = self.switch_dxvk.get_state()
        vkd3d = self.switch_vkd3d.get_state()
        nvapi = self.switch_nvapi.get_state()
        fsr = self.switch_fsr.get_state()
        virt_desktop = self.switch_virt_desktop.get_state()

        self.program["dxvk"] = dxvk
        self.program["vkd3d"] = vkd3d
        self.program["dxvk_nvapi"] = nvapi
        self.program["fsr"] = fsr
        self.program["virtual_desktop"] = virt_desktop
        self.program["arguments"] = self.entry_arguments.get_text()

        self.config = self.manager.update_config(
            config=self.config,
            key=self.program["id"],
            value=self.program,
            scope="External_Programs"
        ).data["config"]

        self.emit("options-saved", self.config)
        self.close()
        return

    def __save(self, *_args):
        GLib.idle_add(self.__idle_save)

    def __choose_script(self, *_args):
        def set_path(dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                self.action_script.set_subtitle(self.__default_script_msg)
                return

            file_path = dialog.get_file().get_path()
            self.program["script"] = file_path
            self.action_script.set_subtitle(file_path)
            self.btn_script_reset.set_visible(True)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Script"),
            parent=self.window,
            action=Gtk.FileChooserAction.OPEN
        )

        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def __reset_script(self, *_args):
        self.program["script"] = ""
        self.action_script.set_subtitle(self.__default_script_msg)
        self.btn_script_reset.set_visible(False)

    def __choose_cwd(self, *_args):
        def set_path(dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                self.action_cwd.set_subtitle(self.__default_cwd_msg)
                return

            directory_path = dialog.get_file().get_path()
            self.program["folder"] = directory_path
            self.action_cwd.set_subtitle(directory_path)
            self.btn_cwd_reset.set_visible(True)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Working Directory"),
            parent=self.window,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )

        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def __reset_cwd(self, *_args):
        """
        This function reset the script path.
        """
        self.program["folder"] = ManagerUtils.get_exe_parent_dir(self.config, self.program["path"])
        self.action_cwd.set_subtitle(self.__default_cwd_msg)
        self.btn_cwd_reset.set_visible(False)

    def __reset_defaults(self, *_args):
        self.switch_dxvk.set_active(self.config.Parameters.dxvk)
        self.switch_vkd3d.set_active(self.config.Parameters.vkd3d)
        self.switch_nvapi.set_active(self.config.Parameters.dxvk_nvapi)
        self.switch_fsr.set_active(self.config.Parameters.fsr)
        self.switch_virt_desktop.set_active(self.config.Parameters.virtual_desktop)
