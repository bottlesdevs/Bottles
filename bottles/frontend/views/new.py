# new.py
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
from gettext import gettext as _
from gi.repository import Gtk, Adw, Pango

from bottles.frontend.utils.threading import RunAsync
from bottles.frontend.utils.gtk import GtkUtils
from bottles.frontend.utils.filters import add_yaml_filters, add_all_filters

from bottles.backend.runner import Runner
from bottles.backend.wine.executor import WineExecutor


@Gtk.Template(resource_path='/com/usebottles/bottles/new.ui')
class NewView(Adw.Window):
    __gtype_name__ = 'NewView'

    # region Widgets
    check_gaming = Gtk.Template.Child()
    check_application = Gtk.Template.Child()
    check_custom = Gtk.Template.Child()
    entry_name = Gtk.Template.Child()
    stack_create = Gtk.Template.Child()
    btn_create = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    btn_choose_env = Gtk.Template.Child()
    label_choose_env = Gtk.Template.Child()
    btn_choose_path = Gtk.Template.Child()
    label_choose_path = Gtk.Template.Child()
    status_statuses = Gtk.Template.Child()
    switch_sandbox = Gtk.Template.Child()
    label_output = Gtk.Template.Child()
    scrolled_output = Gtk.Template.Child()
    combo_runner = Gtk.Template.Child()
    combo_arch = Gtk.Template.Child()
    row_sandbox = Gtk.Template.Child()
    headerbar = Gtk.Template.Child()
    shortcut_escape = Gtk.Template.Child()
    str_list_runner = Gtk.Template.Child()
    group_custom = Gtk.Template.Child()

    # endregion

    def __init__(self, window, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)
        # common variables and references
        self.window = window
        self.manager = window.manager
        self.new_bottle_config = {}

        # connect signals
        self.check_custom.connect("toggled", self.__set_group)
        self.btn_cancel.connect("clicked", self.do_close_request)
        self.btn_close.connect("clicked", self.do_close_request)
        self.btn_create.connect("clicked", self.create_bottle)
        self.btn_choose_env.connect("clicked", self.choose_env_recipe)
        self.btn_choose_path.connect("clicked", self.choose_path)
        self.entry_name.connect('changed', self.__check_entry_name)

        # Populate combo_runner with runner versions from the manager
        self.str_list_runner.splice(0, 0, self.manager.runners_available)

        rs, rc, rv, rl, ry = [], [], [], [], []

        for i in self.manager.runners_available:
            if i.startswith('soda'):
                rs.append(i)
            elif i.startswith('caffe'):
                rc.append(i)
            elif i.startswith('vaniglia'):
                rv.append(i)
            elif i.startswith('lutris'):
                rl.append(i)
            elif i.startswith('sys-'):
                ry.append(i)

        if len(rs) > 0:  # use the latest from Soda
            self.runner = rs[0]
        elif len(rc) > 0:  # use the latest from caffe
            self.runner = rc[0]
        elif len(rv) > 0:  # use the latest from vaniglia
            self.runner = rv[0]
        elif len(rl) > 0:  # use the latest from lutris
            self.runner = rl[0]
        elif len(ry) > 0:  # use the latest from system
            self.runner = ry[0]
        else:  # use any other runner available
            self.runner = self.manager.runners_available[0]

        self.combo_runner.set_selected(self.manager.runners_available.index(self.runner))
        self.combo_arch.set_selected(0)

        # Hide row_sandbox if under Flatpak
        self.row_sandbox.set_visible(not os.environ.get("FLATPAK_ID"))

        # focus on the entry_name
        self.entry_name.grab_focus()

    def __set_group(self, widget: Gtk.CheckButton) -> None:
        """ Checks the state of check_custom and updates group_custom accordingly. """
        self.group_custom.set_sensitive(self.check_custom.get_active())

    def set_active_env(self, widget, row):
        """
        This function set the active environment on row selection.
        """
        self.selected_env = row.get_buildable_id()

    def __check_entry_name(self, *_args):
        is_duplicate = self.entry_name.get_text() in self.manager.local_bottles
        if is_duplicate:
            self.window.show_toast(_("This bottle name is already in use."))
            self.entry_name.add_css_class("error")
            self.btn_create.set_sensitive(False)
        else:
            self.entry_name.remove_css_class("error")
            self.btn_create.set_sensitive(True)
    
    def choose_env_recipe(self, *_args) -> None:
        """
        Opens a file chooser dialog to select the configuration file
        in yaml format.
        """
        def set_path(_dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
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

    def choose_path(self, *_args) -> None:
        """ Opens a file chooser dialog to select the directory. """
        def set_path(_dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
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

        environment = self.__radio_get_active()

        if environment == "custom":
            self.runner = self.manager.runners_available[self.combo_runner.get_selected()]

        RunAsync(
            task_func=self.manager.create_bottle,
            callback=self.finish,
            name=self.entry_name.get_text(),
            path=getattr(self, "custom_path", ""),
            environment=environment,
            runner=getattr(self, "runner", None),
            arch="win32" if self.combo_arch.get_selected() else "win64",
            dxvk=self.manager.dxvk_available[0],
            sandbox=self.switch_sandbox.get_state(),
            fn_logger=self.update_output,
            custom_environment=getattr(self, "env_recipe_path", None)
        )

    def update_output(self, text: str) -> None:
        """
        Updates label_output with the given text by concatenating
        with the previous text.
        """
        current_text = self.label_output.get_text()
        text = f"{current_text}{text}\n"
        self.label_output.set_text(text)

    def finish(self, result, error=None) -> None:
        """ Updates widgets based on whether it succeeded or failed. """
        self.status_statuses.set_description(None)
        self.is_closable = True

        # Show error if bottle unsuccessfully builds
        if not result or not result.status or error:
            self.btn_cancel.set_visible(False)
            self.btn_close.set_visible(True)
            self.status_statuses.set_title(_("Unable to Create Bottle"))
            self.btn_close.get_style_context().add_class("destructive-action")
            return

        # Show success
        self.new_bottle_config = result.data.get("config")
        self.scrolled_output.set_visible(False)
        self.btn_close.set_visible(True)
        self.btn_close.get_style_context().add_class("suggested-action")
        self.status_statuses.set_icon_name("selection-mode-symbolic")
        self.status_statuses.set_title(_("Bottle Created"))
        self.status_statuses.set_description(
            _("\"{0}\" was created successfully.").format(
                self.entry_name.get_text()
            )
        )

        # Ask the manager to check for new bottles,
        # then update the user bottles' list.
        self.manager.check_bottles()
        self.window.page_list.update_bottles(show=result.data.get("config").get("Path"))

    def __radio_get_active(self) -> str:
        """ Sets active environment based on user selection. """
        # TODO: Remove this ugly zig zag and find a better way to set the environment
        if self.check_gaming.get_active():
            return "gaming"
        elif self.check_application.get_active():
            return "application"
        else:
            return "custom"

    def do_close_request(self, *args):
        """ Close window if a new bottle is not being created """
        if getattr(self, "is_closable", True) == False:
            # TODO: Implement AdwMessageDialog to prompt the user if they are
            # SURE they want to cancel creation. For now, the window will not
            # react if the user attempts to close the window while a bottle
            # is being created
            return True
        else:
            self.close()
            return False
