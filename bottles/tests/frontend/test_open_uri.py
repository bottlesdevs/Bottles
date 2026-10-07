# ruff: noqa: E402

from types import SimpleNamespace

import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
gi.require_version("Xdp", "1.0")
gi.require_version("XdpGtk4", "1.0")

from gi.repository import Gio, GLib

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.frontend import params

params.APP_ID = "com.usebottles.bottles"

from bottles.backend.models.result import Result
from bottles.frontend.windows import window
from bottles.frontend.windows.window import BottlesWindow


class PortalStub:
    directory_calls = []
    uri_calls = []
    sandboxed = True

    @classmethod
    def running_under_sandbox(cls):
        return cls.sandboxed

    def open_uri(self, *args):
        self.uri_calls.append(args)

    def open_directory(self, *args):
        self.directory_calls.append(args)


def test_show_uri_opens_file_uri_through_portal_in_flatpak(monkeypatch):
    uri = "file:///tmp/Test"
    parent = object()
    gtk_calls = []
    PortalStub.directory_calls = []
    PortalStub.uri_calls = []
    PortalStub.sandboxed = True

    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(window.Xdp, "Portal", PortalStub)
    monkeypatch.setattr(window.XdpGtk4, "parent_new_gtk", lambda _window: parent)
    monkeypatch.setattr(window.Gtk, "show_uri", lambda *args: gtk_calls.append(args))

    BottlesWindow.g_show_uri_handler.__wrapped__(SimpleNamespace(), Result(data=uri))

    assert len(PortalStub.uri_calls) == 1
    assert PortalStub.uri_calls[0][0] is parent
    assert PortalStub.uri_calls[0][1] == uri
    assert PortalStub.uri_calls[0][3:] == (None, None)
    assert not PortalStub.directory_calls
    assert not gtk_calls


def test_show_uri_opens_web_uri_through_portal_in_flatpak(monkeypatch):
    uri = "https://usebottles.com"
    parent = object()
    gtk_calls = []
    PortalStub.directory_calls = []
    PortalStub.uri_calls = []

    monkeypatch.setenv("FLATPAK_ID", "com.usebottles.bottles")
    monkeypatch.setattr(window.Xdp, "Portal", PortalStub)
    monkeypatch.setattr(window.XdpGtk4, "parent_new_gtk", lambda _window: parent)
    monkeypatch.setattr(window.Gtk, "show_uri", lambda *args: gtk_calls.append(args))

    BottlesWindow.g_show_uri_handler.__wrapped__(SimpleNamespace(), Result(data=uri))

    assert len(PortalStub.uri_calls) == 1
    assert PortalStub.uri_calls[0][0] is parent
    assert PortalStub.uri_calls[0][1] == uri
    assert PortalStub.uri_calls[0][3:] == (None, None)
    assert not PortalStub.directory_calls
    assert not gtk_calls


def test_show_local_uri_uses_cpak_broker(monkeypatch, mocker):
    uri = "file:///home/test/.local/share/bottles/runners/soda"
    gtk_calls = []
    subprocess_new = mocker.patch.object(window.Gio.Subprocess, "new")

    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(window, "is_cpak", lambda: True)
    monkeypatch.setattr(window.Gtk, "show_uri", lambda *args: gtk_calls.append(args))

    BottlesWindow.g_show_uri_handler.__wrapped__(SimpleNamespace(), Result(data=uri))

    subprocess_new.assert_called_once_with(
        ["xdg-open", "/home/test/.local/share/bottles/runners/soda"],
        window.Gio.SubprocessFlags.NONE,
    )
    assert not gtk_calls


def test_show_uri_keeps_native_handler_in_other_sandboxes(monkeypatch):
    uri = "https://usebottles.com"
    gtk_calls = []
    PortalStub.directory_calls = []
    PortalStub.uri_calls = []
    PortalStub.sandboxed = True

    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(window, "is_cpak", lambda: False)
    monkeypatch.setattr(window.Xdp, "Portal", PortalStub)
    monkeypatch.setattr(window.Gtk, "show_uri", lambda *args: gtk_calls.append(args))

    BottlesWindow.g_show_uri_handler.__wrapped__(SimpleNamespace(), Result(data=uri))

    assert len(gtk_calls) == 1
    assert gtk_calls[0][1] == uri
    assert not PortalStub.directory_calls
    assert not PortalStub.uri_calls


def test_show_uri_keeps_native_handler_outside_sandbox(monkeypatch):
    uri = "https://usebottles.com"
    gtk_calls = []
    PortalStub.directory_calls = []
    PortalStub.uri_calls = []
    PortalStub.sandboxed = False

    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(window, "is_cpak", lambda: False)
    monkeypatch.setattr(window.Xdp, "Portal", PortalStub)
    monkeypatch.setattr(window.Gtk, "show_uri", lambda *args: gtk_calls.append(args))

    BottlesWindow.g_show_uri_handler.__wrapped__(SimpleNamespace(), Result(data=uri))

    assert len(gtk_calls) == 1
    assert gtk_calls[0][1] == uri
    assert not PortalStub.directory_calls
    assert not PortalStub.uri_calls


def test_show_local_uri_keeps_window_alive_when_launcher_is_missing(monkeypatch, mocker):
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(window, "is_cpak", lambda: True)
    mocker.patch.object(
        window.Gio.Subprocess, "new", side_effect=GLib.Error("xdg-open unavailable")
    )
    toast = mocker.Mock()
    BottlesWindow.g_show_uri_handler.__wrapped__(
        SimpleNamespace(show_toast=toast), Result(data="file:///home/test/logs/runs")
    )
    toast.assert_called_once()


def test_show_local_uri_reports_failed_launcher(monkeypatch, mocker):
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(window, "is_cpak", lambda: True)
    process = mocker.Mock()
    mocker.patch.object(window.Gio.Subprocess, "new", return_value=process)
    process.wait_check_finish.side_effect = GLib.Error("launcher exited with status 1")
    toast = mocker.Mock()
    BottlesWindow.g_show_uri_handler.__wrapped__(
        SimpleNamespace(show_toast=toast), Result(data="file:///home/test/logs/runs")
    )
    process.wait_check_async.assert_called_once()
    callback = process.wait_check_async.call_args.args[1]
    callback(process, object())
    toast.assert_called_once()


def test_show_local_uri_handles_real_launcher_failure(monkeypatch):
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(window, "is_cpak", lambda: True)
    launch = window.Gio.Subprocess.new
    monkeypatch.setattr(
        window.Gio.Subprocess, "new", lambda _argv, flags: launch(["/bin/false"], flags)
    )
    loop = GLib.MainLoop()
    messages = []

    def show_toast(message):
        messages.append(message)
        loop.quit()

    timer = GLib.timeout_add_seconds(5, lambda: loop.quit() or False)
    try:
        BottlesWindow.g_show_uri_handler.__wrapped__(
            SimpleNamespace(show_toast=show_toast), Result(data="file:///home/test/logs/runs")
        )
        loop.run()
    finally:
        GLib.source_remove(timer)
    assert len(messages) == 1
