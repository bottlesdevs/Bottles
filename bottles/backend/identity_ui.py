# identity_ui.py
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

import argparse
import threading
from gettext import gettext as _

import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from bottles.backend.identity import (
    IdentityBridgeServer,
    MicrosoftIdentityProvider,
    RedirectListener,
    SecretTokenStore,
)


class IdentityBridgeApplication(Adw.Application):
    def __init__(self, socket_path: str, context: str):
        super().__init__(
            application_id="com.usebottles.bottles.IdentityBridge",
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.socket_path = socket_path
        self.context = context
        self.cancel_event = threading.Event()
        self.window = None
        self.status = None
        self.spinner = None
        self.button = None
        self.open_button = None
        self.copy_button = None
        self.authorization_uri = None
        self.authentication_active = False
        self.window_closing = False
        self.close_source = None
        self.held = False

    def do_activate(self):
        if not self.held:
            self.hold()
            self.held = True
        provider = MicrosoftIdentityProvider(
            SecretTokenStore(self.context),
            open_uri=self._open_uri,
            listener_factory=self._listener,
            auth_complete=self._auth_complete,
        )
        server = IdentityBridgeServer(self.socket_path, self.context, provider)
        threading.Thread(target=self._serve, args=(server,), daemon=True).start()

    def _serve(self, server):
        try:
            server.serve()
        finally:
            GLib.idle_add(self._server_stopped)

    def _server_stopped(self):
        if self.held:
            self.release()
            self.held = False
        self.quit()
        return GLib.SOURCE_REMOVE

    def _listener(self, state, client_id):
        self.cancel_event.clear()
        return RedirectListener(
            state,
            client_id,
            self.cancel_event,
            self._activation_received,
        )

    def _activation_received(self, startup_id):
        GLib.idle_add(self._present_window, startup_id)

    def _open_uri(self, uri):
        GLib.idle_add(self._show_authentication, uri)

    def _show_authentication(self, uri=None):
        if self.close_source:
            GLib.source_remove(self.close_source)
            self.close_source = None
        self.authentication_active = True
        self.authorization_uri = uri
        if not self.window:
            self.window = Adw.Window(application=self)
            self.window_closing = False
            self.window.set_title(_("Microsoft 365 sign-in"))
            self.window.set_default_size(440, 260)
            self.window.set_resizable(False)
            self.window.set_icon_name("com.usebottles.bottles")
            self.window.connect("close-request", self._window_closed)
            self.window.connect("destroy", self._window_destroyed)

            toolbar = Adw.ToolbarView()
            toolbar.add_top_bar(Adw.HeaderBar())
            content = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=18,
                margin_top=32,
                margin_bottom=32,
                margin_start=32,
                margin_end=32,
                valign=Gtk.Align.CENTER,
            )
            self.spinner = Gtk.Spinner(spinning=True)
            self.spinner.set_size_request(48, 48)
            content.append(self.spinner)

            title = Gtk.Label(label=_("Continue in your browser"))
            title.add_css_class("title-2")
            content.append(title)

            self.status = Gtk.Label(
                label=_("Complete the Microsoft sign-in in the browser window.")
            )
            self.status.set_wrap(True)
            self.status.set_justify(Gtk.Justification.CENTER)
            self.status.add_css_class("dim-label")
            content.append(self.status)

            actions = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=8,
                halign=Gtk.Align.CENTER,
            )
            self.copy_button = Gtk.Button(label=_("Copy Link"))
            self.copy_button.connect("clicked", self._copy_link)
            actions.append(self.copy_button)

            self.open_button = Gtk.Button(label=_("Open Browser"))
            self.open_button.add_css_class("suggested-action")
            self.open_button.connect("clicked", self._open_browser)
            actions.append(self.open_button)

            self.button = Gtk.Button(label=_("Cancel"))
            self.button.connect("clicked", self._button_clicked)
            actions.append(self.button)
            content.append(actions)
            toolbar.set_content(content)
            self.window.set_content(toolbar)
        self.spinner.set_visible(True)
        self.spinner.start()
        self.status.set_label(
            _("Complete the Microsoft sign-in in the browser window.")
        )
        self.copy_button.set_visible(True)
        self.open_button.set_visible(True)
        self.open_button.set_sensitive(True)
        self.button.set_label(_("Cancel"))
        self._present_window()
        if uri:
            Gio.AppInfo.launch_default_for_uri_async(
                uri, None, None, self._browser_opened, None
            )
        return GLib.SOURCE_REMOVE

    def _present_window(self, startup_id=None):
        if not self.window or self.window_closing:
            return GLib.SOURCE_REMOVE
        surface = self.window.get_surface()
        if startup_id and isinstance(surface, Gdk.Toplevel):
            surface.set_startup_id(startup_id)
        self.window.present()
        surface = self.window.get_surface()
        if isinstance(surface, Gdk.Toplevel):
            surface.focus(Gdk.CURRENT_TIME)
        return GLib.SOURCE_REMOVE

    def _open_browser(self, _button):
        if not self.authorization_uri:
            return
        self.open_button.set_sensitive(False)
        Gio.AppInfo.launch_default_for_uri_async(
            self.authorization_uri, None, None, self._browser_opened, None
        )

    def _browser_opened(self, _source, result, _data):
        try:
            opened = Gio.AppInfo.launch_default_for_uri_finish(result)
        except GLib.Error:
            opened = False
        if self.open_button:
            self.open_button.set_sensitive(True)
        if not opened and self.status:
            self.status.set_label(
                _("The browser did not open. Try again or copy the sign-in link.")
            )

    def _copy_link(self, _button):
        display = Gdk.Display.get_default()
        if not display or not self.authorization_uri:
            return
        display.get_clipboard().set_content(
            Gdk.ContentProvider.new_for_value(self.authorization_uri)
        )
        self.status.set_label(_("Sign-in link copied. Open it in any browser."))

    def _auth_complete(self, success, message):
        GLib.idle_add(self._show_result, success, message)

    def _show_result(self, success, message):
        if not self.window and success is False:
            self._show_authentication()
        if not self.window or self.window_closing:
            return GLib.SOURCE_REMOVE
        self.authentication_active = False
        if success is None:
            self._close_window()
            return GLib.SOURCE_REMOVE
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.open_button.set_visible(False)
        self.copy_button.set_visible(False)
        if success:
            self.status.set_label(_("Microsoft 365 is connected."))
            self.button.set_label(_("Done"))
            self._present_window()
            self.close_source = GLib.timeout_add(900, self._close_window)
        else:
            self.status.set_label(message or _("Microsoft 365 sign-in failed."))
            self.button.set_label(_("Close"))
            self._present_window()
        return GLib.SOURCE_REMOVE

    def _close_window(self):
        self.close_source = None
        if self.window:
            self.window.close()
        return GLib.SOURCE_REMOVE

    def _button_clicked(self, _button):
        if self.authentication_active:
            self.cancel_event.set()
        if self.window:
            self.window.close()

    def _window_closed(self, _window):
        if self.close_source:
            GLib.source_remove(self.close_source)
            self.close_source = None
        self.window_closing = True
        if self.authentication_active:
            self.cancel_event.set()
        return False

    def _window_destroyed(self, _window):
        if self.window is not _window:
            return
        self.window = None
        self.window_closing = False
        self.status = None
        self.spinner = None
        self.button = None
        self.open_button = None
        self.copy_button = None
        self.authorization_uri = None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--socket")
    parser.add_argument("--context")
    args = parser.parse_args()
    if not args.serve or not args.socket or not args.context:
        parser.error("--serve, --socket and --context are required")
    return IdentityBridgeApplication(args.socket, args.context).run([])


if __name__ == "__main__":
    raise SystemExit(main())
