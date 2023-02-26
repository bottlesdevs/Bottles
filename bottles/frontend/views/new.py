# new.py: Create new bottle interface
#
# Copyright 2022 Bottles Contributors
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
from gi.repository import Gtk, Adw, Pango, Gio

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.utils.filters import add_yaml_filters, add_all_filters
from bottles.frontend.utils.gtk import GtkUtils


@Gtk.Template(resource_path="/com/usebottles/bottles/new.ui")
class NewView(Adw.Window):
    __gtype_name__ = "NewView"

    # region Widgets
    application = Gtk.Template.Child()
    gaming = Gtk.Template.Child()
    custom = Gtk.Template.Child()
    check_application = Gtk.Template.Child()
    check_gaming = Gtk.Template.Child()
    check_custom = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    stack_create = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    btn_choose_env = Gtk.Template.Child()
    btn_choose_env_reset = Gtk.Template.Child()
    label_choose_env = Gtk.Template.Child()
    btn_choose_path = Gtk.Template.Child()
    btn_choose_path_reset = Gtk.Template.Child()
    label_choose_path = Gtk.Template.Child()
    status_statuses = Gtk.Template.Child()
    switch_sandbox = Gtk.Template.Child()
    label_output = Gtk.Template.Child()
    scrolled_output = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    combo_arch = Gtk.Template.Child()
    str_list_arch = Gtk.Template.Child()
    row_sandbox = Gtk.Template.Child()
    headerbar = Gtk.Template.Child()
    shortcut_escape = Gtk.Template.Child()
    str_list_runner = Gtk.Template.Child()
    group_custom = Gtk.Template.Child()
    menu_duplicate = Gtk.Template.Child()

    # endregion

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)
        # common variables and references
        self.app = window.app
        self.window = window
        self.manager = window.manager
        self.new_bottle_config = BottleConfig()
        self.env_recipe_path = None
        self.custom_path = ""
        self.is_closable = True
        self.runner = None
        self.default_string = _("(Default)")

        self.arch = {
            "win64": "64-bit",
            "win32": "32-bit"
        }

        # connect signals
        self.check_custom.connect("toggled", self.__set_group)
        self.btn_cancel.connect("clicked", self.do_close_request)
        self.btn_close.connect("clicked", self.do_close_request)
        self.btn_create.connect("clicked", self.create_bottle)
        self.btn_choose_env.connect("clicked", self.__choose_env_recipe)
        self.btn_choose_env_reset.connect("clicked", self.__reset_env_recipe)
        self.btn_choose_path.connect("clicked", self.__choose_path)
        self.btn_choose_path_reset.connect("clicked", self.__reset_path)
        self.entry_name.connect("changed", self.__check_entry_name)

        # Populate widgets
        self.label_choose_env.set_label(self.default_string)
        self.label_choose_path.set_label(self.default_string)
        self.str_list_runner.splice(0, 0, self.manager.runners_available)
        self.str_list_arch.splice(0, 0, list(self.arch.values()))

        # Hide row_sandbox if under Flatpak
        self.row_sandbox.set_visible(not os.environ.get("FLATPAK_ID"))

        # focus on the entry_name
        self.entry_name.grab_focus()

    def __set_group(self, *_args) -> None:
        """ Checks the state of combo_environment and updates group_custom accordingly. """
        self.group_custom.set_sensitive(self.check_custom.get_active())

    def __check_entry_name(self, *_args) -> None:
        is_duplicate = self.entry_name.get_text() in self.manager.local_bottles
        is_invalid = is_duplicate or self.entry_name.get_text() == ""
        self.btn_create.set_sensitive(not is_invalid)
        self.menu_duplicate.set_visible(is_duplicate)

        if is_invalid:
            self.entry_name.add_css_class("error")
        else:
            self.entry_name.remove_css_class("error")

    def __choose_env_recipe(self, *_args) -> None:
        """
        Opens a file chooser dialog to select the configuration file
        in yaml format.
        """
        def set_path(_dialog, response: Gtk.ResponseType):
            if response == Gtk.ResponseType.ACCEPT:
                self.btn_choose_env_reset.set_visible(True)
                self.env_recipe_path = dialog.get_file().get_path()
                self.label_choose_env.set_label(dialog.get_file().get_basename())
                self.label_choose_env.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select a Configuration File"),
            action=Gtk.FileChooserAction.OPEN,
            parent=self.window,
        )

        add_yaml_filters(dialog)
        add_all_filters(dialog)
        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def __choose_path(self, *_args) -> None:
        """ Opens a file chooser dialog to select the directory. """
        def set_path(_dialog, response: Gtk.ResponseType) -> None:
            if response == Gtk.ResponseType.ACCEPT:
                self.btn_choose_path_reset.set_visible(True)
                self.custom_path = dialog.get_file().get_path()
                self.label_choose_path.set_label(dialog.get_file().get_basename())
                self.label_choose_path.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Bottle Directory"),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            parent=self.window
        )

        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()

    def create_bottle(self, *_args) -> None:
        """ Starts creating the bottle. """
        # set widgets states
        self.is_closable = False
        self.btn_cancel.set_visible(False)
        self.btn_create.set_visible(False)
        self.set_title("")
        self.headerbar.add_css_class("flat")
        self.shortcut_escape.set_action(None)
        self.stack_create.set_visible_child_name("page_statuses")
        self.status_statuses.set_title(_("Creating Bottle…"))
        self.status_statuses.set_description(_("This could take a while."))

        if self.check_custom.get_active():
            self.runner = self.manager.runners_available[self.combo_runner.get_selected()]

        RunAsync(
            task_func=self.manager.create_bottle,
            callback=self.finish,
            name=self.entry_name.get_text(),
            path=self.custom_path,
            environment=self.__radio_get_active(),
            runner=self.runner,
            arch=list(self.arch)[self.combo_arch.get_selected()],
            dxvk=self.manager.dxvk_available[0],
            sandbox=self.switch_sandbox.get_state(),
            fn_logger=self.update_output,
            custom_environment=self.env_recipe_path
        )

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
    def finish(self, result, error=None) -> None:
        """ Updates widgets based on whether it succeeded or failed. """

        def send_notification(notification: Gio.Notification) -> None:
            """ Sends notification if out of focus. """
            if not self.is_active():
                self.app.send_notification(None, notification)

        self.status_statuses.set_description(None)
        self.is_closable = True
        notification = Gio.Notification()

        # Show error if bottle unsuccessfully builds
        if not result or not result.status or error:
            title = _("Unable to Create Bottle")
            self.btn_cancel.set_visible(False)
            self.btn_close.set_visible(True)
            notification.set_title(title)
            notification.set_body(_("Bottle failed to create with one or more errors."))
            self.status_statuses.set_title(title)
            self.btn_close.get_style_context().add_class("destructive-action")
            send_notification(notification)
            return

        # Show success
        title = _("Bottle Created")
        description = _("\"{0}\" was created successfully.").format(
                self.entry_name.get_text()
            )

        notification.set_title(title)
        notification.set_body(description)

        self.new_bottle_config = result.data.get("config")
        self.scrolled_output.set_visible(False)
        self.btn_close.set_visible(True)
        self.btn_close.get_style_context().add_class("suggested-action")
        self.status_statuses.set_icon_name("selection-mode-symbolic")
        self.status_statuses.set_title(title)
        self.status_statuses.set_description(description)
        send_notification(notification)

        # Ask the manager to check for new bottles,
        # then update the user bottles' list.
        self.manager.check_bottles()
        self.window.page_list.update_bottles(show=result.data.get("config").get("Path"))

    def __radio_get_active(self) -> str:
        # TODO: Remove this ugly zig zag and find a better way to set the environment
        # https://docs.gtk.org/gtk4/class.CheckButton.html#grouping
        if self.check_application.get_active():
            return "application"
        if self.check_gaming.get_active():
            return "gaming"
        return "custom"

    def __reset_env_recipe(self, _widget: Gtk.Button) -> None:
        self.btn_choose_env_reset.set_visible(False)
        self.env_recipe_path = None
        self.label_choose_env.set_label(self.default_string)

    def __reset_path(self, _widget: Gtk.Button) -> None:
        self.btn_choose_path_reset.set_visible(False)
        self.custom_path = ""
        self.label_choose_path.set_label(self.default_string)

    def do_close_request(self, *_args) -> bool:
        """ Close window if a new bottle is not being created """
        if self.is_closable is False:
            # TODO: Implement AdwMessageDialog to prompt the user if they are
            # SURE they want to cancel creation. For now, the window will not
            # react if the user attempts to close the window while a bottle
            # is being created in a feature update
            return True
        self.close()
        return False
