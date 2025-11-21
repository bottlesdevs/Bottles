# dependency_install.py
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
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from gettext import gettext as _
from typing import List, Optional

from gi.repository import Adw, GLib, Gtk

from bottles.frontend.utils.gtk import GtkUtils


@Gtk.Template(resource_path="/com/usebottles/bottles/dialog-dependency-install.ui")
class DependencyInstallDialog(Adw.Window):
    __gtype_name__ = "DependencyInstallDialog"

    # region widgets
    label_title = Gtk.Template.Child()
    label_status = Gtk.Template.Child()
    progress_download = Gtk.Template.Child()
    steps_list = Gtk.Template.Child()
    spinner_progress = Gtk.Template.Child()
    btn_close = Gtk.Template.Child()
    # endregion

    def __init__(self, parent, dependency_name: str, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent)

        self.dependency_name = dependency_name
        self._steps: List[Adw.ActionRow] = []

        self.label_title.set_label(_("Installing “{0}”…").format(dependency_name))
        self.label_status.set_label(_("Preparing installation…"))
        self.progress_download.set_visible(False)
        self.btn_close.set_sensitive(False)
        self.spinner_progress.start()

        self.btn_close.connect("clicked", self.__on_close_clicked)

    def __create_step_row(self, text: str) -> Adw.ActionRow:
        row = Adw.ActionRow(title=text)
        row.set_activatable(False)
        row.set_selectable(False)

        check_image = Gtk.Image.new_from_icon_name("selection-mode-symbolic")
        check_image.add_css_class("accent")
        check_image.set_visible(False)

        row.add_suffix(check_image)
        row._completion_icon = check_image  # type: ignore[attr-defined]

        return row

    def __mark_last_step_completed(self) -> None:
        if not self._steps:
            return

        icon = getattr(self._steps[-1], "_completion_icon", None)
        if icon:
            icon.set_visible(True)

    def __scroll_to_bottom(self) -> bool:
        adjustment = self.steps_list.get_parent().get_vadjustment()
        adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())
        return GLib.SOURCE_REMOVE

    def __on_close_clicked(self, *_args):
        self.close()

    @GtkUtils.run_in_main_loop
    def add_step(self, text: str) -> None:
        if not text:
            return

        self.__mark_last_step_completed()

        row = self.__create_step_row(text)
        self.steps_list.append(row)
        self._steps.append(row)
        self.label_status.set_label(text)

        GLib.idle_add(self.__scroll_to_bottom)

    @GtkUtils.run_in_main_loop
    def update_progress(self, fraction: Optional[float]) -> None:
        if fraction is None:
            self.progress_download.set_fraction(0)
            self.progress_download.set_text("")
            self.progress_download.set_visible(False)
            return

        clamped_fraction = max(0.0, min(1.0, fraction))
        self.progress_download.set_fraction(clamped_fraction)
        self.progress_download.set_visible(True)

        percent = int(clamped_fraction * 100)
        self.progress_download.set_text(f"{percent}%")

    @GtkUtils.run_in_main_loop
    def finish(self, success: bool) -> None:
        self.spinner_progress.set_visible(False)
        self.spinner_progress.stop()
        self.progress_download.set_visible(False)
        self.btn_close.set_sensitive(True)

        if success:
            message = _("{0} installed.").format(self.dependency_name)
        else:
            message = _("{0} failed to install.").format(self.dependency_name)

        self.label_status.set_label(message)
        self.add_step(message)
        self.__mark_last_step_completed()
