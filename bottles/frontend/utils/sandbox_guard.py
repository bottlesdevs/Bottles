# sandbox_guard.py
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

import os
import shutil
from gettext import gettext as _

from gi.repository import Adw, GLib, Gtk

from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.utils.threading import RunAsync
from bottles.backend.wine.executor import WineExecutor

# files copied into the bottle so the dedicated sandbox can reach them live in
# this hidden folder under the bottle path (always shared read/write with the
# sandbox)
STAGING_DIR_NAME = ".bottles_staged"

_CHUNK = 4 * 1024 * 1024


def _add_option(box, title, subtitle, group=None):
    option = Gtk.CheckButton.new_with_label(title)
    if group is not None:
        option.set_group(group)
    caption = Gtk.Label(label=subtitle)
    caption.add_css_class("dim-label")
    caption.add_css_class("caption")
    caption.set_halign(Gtk.Align.START)
    caption.set_wrap(True)
    caption.set_xalign(0)
    caption.set_margin_start(28)
    box.append(option)
    box.append(caption)
    return option


def _copy_into_bottle(parent, config, exec_path, on_launch):
    """Copy the program into a temporary folder inside the bottle, showing a
    real progress bar with a cancel button, then launch the copy in the
    dedicated sandbox. Only the chosen file is copied: anything stored next to
    it is not, so a launch may still be incomplete."""
    name = os.path.basename(exec_path)
    staging_dir = os.path.join(ManagerUtils.get_bottle_path(config), STAGING_DIR_NAME)
    dst = os.path.join(staging_dir, name)

    dialog = Adw.MessageDialog.new(
        parent,
        _("Copying into the bottle"),
        _(
            "Moving “{0}” into a temporary folder inside the bottle so "
            "the dedicated sandbox can reach it. Files stored next to it are not "
            "included, so the program may not work fully."
        ).format(name),
    )

    progress = Gtk.ProgressBar()
    progress.set_hexpand(True)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.append(progress)
    dialog.set_extra_child(box)

    dialog.add_response("cancel", _("Cancel"))
    dialog.set_close_response("cancel")

    state = {"cancel": False, "done": False}

    def on_response(_dialog, _response):
        if not state["done"]:
            state["cancel"] = True

    dialog.connect("response", on_response)

    def set_fraction(fraction):
        progress.set_fraction(fraction)
        return False

    def worker():
        total = os.path.getsize(exec_path)
        copied = 0
        os.makedirs(staging_dir, exist_ok=True)
        with open(exec_path, "rb") as src, open(dst, "wb") as out:
            while True:
                if state["cancel"]:
                    return None
                chunk = src.read(_CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                copied += len(chunk)
                GLib.idle_add(set_fraction, copied / total if total else 1.0)
        shutil.copymode(exec_path, dst)
        return dst

    def done(result=False, error=False):
        state["done"] = True
        dialog.close()
        if error or not result:
            try:
                os.remove(dst)
            except OSError:
                pass
            if error and not state["cancel"] and hasattr(parent, "show_toast"):
                parent.show_toast(_("Could not copy the file into the bottle."))
            return
        on_launch(None, result)

    dialog.present()
    RunAsync(worker, callback=done)


def guard_sandbox_launch(parent, config, exec_path, on_launch):
    """Ask the user how to launch a program the dedicated sandbox cannot reach.

    When the dedicated sandbox is enabled and ``exec_path`` lives outside the
    bottle (a document portal path), the program cannot be opened inside the
    sandbox. A dialog is then presented and ``on_launch(sandbox_override,
    exec_path)`` is called with the executable to actually run: either the
    original path with the sandbox disabled, or a copy staged inside the bottle
    with the sandbox kept on. In every other case ``on_launch(None, exec_path)``
    is called right away. ``on_launch`` is not called if the user cancels.
    """
    if not config.Parameters.sandbox or not WineExecutor.is_unreachable_in_sandbox(
        exec_path
    ):
        on_launch(None, exec_path)
        return

    name = os.path.basename(exec_path) if exec_path else _("This program")

    dialog = Adw.MessageDialog.new(
        parent,
        _("Can't reach this program in the sandbox"),
        _(
            "“{0}” is stored outside the bottle, where the dedicated "
            "sandbox can't reach it. Choose how to launch it this time:"
        ).format(name),
    )

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    opt_off = _add_option(
        box,
        _("Run without the dedicated sandbox"),
        _("Runs with the same access as Bottles, without the extra isolation."),
    )
    opt_copy = _add_option(
        box,
        _("Copy into the bottle and keep the sandbox"),
        _(
            "Copies the file into a temporary folder inside the bottle. Files "
            "stored next to it are not included, so it may not work fully."
        ),
        group=opt_off,
    )
    opt_off.set_active(True)
    dialog.set_extra_child(box)

    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("run", _("Run"))
    dialog.set_response_appearance("run", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("run")
    dialog.set_close_response("cancel")

    def on_response(_dialog, response):
        if response != "run":
            return
        if opt_copy.get_active():
            _copy_into_bottle(parent, config, exec_path, on_launch)
        else:
            on_launch("off", exec_path)

    dialog.connect("response", on_response)
    dialog.present()
