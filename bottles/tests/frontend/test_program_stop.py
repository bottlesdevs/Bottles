# ruff: noqa: E402

import time
from types import SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
from gi.repository import Gio, GLib, Gtk

Gio.resources_register(Gio.Resource.load("/app/share/bottles/bottles.gresource"))

from bottles.frontend.widgets import program


@pytest.mark.parametrize("sandbox", [False, True])
def test_stop_restores_buttons_after_worker(monkeypatch, sandbox):
    calls = []

    def kill_process(pid=None, name=None):
        calls.append((pid, name))

    monkeypatch.setattr(
        program, "WineDbg", lambda config: SimpleNamespace(kill_process=kill_process)
    )
    monkeypatch.setattr(
        program,
        "WineServer",
        lambda config: SimpleNamespace(force_kill=lambda: calls.append("sandbox")),
    )
    run, stop = Gtk.Button(), Gtk.Button()
    run.set_visible(False)
    stop.set_visible(True)
    entry = SimpleNamespace(
        config=SimpleNamespace(Parameters=SimpleNamespace(sandbox=sandbox)),
        program={"name": "Fixture"},
        executable="fixture.exe",
        window=SimpleNamespace(show_toast=Mock()),
        btn_run=run,
        btn_stop=stop,
    )
    entry._ProgramEntry__reset_buttons = (
        lambda result, error: program.ProgramEntry._ProgramEntry__reset_buttons(
            entry, result, error
        )
    )
    program.ProgramEntry.stop_process(entry, stop)
    deadline = time.monotonic() + 5
    context = GLib.MainContext.default()
    while not run.get_visible() and time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)
    assert calls == (["sandbox"] if sandbox else [(None, "fixture.exe")])
    assert run.get_visible() and run.get_sensitive()
    assert not stop.get_visible() and not stop.get_sensitive()
