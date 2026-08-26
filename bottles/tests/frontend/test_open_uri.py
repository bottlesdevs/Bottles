# ruff: noqa: E402

from types import SimpleNamespace

import gi

gi.require_version("Adw", "1")
gi.require_version("Xdp", "1.0")
gi.require_version("XdpGtk4", "1.0")

from gi.repository import Gio

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


def test_show_uri_opens_directory_through_portal_in_flatpak(monkeypatch):
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

    assert len(PortalStub.directory_calls) == 1
    assert PortalStub.directory_calls[0][0] is parent
    assert PortalStub.directory_calls[0][1] == uri
    assert PortalStub.directory_calls[0][3:] == (None, None)
    assert not PortalStub.uri_calls
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


def test_show_uri_keeps_native_handler_in_other_sandboxes(monkeypatch):
    uri = "https://usebottles.com"
    gtk_calls = []
    PortalStub.directory_calls = []
    PortalStub.uri_calls = []
    PortalStub.sandboxed = True

    monkeypatch.delenv("FLATPAK_ID", raising=False)
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
    monkeypatch.setattr(window.Xdp, "Portal", PortalStub)
    monkeypatch.setattr(window.Gtk, "show_uri", lambda *args: gtk_calls.append(args))

    BottlesWindow.g_show_uri_handler.__wrapped__(SimpleNamespace(), Result(data=uri))

    assert len(gtk_calls) == 1
    assert gtk_calls[0][1] == uri
    assert not PortalStub.directory_calls
    assert not PortalStub.uri_calls
