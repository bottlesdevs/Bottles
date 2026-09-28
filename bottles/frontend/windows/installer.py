# installer.py
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

import time
import urllib.error
import urllib.request
from gettext import gettext as _
from typing import Optional

from gi.repository import Adw, GdkPixbuf, Gio, GLib, Gtk

from bottles.backend.utils.threading import RunAsync
from bottles.frontend.utils.gtk import GtkUtils


INSTALLER_ICON_USER_AGENT = "Bottles"


def fetch_installer_icon(url: str | None) -> bytes | None:
    if url is None:
        return None

    request = urllib.request.Request(
        url,
        headers={"User-Agent": INSTALLER_ICON_USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
        return None


@Gtk.Template(resource_path="/com/usebottles/bottles/local-resource-entry.ui")
class LocalResourceEntry(Adw.ActionRow):
    __gtype_name__ = "LocalResourceEntry"

    # region Widgets
    btn_path = Gtk.Template.Child()

    # endregion

    def __init__(self, parent, resource, **kwargs):
        super().__init__(**kwargs)

        # common variables and references
        self.parent = parent
        self.resource = resource

        self.set_title(resource)

        # connect signals
        self.btn_path.connect("clicked", self.__choose_path)

    def __choose_path(self, *_args):
        """
        Open the file chooser dialog and set the path to the
        selected file
        """

        def set_path(_dialog, response):
            if response != Gtk.ResponseType.ACCEPT:
                return

            path = dialog.get_file().get_path()
            self.parent.add_resource(self.resource, path)
            self.set_subtitle(path)

        dialog = Gtk.FileChooserNative.new(
            title=_("Select Resource File"),
            action=Gtk.FileChooserAction.OPEN,
            parent=self.parent,
        )

        dialog.set_modal(True)
        dialog.connect("response", set_path)
        dialog.show()


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-installer.ui")
class InstallerDialog(Adw.Window):
    __gtype_name__ = "InstallerDialog"
    __sections = {}
    __steps = 0
    __current_step = 0
    __local_resources = []
    __final_resources = {}

    # region widgets
    stack = Gtk.Template.Child()
    window_title = Gtk.Template.Child()
    btn_install = Gtk.Template.Child()
    btn_proceed = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    status_init = Gtk.Template.Child()
    status_installed = Gtk.Template.Child()
    status_error = Gtk.Template.Child()
    progressbar = Gtk.Template.Child()
    label_activity = Gtk.Template.Child()
    label_elapsed = Gtk.Template.Child()
    btn_details = Gtk.Template.Child()
    details_revealer = Gtk.Template.Child()
    details_view = Gtk.Template.Child()
    group_resources = Gtk.Template.Child()
    install_status_page = Gtk.Template.Child()
    img_icon = Gtk.Template.Child()
    img_icon_install = Gtk.Template.Child()
    style_provider = Gtk.CssProvider()

    # endregion

    def __init__(self, window, config, installer, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(window)

        self.window = window
        self.manager = window.manager
        self.config = config
        self.installer = installer
        self.__sections = []
        self.__steps = 0
        self.__current_step = 0
        self.__log_lines = []
        self.__elapsed_source = None
        self.__started_at = None

        self.__steps_phrases = {
            "deps": _("Installing Windows dependencies…"),
            "params": _("Configuring the bottle…"),
            "steps": _("Processing installer steps…"),
            "exe": _("Installing the {}…".format(installer[1].get("Name"))),
            "checks": _("Performing final checks…"),
        }

        self.status_init.set_title(installer[1].get("Name"))
        self.install_status_page.set_title(
            _("Installing {0}…").format(installer[1].get("Name"))
        )
        self.status_installed.set_description(
            _("{0} is now available in the programs view.").format(
                installer[1].get("Name")
            )
        )
        self.__set_icon()

        self.btn_install.connect("clicked", self.__check_resources)
        self.btn_proceed.connect("clicked", self.__install)
        self.btn_close.connect("clicked", self.__close)
        self.btn_details.connect("clicked", self.__toggle_details)

    def __set_icon(self):
        def fetch_icon():
            url = self.manager.installer_manager.get_icon_url(self.installer[0])
            return fetch_installer_icon(url)

        def set_icon(data, error):
            if error is not None or data is None:
                self.img_icon.set_visible(False)
                self.img_icon_install.set_visible(False)
                return

            try:
                stream = Gio.MemoryInputStream.new_from_data(data, None)
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream(stream, None)
                self.img_icon.set_pixel_size(78)
                self.img_icon.set_from_pixbuf(pixbuf)
                self.img_icon_install.set_pixel_size(78)
                self.img_icon_install.set_from_pixbuf(pixbuf)
            except GLib.Error:
                self.img_icon.set_visible(False)
                self.img_icon_install.set_visible(False)

        RunAsync(fetch_icon, callback=set_icon)

    def __check_resources(self, *_args):
        self.__local_resources = self.manager.installer_manager.has_local_resources(
            self.installer
        )
        if len(self.__local_resources) == 0:
            self.__install()
            return

        for resource in self.__local_resources:
            _entry = LocalResourceEntry(self, resource)
            GLib.idle_add(self.group_resources.add, _entry)

        self.btn_proceed.set_visible(True)
        self.stack.set_visible_child_name("page_resources")

    def __install(self, *_args):
        self.set_deletable(False)
        self.stack.set_visible_child_name("page_install")
        self.__started_at = time.monotonic()
        self.__elapsed_source = GLib.timeout_add_seconds(1, self.__update_elapsed)
        self.label_activity.set_label(_("Preparing installer..."))

        @GtkUtils.run_in_main_loop
        def set_status(result, error=False):
            if result is None:
                message = str(error) if error else _("Installer failed unexpectedly")
                self.__error(message)
                return

            if result.ok:
                return self.__installed()
            _err = result.data.get("message", _("Installer failed with unknown error"))
            self.__error(_err)

        self.set_steps(self.manager.installer_manager.count_steps(self.installer))

        RunAsync(
            task_func=self.manager.installer_manager.install,
            callback=set_status,
            config=self.config,
            installer=self.installer,
            step_fn=self.next_step,
            local_resources=self.__final_resources,
            progress_fn=self.update_progress,
            activity_fn=self.update_activity,
            log_fn=self.add_log,
        )

    def __installed(self):
        self.__stop_activity()
        self.set_deletable(False)
        self.stack.set_visible_child_name("page_installed")
        self.window.page_details.view_bottle.update_programs(force_update=True)
        self.window.page_details.go_back_sidebar()

    def __error(self, error):
        self.__stop_activity()
        self.set_deletable(True)
        self.status_error.set_description(error)
        self.stack.set_visible_child_name("page_error")

    @GtkUtils.run_in_main_loop
    def next_step(self, detail=None):
        """Next step"""
        section = self.__sections[self.__current_step]

        if section == "deps" and detail is not None:
            phrase = _("Installing dependency: {0}").format(detail)
        else:
            phrase = self.__steps_phrases[section]

        self.label_activity.set_label(phrase)
        self.__current_step += 1
        self.progressbar.set_fraction(self.__current_step * (1 / self.__steps))
        self.progressbar.set_show_text(False)

    @GtkUtils.run_in_main_loop
    def update_progress(self, fraction: Optional[float]):
        if fraction is None:
            fraction = self.__current_step / self.__steps if self.__steps else 0
            self.progressbar.set_fraction(fraction)
            self.progressbar.set_show_text(False)
            return

        fraction = max(0.0, min(1.0, fraction))
        self.progressbar.set_fraction(fraction)
        self.progressbar.set_text(f"{int(fraction * 100)}%")
        self.progressbar.set_show_text(True)

    @GtkUtils.run_in_main_loop
    def update_activity(self, command: Optional[str]):
        if command:
            self.label_activity.set_label(_("Running {0}...").format(command))
            return
        self.label_activity.set_label(_("Preparing the next step..."))

    @GtkUtils.run_in_main_loop
    def add_log(self, line: str):
        if not line:
            return

        self.__log_lines.append(line)
        self.__log_lines = self.__log_lines[-200:]
        self.details_view.get_buffer().set_text("\n".join(self.__log_lines))
        self.btn_details.set_visible(True)

    def __update_elapsed(self):
        if self.__started_at is None:
            return GLib.SOURCE_REMOVE

        elapsed = int(time.monotonic() - self.__started_at)
        hours, elapsed = divmod(elapsed, 3600)
        minutes, seconds = divmod(elapsed, 60)
        if hours:
            value = f"{hours:d}:{minutes:02d}:{seconds:02d}"
        else:
            value = f"{minutes:02d}:{seconds:02d}"
        self.label_elapsed.set_label(_("Active for {0}").format(value))
        return GLib.SOURCE_CONTINUE

    def __stop_activity(self):
        if self.__elapsed_source:
            GLib.source_remove(self.__elapsed_source)
            self.__elapsed_source = None
        self.__started_at = None

    def __toggle_details(self, *_args):
        reveal = not self.details_revealer.get_reveal_child()
        self.details_revealer.set_reveal_child(reveal)
        self.btn_details.set_label(_("Hide Details") if reveal else _("Show Details"))

    def set_steps(self, steps):
        """Set steps"""
        self.__steps = steps["total"]
        self.__sections = steps["sections"]

    def add_resource(self, resource, path):
        self.__final_resources[resource] = path
        if len(self.__local_resources) == len(self.__final_resources):
            self.btn_proceed.set_sensitive(True)

    def __close(self, *_args):
        self.__stop_activity()
        self.destroy()
