from gettext import gettext as _
from threading import Event
from typing import Optional

from gi.repository import Adw, GLib, Gtk

from bottles.backend.models.result import Result
from bottles.backend.state import Status
from bottles.backend.utils.threading import RunAsync
from bottles.frontend.utils.gtk import GtkUtils


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-winebridge-update.ui")
class WineBridgeUpdateDialog(Adw.Window):
    __gtype_name__ = "WineBridgeUpdateDialog"

    stack_switcher = Gtk.Template.Child()
    btn_cancel = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    btn_update = Gtk.Template.Child()
    status_page = Gtk.Template.Child()
    status_done = Gtk.Template.Child()
    status_error = Gtk.Template.Child()
    progressbar = Gtk.Template.Child()
    label_status = Gtk.Template.Child()
    window_title = Gtk.Template.Child()

    def __init__(
        self,
        parent,
        manager,
        latest_version: Optional[str],
        installed_version: Optional[str],
        offline: bool = False,
    ):
        super().__init__(transient_for=parent, modal=True)

        self.manager = manager
        self.latest_version = latest_version
        self.installed_version = installed_version
        self.offline = offline
        self._installing = False
        self._cancel_event: Optional[Event] = None

        self.window_title.set_title(_("WineBridge update"))
        self.btn_update.connect("clicked", self.__start_update)
        self.btn_close.connect("clicked", self.__close)
        self.btn_cancel.connect("clicked", self.__on_cancel)

        self.__populate_details()

    def __populate_details(self):
        description = _(
            "WineBridge is a core component for Bottles. Updating ensures stability, performance, and compatibility with the latest features."
        )
        warning = _(
            "Declining can cause instability, performance degradation, and incompatibilities with new Bottles releases."
        )

        if self.offline:
            warning = (
                warning
                + " "
                + _("Restart Bottles once internet is available to install it.")
            )
            self.btn_update.set_sensitive(False)
            self.btn_update.set_tooltip_text(
                _("Connect to the internet to update WineBridge.")
            )

        self.status_page.set_title(_("%s Available") % self.latest_version)
        self.status_page.set_description(description + "\n\n" + warning)

    def __start_update(self, *_args):
        if not self.latest_version:
            self.__show_error()
            return

        self._installing = True
        self._cancel_event = Event()
        self.btn_update.set_sensitive(False)
        self.btn_cancel.set_sensitive(True)
        self.btn_close.set_visible(False)
        self.stack_switcher.set_visible_child_name("page_progress")
        self.progressbar.set_fraction(0)
        self.progressbar.set_text("0%")
        self.label_status.set_label(_("Downloading WineBridge…"))

        RunAsync(
            task_func=self.manager.component_manager.install,
            callback=self.__on_install_complete,
            component_type="winebridge",
            component_name=self.latest_version,
            func=self.__update_progress,
            cancel_event=self._cancel_event,
        )

    def __on_cancel(self, *_args):
        if self._installing and self._cancel_event:
            self._cancel_event.set()
            self.btn_cancel.set_sensitive(False)
            self.label_status.set_label(_("Cancelling…"))
            return

        self.close()

    def __close(self, *_args):
        self.close()

    def __show_error(self):
        self._installing = False
        self.btn_cancel.set_sensitive(False)
        self.btn_update.set_visible(False)
        self.btn_close.set_visible(True)
        self.stack_switcher.set_visible_child_name("page_error")

    def __update_progress(
        self,
        received: int = 0,
        total: int = 0,
        status: Optional[Status] = None,
        **_kwargs,
    ):
        if status == Status.CANCELLED:
            GLib.idle_add(self.__show_error)
            return

        if not total:
            return

        fraction = received / total
        GLib.idle_add(self.progressbar.set_fraction, fraction)
        GLib.idle_add(self.progressbar.set_text, f"{int(fraction * 100)}%")
        GLib.idle_add(
            self.label_status.set_label,
            _("Updating WineBridge… ({percent}%)").format(percent=int(fraction * 100)),
        )

    @GtkUtils.run_in_main_loop
    def __on_install_complete(self, result: Result, error=False):
        self._installing = False
        if error or not result.ok:
            self.__show_error()
            return

        self.progressbar.set_fraction(1)
        self.progressbar.set_text("100%")
        self.btn_update.set_visible(False)
        self.btn_cancel.set_visible(False)
        self.btn_close.set_visible(True)
        self.stack_switcher.set_visible_child_name("page_done")
