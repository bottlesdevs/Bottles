# umu.py
#
# Copyright 2026 mirkobrombin <brombin94@gmail.com>
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

from gi.repository import Adw, Gtk

from bottles.backend.utils.manager import ManagerUtils


@Gtk.Template(resource_path="/com/usebottles/bottles/umu-prefix-row.ui")
class UmuPrefixRow(Adw.ActionRow):
    __gtype_name__ = "UmuPrefixRow"

    label_state = Gtk.Template.Child()
    btn_browse = Gtk.Template.Child()

    def __init__(self, entry, settings_callback, **kwargs):
        super().__init__(**kwargs)
        if entry.get("source") != "umu":
            raise ValueError("UMU rows require an UMU source entry")

        self.entry = entry
        self.source = "umu"
        self.settings_callback = settings_callback
        self.connect("activated", self.__show_settings)
        self.set_title(entry.get("name") or entry.get("source_id"))
        self.set_subtitle(entry.get("path", ""))

        state = entry.get("state", "ready")
        state_labels = {
            "draft": _("Choose Executable"),
            "installing": _("Installing"),
            "failed": _("Installation Failed"),
            "stopped": _("Installation Stopped"),
            "detected": _("Setup Required"),
        }
        state_descriptions = {
            "draft": _("The installer finished. Select the game executable."),
            "installing": _("The installer is still running."),
            "failed": _("The installer exited before setup completed."),
            "stopped": _("The installer was stopped before setup completed."),
            "detected": _("Select the game identity and executable to complete setup."),
        }
        if state in state_labels:
            self.label_state.set_label(state_labels[state])
            self.label_state.set_tooltip_text(state_descriptions[state])
            self.label_state.set_visible(True)
            self.set_subtitle(state_descriptions[state])

        path = entry.get("path", "")
        self.btn_browse.set_sensitive(bool(path))
        self.btn_browse.connect("clicked", self.__open_prefix)

    def __open_prefix(self, *_args):
        ManagerUtils.open_filemanager(
            path_type="custom", custom_path=self.entry.get("path", "")
        )

    def __show_settings(self, *_args):
        self.settings_callback(
            self.entry if self.entry.get("detected") else self.entry["source_id"]
        )
