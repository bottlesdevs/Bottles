# flatpak.py
#
# Copyright 2026 The Bottles Contributors
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
import shlex
import webbrowser
from gettext import gettext as _
from typing import Optional

from gi.repository import Adw, Gdk, Gtk

from bottles.backend.utils.manager import ManagerUtils


EXPOSE_DIRECTORIES_URL = "https://docs.usebottles.com/flatpak/expose-directories"
FILESYSTEM_PERMISSION_SUFFIXES = (":ro", ":rw", ":create")


def get_filesystem_override_command(path: str) -> Optional[str]:
    app_id = os.environ.get("FLATPAK_ID")
    if not app_id:
        return None

    host_path = ManagerUtils.get_portal_host_path(path)
    if not host_path or host_path.rstrip("/").endswith(FILESYSTEM_PERMISSION_SUFFIXES):
        return None

    return shlex.join(
        [
            "flatpak",
            "override",
            "--user",
            f"--filesystem={host_path}",
            app_id,
        ]
    )


def _copy_command(parent, command: str) -> None:
    display = Gdk.Display.get_default()
    if not display:
        return

    clipboard = display.get_clipboard()
    clipboard.set_content(Gdk.ContentProvider.new_for_value(command))
    if hasattr(parent, "show_toast"):
        parent.show_toast(_("Copied to clipboard"))


def show_external_folder_access_dialog(parent, path: str) -> None:
    dialog = Adw.MessageDialog.new(
        parent,
        _("Folder Access Required"),
        _(
            "Bottles needs direct Flatpak access to this folder for reliable "
            "bottle storage. Grant access, restart Bottles, then select the "
            "folder again."
        ),
    )

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    command = get_filesystem_override_command(path)
    if command:
        command_label = Gtk.Label(label=_("Run this command on the host:"))
        command_label.set_halign(Gtk.Align.START)
        command_label.set_xalign(0)
        box.append(command_label)

        command_box = Gtk.Box(spacing=6)
        command_entry = Gtk.Entry()
        command_entry.set_editable(False)
        command_entry.set_focusable(False)
        command_entry.set_hexpand(True)
        command_entry.set_text(command)
        command_entry.set_tooltip_text(command)
        command_entry.set_width_chars(38)
        command_entry.add_css_class("monospace")

        copy_button = Gtk.Button(icon_name="edit-copy-symbolic")
        copy_button.set_tooltip_text(_("Copy command"))
        copy_button.connect("clicked", lambda _button: _copy_command(parent, command))

        command_box.append(command_entry)
        command_box.append(copy_button)
        box.append(command_box)

    documentation_content = Adw.ButtonContent(
        icon_name="external-link-symbolic",
        label=_("Open Documentation"),
    )
    documentation_button = Gtk.Button(child=documentation_content)
    documentation_button.set_halign(Gtk.Align.START)
    documentation_button.add_css_class("flat")
    documentation_button.connect(
        "clicked", lambda _button: webbrowser.open_new_tab(EXPOSE_DIRECTORIES_URL)
    )
    box.append(documentation_button)

    dialog.set_extra_child(box)
    dialog.add_response("dismiss", _("_Dismiss"))
    dialog.set_close_response("dismiss")
    dialog.present()


def resolve_bottles_directory(parent, path: str) -> Optional[str]:
    resolved_path = ManagerUtils.resolve_portal_path(path)
    if resolved_path and "/run/user/" in resolved_path and "/doc/" in resolved_path:
        show_external_folder_access_dialog(parent, resolved_path)
        return None
    return resolved_path
