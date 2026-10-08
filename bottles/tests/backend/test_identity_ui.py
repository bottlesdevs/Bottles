import os
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bottles.backend import identity_ui


def test_closed_sign_in_window_can_be_reopened():
    if not shutil.which("xvfb-run") or not shutil.which("dbus-run-session"):
        pytest.skip("Xvfb or D-Bus is unavailable")
    code = """
import time
from bottles.backend.identity_ui import IdentityBridgeApplication
from gi.repository import GLib

def dispatch():
    deadline = time.monotonic() + 0.2
    while time.monotonic() < deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)

app = IdentityBridgeApplication("unused.sock", "test")
assert app.register(None)
app._show_authentication()
app._show_result(False, "sign-in failed")
old_window = app.window
app._close_window()
dispatch()
assert app.window is None
assert not app.window_closing
app._show_authentication()
assert app.window is not old_window and app.window.get_visible()
app._window_destroyed(old_window)
assert app.window is not None
app._close_window()
dispatch()
assert app.window is None
"""
    environment = os.environ.copy()
    environment.update(GDK_BACKEND="x11", GSK_RENDERER="cairo", WAYLAND_DISPLAY="")
    result = subprocess.run(
        ["dbus-run-session", "--", "xvfb-run", "-a", sys.executable, "-c", code],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("fails", [False, True])
def test_server_exit_releases_application(monkeypatch, fails):
    stopped = Mock()
    application = SimpleNamespace(_server_stopped=stopped)
    server = Mock()
    idle_add = Mock()
    monkeypatch.setattr(identity_ui.GLib, "idle_add", idle_add)
    if fails:
        server.serve.side_effect = OSError("socket already in use")
        with pytest.raises(OSError):
            identity_ui.IdentityBridgeApplication._serve(application, server)
    else:
        identity_ui.IdentityBridgeApplication._serve(application, server)

    server.serve.assert_called_once_with()
    idle_add.assert_called_once_with(stopped)


def test_activation_callback_presents_the_window(monkeypatch):
    present_window = Mock()
    idle_add = Mock()
    application = SimpleNamespace(_present_window=present_window)
    monkeypatch.setattr(identity_ui.GLib, "idle_add", idle_add)

    identity_ui.IdentityBridgeApplication._activation_received(
        application,
        "activation-token",
    )

    idle_add.assert_called_once_with(present_window, "activation-token")


def test_present_window_uses_the_activation_token(monkeypatch):
    calls = []

    class Toplevel:
        def set_startup_id(self, startup_id):
            calls.append(("startup", startup_id))

        def focus(self, timestamp):
            calls.append(("focus", timestamp))

    surface = Toplevel()
    window = SimpleNamespace(
        get_surface=lambda: surface,
        present=lambda: calls.append(("present", None)),
    )
    application = SimpleNamespace(window=window, window_closing=False)
    monkeypatch.setattr(identity_ui.Gdk, "Toplevel", Toplevel)

    result = identity_ui.IdentityBridgeApplication._present_window(
        application,
        "activation-token",
    )

    assert result == identity_ui.GLib.SOURCE_REMOVE
    assert calls == [
        ("startup", "activation-token"),
        ("present", None),
        ("focus", identity_ui.Gdk.CURRENT_TIME),
    ]


def test_successful_authentication_presents_the_result(monkeypatch):
    present_window = Mock()
    close_window = Mock()
    timeout_add = Mock(return_value=17)
    status = Mock()
    button = Mock()
    application = SimpleNamespace(
        window=object(),
        window_closing=False,
        authentication_active=True,
        spinner=Mock(),
        open_button=Mock(),
        copy_button=Mock(),
        status=status,
        button=button,
        close_source=None,
        _present_window=present_window,
        _close_window=close_window,
    )
    monkeypatch.setattr(identity_ui.GLib, "timeout_add", timeout_add)

    result = identity_ui.IdentityBridgeApplication._show_result(
        application,
        True,
        "",
    )

    assert result == identity_ui.GLib.SOURCE_REMOVE
    present_window.assert_called_once_with()
    timeout_add.assert_called_once_with(900, close_window)
    assert application.close_source == 17
    status.set_label.assert_called_once_with("Microsoft 365 is connected.")
    button.set_label.assert_called_once_with("Done")
