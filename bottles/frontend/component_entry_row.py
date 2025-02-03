# component_entry_row.py
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

from gettext import gettext as _

from gi.repository import Gtk, GObject, Adw

import logging
from bottles.backend.state import Status
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.gtk import GtkUtils


@Gtk.Template(resource_path="/com/usebottles/bottles/component-entry-row.ui")
class ComponentEntryRow(Adw.ActionRow):
    __gtype_name__ = "ComponentEntryRow"
    __gsignals__ = {
        "component-installed": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "component-error": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    # region Widgets
    btn_download = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()
    btn_remove = Gtk.Template.Child()
    btn_err = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    box_download_status = Gtk.Template.Child()
    label_task_status = Gtk.Template.Child()

    # endregion

    def __init__(
        self, window, component, component_type, is_upgradable=False, **kwargs
    ):
        super().__init__(**kwargs)

        # common variables and references
        self.window = window
        self.manager = window.manager
        self.component_manager = self.manager.component_manager
        self.name = component[0]
        self.component_type = component_type
        self.is_upgradable = is_upgradable

        # populate widgets
        self.set_title(self.name)
        self.set_can_focus(False)

        if component[1].get("Installed"):
            self.btn_browse.set_visible(True)
            if not self.manager.component_manager.is_in_use(
                self.component_type, self.name
            ):
                self.btn_remove.set_visible(True)
        else:
            self.btn_download.set_visible(True)
            self.btn_browse.set_visible(False)

        if is_upgradable:
            self.btn_download.set_icon_name("software-update-available-symbolic")
            self.btn_download.set_tooltip_text(_("Upgrade"))

        # connect signals
        self.btn_download.connect("clicked", self.download)
        self.btn_err.connect("clicked", self.download)
        self.btn_remove.connect("clicked", self.uninstall)
        self.btn_browse.connect("clicked", self.run_browse)

    def download(self, widget):
        @GtkUtils.run_in_main_loop
        def async_callback(result, error=False):
            if not result or result.status:
                return self.set_installed()

            return self.update_progress(status=Status.FAILED)

        @GtkUtils.run_in_main_loop
        def async_func(*args, **kwargs):
            return self.update_progress(*args, **kwargs)

        self.btn_download.set_visible(False)
        self.btn_cancel.set_visible(False)  # TODO: unimplemented
        self.box_download_status.set_visible(True)

        RunAsync(
            task_func=self.component_manager.install,
            callback=async_callback,
            component_type=self.component_type,
            component_name=self.name,
            func=async_func,
        )

    def uninstall(self, widget):
        @GtkUtils.run_in_main_loop
        def update(result, error=False):
            if result.ok:
                return self.set_uninstalled()

            return self.set_err(result.data.get("message"), retry=False)

        self.btn_err.set_visible(False)
        self.btn_remove.set_visible(False)

        RunAsync(
            task_func=self.component_manager.uninstall,
            callback=update,
            component_type=self.component_type,
            component_name=self.name,
        )

    def run_browse(self, widget):
        self.btn_download.set_visible(False)

        ManagerUtils.open_filemanager(
            path_type=self.component_type, component=self.name
        )

    def update_progress(
        self,
        received_size: int = 0,
        total_size: int = 0,
        status: Status | None = None,
    ):
        if status == Status.FAILED:
            logging.error("Component installation failed")
            self.set_err()
            return False

        self.box_download_status.set_visible(True)

        percent = int(received_size * 100 / total_size)
        self.label_task_status.set_text(f"{percent}%")

        if percent >= 100:
            self.label_task_status.set_text(_("Installing…"))

    def set_err(self, msg=None, retry=True):
        self.box_download_status.set_visible(False)
        self.btn_remove.set_visible(False)
        self.btn_cancel.set_visible(False)
        self.btn_browse.set_visible(False)
        self.btn_err.set_visible(True)
        if msg:
            self.btn_err.set_tooltip_text(msg)
        if not retry:
            self.btn_err.set_sensitive(False)

    def set_installed(self):
        self.btn_err.set_visible(False)
        self.box_download_status.set_visible(False)
        self.btn_browse.set_visible(True)
        self.btn_cancel.set_visible(False)
        if not self.manager.component_manager.is_in_use(self.component_type, self.name):
            self.btn_remove.set_visible(True)

    def set_uninstalled(self):
        self.btn_browse.set_visible(False)
        self.btn_err.set_visible(False)
        self.btn_download.set_visible(True)
        if self.name in self.manager.get_offline_components(
            self.component_type, self.name
        ):
            self.set_visible(False)


class ComponentExpander(Adw.ExpanderRow):
    def __init__(self, title, subtitle=None, **kwargs):
        super().__init__(**kwargs)

        self.set_title(title)
        if subtitle:
            self.set_subtitle(subtitle)
