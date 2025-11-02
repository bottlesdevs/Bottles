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
from gettext import gettext as _
from threading import Event
from typing import Any, Optional

from bottles.backend.state import Task, TaskManager
from gi.repository import Gtk, Adw, Pango, Gio, Xdp, GObject, GLib

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.threading import RunAsync
from bottles.backend.models.result import Result
from bottles.frontend.utils.filters import add_yaml_filters, add_all_filters
from bottles.frontend.utils.gtk import GtkUtils
from pathvalidate import sanitize_filename


@Gtk.Template(resource_path="/com/usebottles/bottles/check-row.ui")
class BottlesCheckRow(Adw.ActionRow):
    """An `AdwActionRow` with a designated `GtkCheckButton` as prefix."""

    __gtype_name__ = "BottlesCheckRow"

    check_button = Gtk.Template.Child()

    active = GObject.Property(type=bool, default=False)
    environment = GObject.Property(type=str, default=None)

    # Add row’s check button to the group
    group = GObject.Property(
        # FIXME: Supposed to be a BottlesCheckRow widget type.
        type=Adw.ActionRow,
        default=None,
        setter=lambda self, group: self.check_button.set_group(group.check_button),
    )


@Gtk.Template(resource_path="/com/usebottles/bottles/new-bottle-dialog.ui")
class BottlesNewBottleDialog(Adw.Dialog):
    __gtype_name__ = "BottlesNewBottleDialog"

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
    btn_cancel_creating = Gtk.Template.Child()
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
        self.manager = self.window.manager
        self.new_bottle_config = BottleConfig()
        self.env_recipe_path = None
        self.custom_path = ""
        self.runner = None
        self.default_string = _("(Default)")

        self._creation_task: Optional[Task] = None
        self._creation_job: Optional[RunAsync] = None
        self._creation_cancel_event: Optional[Event] = None
        self._cleanup_job: Optional[RunAsync] = None
        self._cleanup_config: Optional[BottleConfig] = None
        self._cancel_requested = False

        self.arch = {"win64": "64-bit", "win32": "32-bit"}

        # connect signals
        self.window.connect("notify::is-active", self.__remove_notifications)
        self.btn_cancel.connect("clicked", self.__close_dialog)
        self.btn_close.connect("clicked", self.__close_dialog)
        self.btn_create.connect("clicked", self.create_bottle)
        self.btn_cancel_creating.connect("clicked", self.__prompt_cancel_confirmation)
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
        self.str_list_runner.splice(0, 0, self.manager.runners_available)
        self.str_list_arch.splice(0, 0, list(self.arch.values()))

        self.selected_environment = (
            self.environment_list_box.get_first_child().environment
        )

    def __check_validity(self, *_args: Any) -> tuple[bool, bool]:
        is_empty = self.entry_name.get_text() == ""
        is_duplicate = self.entry_name.get_text() in self.manager.local_bottles
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
        self.set_can_close(False)
        self.stack_create.set_visible_child_name("page_creating")
        self._cancel_requested = False
        self._cleanup_config = None
        self.btn_cancel_creating.set_sensitive(True)
        self.btn_cancel_creating.set_label(_("_Cancel Creation"))

        self.runner = self.manager.runners_available[self.combo_runner.get_selected()]

        self.__clear_creation_task()

        task_title = _("Creating “{0}”").format(self.entry_name.get_text())
        self._creation_task = Task(title=task_title)
        TaskManager.add(self._creation_task)

        self._creation_cancel_event = Event()
        self._creation_job = RunAsync(
            task_func=self.manager.create_bottle,
            callback=self.finish,
            name=self.entry_name.get_text(),
            path=self.custom_path,
            environment=self.selected_environment,
            runner=self.runner,
            arch=list(self.arch)[self.combo_arch.get_selected()],
            dxvk=self.manager.dxvk_available[0],
            fn_logger=self.update_output,
            custom_environment=self.env_recipe_path,
            cancel_event=self._creation_cancel_event,
        )

    @GtkUtils.run_in_main_loop
    def update_output(self, text: str) -> None:
        """
        Updates label_output with the given text by concatenating
        with the previous text.
        """
        current_text = self.label_output.get_text()
        new_line = text
        updated_text = f"{current_text}{new_line}\n"
        self.label_output.set_text(updated_text)

        if self._creation_task is not None and new_line.strip():
            self._creation_task.subtitle = new_line.strip()

    @GtkUtils.run_in_main_loop
    def finish(self, result: Optional[Result], error=None) -> None:
        """Updates widgets based on whether it succeeded or failed."""

        def send_notification(notification: Gio.Notification) -> None:
            """Sends notification if out of focus."""
            if not self.window.is_active():
                self.app.send_notification("bottle-created-completed", notification)

        result_config = None
        if result and result.data:
            result_config = result.data.get("config")
            if result_config:
                self.new_bottle_config = result_config

        if self._cancel_requested:
            if result_config:
                self._cleanup_config = result_config
            self.__clear_creation_task()
            self.__start_cancellation_cleanup()
            return

        self.set_can_close(True)
        self.stack_create.set_visible_child_name("page_completed")
        notification = Gio.Notification()

        self.__clear_creation_task()

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
        if (
            self._creation_task is not None
            and self.stack_create.get_visible_child_name() == "page_creating"
        ):
            if self._cancel_requested:
                return
            self.__prompt_cancel_confirmation()
            return

        self.__finalize_close()

    def __prompt_cancel_confirmation(
        self,
        _source: Optional[Gtk.Widget] = None,
    ) -> None:
        if self._cancel_requested:
            return

        def handle_response(dialog: Adw.MessageDialog, response: str) -> None:
            if response == "confirm":
                self.__cancel_creation()
            dialog.destroy()

        dialog = Adw.MessageDialog.new(
            self.window,
            _("Cancel Bottle Creation?"),
            _(
                "Cancelling now will stop the setup once the current step finishes and remove any files created so far."
            ),
        )
        dialog.add_response("keep", _("_Keep Waiting"))
        dialog.add_response("confirm", _("_Delete and Cancel"))
        dialog.set_response_appearance("keep", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_response_appearance("confirm", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("keep")
        dialog.set_close_response("keep")
        dialog.connect("response", handle_response)
        dialog.present()

    def __cancel_creation(self) -> None:
        if self._cancel_requested:
            return

        self._cancel_requested = True
        self._cleanup_config = self.__build_cleanup_config()
        self.set_can_close(False)
        self.btn_cancel_creating.set_sensitive(False)
        self.btn_cancel_creating.set_label(_("Cancelling…"))

        if self._creation_task is not None:
            self._creation_task.subtitle = _("Cancelling…")

        if self._creation_job is not None:
            self._creation_job.cancel()
        if self._creation_cancel_event is not None:
            self._creation_cancel_event.set()

        self.update_output(
            _("Cancellation requested. Waiting for current step to finish before cleaning up…")
        )

    def __finalize_close(self) -> None:
        self.window.disconnect_by_func(self.__remove_notifications)
        self.close()

    def __clear_creation_task(self) -> None:
        if self._creation_task is None:
            return

        if self._creation_task.task_id and TaskManager.get(self._creation_task.task_id):
            TaskManager.remove(self._creation_task)

        self._creation_task = None
        self._creation_job = None
        self._creation_cancel_event = None

    def __build_cleanup_config(self) -> BottleConfig:
        config = BottleConfig()
        name = self.entry_name.get_text()
        config.Name = name
        config.Environment = self.selected_environment.capitalize()
        sanitized = sanitize_filename(name.replace(" ", "-"), platform="universal")

        if self.custom_path:
            config.Path = os.path.join(self.custom_path, sanitized)
            config.Custom_Path = True
        else:
            config.Path = sanitized
            config.Custom_Path = False

        return config

    def __start_cancellation_cleanup(self) -> None:
        if self._cleanup_job is not None:
            return
        cleanup_config = self._cleanup_config or self.__build_cleanup_config()
        self.update_output(_("Removing created files…"))
        self._cleanup_job = RunAsync(
            task_func=self.manager.delete_bottle,
            callback=self.__on_cleanup_finished,
            config=cleanup_config,
        )

    @GtkUtils.run_in_main_loop
    def __on_cleanup_finished(self, success: Optional[bool], error=None) -> None:
        self._cleanup_job = None
        self._cleanup_config = None

        if not success or error:
            self.update_output(
                _("Unable to remove every file automatically. Check the logs for details."),
            )
        else:
            self.update_output(_("Cleanup completed."))

        self.manager.check_bottles()
        self.window.page_list.update_bottles_list()
        self.set_can_close(True)
        self._cancel_requested = False
        self.__finalize_close()
