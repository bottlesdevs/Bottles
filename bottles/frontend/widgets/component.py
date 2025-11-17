# component.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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
from threading import Event
from typing import Dict, Optional

from gi.repository import Adw, GObject, Gtk

from bottles.backend.logger import Logger
from bottles.backend.state import Status
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.utils.gtk import GtkUtils

logging = Logger()


@Gtk.Template(resource_path="/com/usebottles/bottles/component-entry.ui")
class ComponentEntry(Adw.ActionRow):
    __gtype_name__ = "ComponentEntry"
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
    spinner = Gtk.Template.Child()

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
        self._download_task: Optional[RunAsync] = None
        self._cancel_event: Optional[Event] = None
        self._cancelled_during_download = False
        self._pre_download_visibility: Optional[Dict[str, bool]] = None

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
        self.btn_cancel.connect("clicked", self.cancel_download)

    def download(self, widget):
        @GtkUtils.run_in_main_loop
        def async_callback(result, error=False):
            self._clear_download_context()

            if self._cancelled_during_download:
                self._cancelled_during_download = False
                return False

            if result and getattr(result, "message", "") == "cancelled":
                self._restore_pre_download_visibility()
                return False

            if result and getattr(result, "ok", False):
                self._pre_download_visibility = None
                return self.set_installed()

            return self.update_progress(status=Status.FAILED)

        @GtkUtils.run_in_main_loop
        def async_func(
            received_size: int = 0,
            total_size: int = 0,
            status: Optional[Status] = None,
        ):
            return self.update_progress(
                received_size=received_size,
                total_size=total_size,
                status=status,
            )

        self._cancel_event = Event()
        self._cancelled_during_download = False
        self._pre_download_visibility = {
            "btn_download": self.btn_download.get_visible(),
            "btn_browse": self.btn_browse.get_visible(),
            "btn_remove": self.btn_remove.get_visible(),
        }

        self.btn_download.set_visible(False)
        self.btn_cancel.set_visible(True)
        self.btn_cancel.set_sensitive(True)
        self.box_download_status.set_visible(True)
        self._set_spinner_active(True)
        self.label_task_status.set_text(_("Calculating…"))

        self._download_task = RunAsync(
            task_func=self.component_manager.install,
            callback=async_callback,
            component_type=self.component_type,
            component_name=self.name,
            func=async_func,
            cancel_event=self._cancel_event,
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
        status: Optional[Status] = None,
    ):
        if status == Status.FAILED:
            logging.error("Component installation failed")
            self.set_err()
            self._clear_download_context()
            return False

        if status == Status.CANCELLED:
            self._cancelled_during_download = True
            self._restore_pre_download_visibility()
            return False

        received_size = self._sanitize_progress_value(received_size)
        total_size = self._sanitize_progress_value(total_size)

        self.box_download_status.set_visible(True)
        self.btn_cancel.set_visible(True)

        if total_size <= 0:
            self.label_task_status.set_text(_("Calculating…"))
            self._set_spinner_active(True)
            return True

        if self._cancel_event and self._cancel_event.is_set():
            return False

        self._set_spinner_active(False)

        if total_size == 0:
            percent = 0
        else:
            bounded_received = min(received_size, total_size)
            percent = int(bounded_received * 100 / total_size)

        self.label_task_status.set_text(f"{percent}%")

        if percent >= 100:
            self.label_task_status.set_text(_("Installing…"))

    def set_err(self, msg=None, retry=True):
        self.box_download_status.set_visible(False)
        self.btn_remove.set_visible(False)
        self.btn_cancel.set_visible(False)
        self.btn_browse.set_visible(False)
        self._set_spinner_active(False)
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
        self._set_spinner_active(False)
        if not self.manager.component_manager.is_in_use(self.component_type, self.name):
            self.btn_remove.set_visible(True)

    def set_uninstalled(self):
        self.btn_browse.set_visible(False)
        self.btn_err.set_visible(False)
        self.btn_download.set_visible(True)
        self._set_spinner_active(False)
        if self.name in self.manager.get_offline_components(
            self.component_type, self.name
        ):
            self.set_visible(False)

    def cancel_download(self, widget):
        if not self._cancel_event or self._cancel_event.is_set():
            return

        self._cancel_event.set()
        self.btn_cancel.set_sensitive(False)
        self.label_task_status.set_text(_("Cancelling…"))
        self._set_spinner_active(True)
        if self._download_task:
            self._download_task.cancel()

    def _restore_pre_download_visibility(self):
        self._set_spinner_active(False)
        self.box_download_status.set_visible(False)
        self.btn_cancel.set_visible(False)
        self.btn_cancel.set_sensitive(True)
        self.btn_err.set_visible(False)
        self.label_task_status.set_text("0%")

        if self._pre_download_visibility:
            self.btn_download.set_visible(
                self._pre_download_visibility.get("btn_download", True)
            )
            self.btn_browse.set_visible(
                self._pre_download_visibility.get("btn_browse", False)
            )
            self.btn_remove.set_visible(
                self._pre_download_visibility.get("btn_remove", False)
            )
        else:
            self.btn_download.set_visible(True)

        self._pre_download_visibility = None

    def _set_spinner_active(self, active: bool):
        if not self.spinner:
            return
        self.spinner.set_visible(active)
        if active:
            self.spinner.start()
        else:
            self.spinner.stop()

    @staticmethod
    def _sanitize_progress_value(value: Optional[int]) -> int:
        try:
            if value is None:
                return 0
            coerced = int(value)
        except (TypeError, ValueError):
            return 0

        if coerced < 0:
            return 0

        return coerced

    def _clear_download_context(self):
        self._set_spinner_active(False)
        self._cancel_event = None
        self._download_task = None


class ComponentExpander(Adw.ExpanderRow):
    def __init__(self, title, subtitle=None, **kwargs):
        super().__init__(**kwargs)

        self.set_title(title)
        if subtitle:
            self.set_subtitle(subtitle)
