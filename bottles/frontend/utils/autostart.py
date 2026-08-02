# ruff: noqa: E402
from gettext import gettext as _

import gi

gi.require_version("Xdp", "1.0")
gi.require_version("XdpGtk4", "1.0")
from gi.repository import GLib, Xdp, XdpGtk4

from bottles.backend.logger import Logger
from bottles.backend.utils.manager import ManagerUtils

logging = Logger()


def set_autostart_enabled(
    parent,
    enabled: bool,
    callback,
    portal=None,
    sandboxed=None,
):
    if sandboxed is None:
        sandboxed = Xdp.Portal.running_under_sandbox()

    if not sandboxed:
        callback(ManagerUtils.set_autostart_entry(enabled))
        return

    portal = portal or Xdp.Portal()
    flags = Xdp.BackgroundFlags.AUTOSTART if enabled else Xdp.BackgroundFlags(0)
    portal_parent = XdpGtk4.parent_new_gtk(parent) if parent else None

    def finish(_portal, result, _data=None):
        try:
            accepted = portal.request_background_finish(result)
            callback(bool(accepted) if enabled else True)
        except GLib.Error as error:
            logging.warning(f"Failed to update autostart permission: {error}")
            callback(False)

    portal.request_background(
        portal_parent,
        _("Launch selected Bottles programs when you log in."),
        ["bottles-cli", "autostart"],
        flags,
        None,
        finish,
        None,
    )
