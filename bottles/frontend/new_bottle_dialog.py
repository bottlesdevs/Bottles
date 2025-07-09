# new_bottle_dialog.py
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

import os
import subprocess

from gettext import gettext as _
from typing import Any
from gi.repository import Gtk, Adw, Pango, Gio, Xdp, GObject, GLib

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.threading import RunAsync
from bottles.backend.models.result import Result
from bottles.frontend.filters import add_yaml_filters, add_all_filters
from bottles.frontend.gtk import GtkUtils


@Gtk.Template(resource_path="/com/usebottles/bottles/check-row.ui")
class CheckRow(Adw.ActionRow):
    """An `AdwActionRow` with a designated `GtkCheckButton` as prefix."""

    __gtype_name__ = "CheckRow"

    check_button = Gtk.Template.Child()

    active = GObject.Property(type=bool, default=False)
    environment = GObject.Property(type=str, default=None)

    # Add row’s check button to the group
    group = GObject.Property(
        # FIXME: Supposed to be a CheckRow widget type.
        type=Adw.ActionRow,
        default=None,
        setter=lambda self, group: self.check_button.set_group(group.check_button),
    )


@Gtk.Template(resource_path="/com/usebottles/bottles/new-bottle-dialog.ui")
class NewBottleDialog(Adw.Dialog):
    __gtype_name__ = "NewBottleDialog"

    # region Widgets
    entry_name = Gtk.Template.Child()
    stack_create = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    btn_choose_env = Gtk.Template.Child()
    btn_choose_env_reset = Gtk.Template.Child()
    label_choose_env = Gtk.Template.Child()
    status_page_status = Gtk.Template.Child()
    btn_choose_path = Gtk.Template.Child()
    btn_choose_path_reset = Gtk.Template.Child()
    label_choose_path = Gtk.Template.Child()
    label_output = Gtk.Template.Child()
    scrolled_output = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    combo_arch = Gtk.Template.Child()
    str_list_arch = Gtk.Template.Child()
    str_list_runner = Gtk.Template.Child()
    menu_duplicate = Gtk.Template.Child()
    environment_list_box = Gtk.Template.Child()

    selected_environment = GObject.Property(type=str, default=None)

    # endregion

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # common variables and references
        self.window = GtkUtils.get_parent_window()
        if not self.window or not Xdp.Portal.running_under_sandbox():
            return

        self.app = self.window.get_application()
        self.new_bottle_config = BottleConfig()
        self.available_runners = []
        self.available_dxvk_versions = []
        self.env_recipe_path = None
        self.custom_path = ""
        self.default_string = _("(Default)")

        try:
            wine_version = subprocess.check_output(["wine", "--version"], text=True)
            wine_version = "sys-" + wine_version.split("\n")[0].split(" ")[0]
            self.available_runners.append(wine_version)
        except FileNotFoundError:
            pass

        self.available_dxvk_versions = self.__get_available_versions_from_component(
            "dxvk"
        )
        self.available_nvapi_versions = self.__get_available_versions_from_component(
            "nvapi"
        )
        self.available_vkd3d_versions = self.__get_available_versions_from_component(
            "vkd3d"
        )
        self.available_runners = (
            self.available_runners
            + self.__get_available_versions_from_component("runners")
        )

        self.arch = {"win64": "64-bit", "win32": "32-bit"}

        # connect signals
        self.window.connect("notify::is-active", self.__remove_notifications)
        self.btn_cancel.connect("clicked", self.__close_dialog)
        self.btn_close.connect("clicked", self.__close_dialog)
        self.btn_create.connect("clicked", self.create_bottle)
        self.btn_choose_env.connect("clicked", self.__choose_env_recipe)
        self.btn_choose_env_reset.connect("clicked", self.__reset_env_recipe)
        self.btn_choose_path.connect("clicked", self.__choose_path)
        self.btn_choose_path_reset.connect("clicked", self.__reset_path)
        self.entry_name.connect("changed", self.__check_entry_name)
        self.entry_name.connect("entry-activated", self.__entry_activated)
        self.environment_list_box.connect(
            "row-activated",
            lambda _, row: self.set_property("selected-environment", row.environment),
        )

        # Populate widgets
        self.label_choose_env.set_label(self.default_string)
        self.label_choose_path.set_label(self.default_string)
        self.str_list_runner.splice(0, 0, self.available_runners)
        self.str_list_arch.splice(0, 0, list(self.arch.values()))

        self.selected_environment = (
            self.environment_list_box.get_first_child().environment
        )

    def __get_available_versions_from_component(self, component: str) -> list[str]:
        component_dir = os.path.join(GLib.get_user_data_dir(), "bottles", component)
        return os.listdir(component_dir)

    def __get_path(self) -> str:
        if self.custom_path:
            return self.custom_path
        else:
            return os.path.join(
                GLib.get_user_data_dir(), "bottles", self.entry_name.get_text()
            )

    def __check_validity(self, *_args: Any) -> tuple[bool, bool]:
        is_empty = self.entry_name.get_text() == ""
        is_duplicate = self.entry_name.get_text() in self.app.local_bottles
        return (is_empty, is_duplicate)

    def __check_entry_name(self, *_args: Any) -> None:
        is_empty, is_duplicate = self.__check_validity()
        is_invalid = is_empty or is_duplicate
        self.btn_create.set_sensitive(not is_invalid)
        self.menu_duplicate.set_visible(is_duplicate)

        if is_invalid:
            self.entry_name.add_css_class("error")
        else:
            self.entry_name.remove_css_class("error")

    def __entry_activated(self, *_args: Any) -> None:
        if not any(self.__check_validity()):
            self.create_bottle()

    def __remove_notifications(self, *_args: Any) -> None:
        self.app.withdraw_notification("bottle-created-completed")

    def __choose_env_recipe(self, *_args: Any) -> None:
        """
        Opens a file chooser dialog to select the configuration file
        in yaml format.
        """

        def set_path(dialog, result):
            try:
                file = dialog.open_finish(result)
            except GLib.Error:
                return

            self.btn_choose_env_reset.set_visible(True)
            self.env_recipe_path = file.get_path()
            self.label_choose_env.set_label(file.get_basename())
            self.label_choose_env.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

        filters = Gio.ListStore.new(Gtk.FileFilter)

        yaml_filter = Gtk.FileFilter()
        yaml_filter.set_name("YAML")
        yaml_filter.add_mime_type("application/yaml")

        all_filter = Gtk.FileFilter()
        all_filter.set_name(_("All Files"))
        all_filter.add_pattern("*")

        filters.append(yaml_filter)
        filters.append(all_filter)

        dialog = Gtk.FileDialog.new()
        dialog.set_title(_("Select Configuration"))
        dialog.set_filters(filters)

        dialog.open(self.window, callback=set_path)

    def __choose_path(self, *_args: Any) -> None:
        """Opens a file chooser dialog to select the directory."""

        def set_path(dialog, result):
            try:
                folder = dialog.select_folder_finish(result)
            except GLib.Error:
                return

            self.custom_path = folder.get_path()
            print(folder.get_basename())

            self.btn_choose_path_reset.set_visible(True)
            self.label_choose_path.set_label(folder.get_basename())
            self.label_choose_path.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

        dialog = Gtk.FileDialog.new()
        dialog.set_title(_("Select Directory"))
        dialog.set_modal(True)
        dialog.select_folder(parent=self.window, callback=set_path)

    def create_bottle(self, *_args: Any) -> None:
        """Starts creating the bottle."""
        # set widgets states
        # self.set_can_close(False) TODO: UNCOMMENT
        self.stack_create.set_visible_child_name("page_creating")

        config = BottleConfig(
            Name=self.entry_name.get_text(),
            Arch=list(self.arch)[self.combo_arch.get_selected()],
            Runner=self.available_runners[self.combo_runner.get_selected()],
            Custom_Path=bool(self.custom_path),
            Path=os.path.join(self.custom_path, self.entry_name.get_text()),
            Environment=self.selected_environment,
        )

        print(config)

        # RunAsync(
        #     task_func=self.manager.create_bottle,
        #     callback=self.finish,
        #     name=self.entry_name.get_text(),
        #     path=self.custom_path,
        #     environment=self.selected_environment,
        #     runner=runner,
        #     arch=list(self.arch)[self.combo_arch.get_selected()],
        #     dxvk=self.available_dxvk_versions[0],
        #     fn_logger=self.update_output,
        #     custom_environment=self.env_recipe_path,
        # )

    @GtkUtils.run_in_main_loop
    def update_output(self, text: str) -> None:
        """
        Updates label_output with the given text by concatenating
        with the previous text.
        """
        current_text = self.label_output.get_text()
        text = f"{current_text}{text}\n"
        self.label_output.set_text(text)

    @GtkUtils.run_in_main_loop
    def finish(self, result: Result | None, error=None) -> None:
        """Updates widgets based on whether it succeeded or failed."""

        def send_notification(notification: Gio.Notification) -> None:
            """Sends notification if out of focus."""
            if not self.window.is_active():
                self.app.send_notification("bottle-created-completed", notification)

        self.set_can_close(True)
        self.stack_create.set_visible_child_name("page_completed")
        notification = Gio.Notification()

        # Show error if bottle unsuccessfully builds
        if not result or not result.status or error:
            title = _("Unable to Create Bottle")
            notification.set_title(title)
            notification.set_body(_("Bottle failed to create with one or more errors."))
            self.status_page_status.set_title(title)
            self.btn_close.add_css_class("destructive-action")
            send_notification(notification)

            # Display error logs in the result page
            self.scrolled_output.unparent()
            box = self.status_page_status.get_child()
            box.prepend(self.scrolled_output)

            return

        # Show success
        title = _("Bottle Created")
        description = _("“{0}” was created successfully.").format(
            self.entry_name.get_text()
        )

        notification.set_title(title)
        notification.set_body(description)

        self.new_bottle_config = result.data.get("config")
        self.btn_close.add_css_class("suggested-action")
        self.status_page_status.set_icon_name("selection-mode-symbolic")
        self.status_page_status.set_title(title)
        self.status_page_status.set_description(description)
        send_notification(notification)

        # Ask the manager to check for new bottles,
        # then update the user bottles' list.
        self.manager.check_bottles()
        self.window.page_list.update_bottles_list()
        self.window.page_list.show_page(self.new_bottle_config.get("Path"))

    def __reset_env_recipe(self, *_args: Any) -> None:
        self.btn_choose_env_reset.set_visible(False)
        self.env_recipe_path = None
        self.label_choose_env.set_label(self.default_string)

    def __reset_path(self, *_args: Any) -> None:
        self.btn_choose_path_reset.set_visible(False)
        self.custom_path = ""
        self.label_choose_path.set_label(self.default_string)

    def __close_dialog(self, *_args: Any) -> None:
        self.window.disconnect_by_func(self.__remove_notifications)
        # TODO: Implement AdwMessageDialog to prompt the user if they are
        # SURE they want to cancel creation. For now, the window will not
        # react if the user attempts to close the window while a bottle
        # is being created in a feature update
        self.close()
