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


@pytest.fixture
def entry():
    run, stop = Gtk.Button(), Gtk.Button()
    run.set_visible(False)
    stop.set_visible(True)
    entry = SimpleNamespace(
        config=SimpleNamespace(Parameters=SimpleNamespace(sandbox=False)),
        program={"name": "Fixture"},
        executable="fixture.exe",
        window=SimpleNamespace(show_toast=Mock()),
        btn_run=run,
        btn_stop=stop,
        pop_actions=Mock(),
    )
    entry._ProgramEntry__reset_buttons = lambda result=False, error=False: (
        program.ProgramEntry._ProgramEntry__reset_buttons(entry, result, error)
    )
    entry._ProgramEntry__crash_threshold_seconds = 5
    return entry


def wait_for(predicate):
    deadline = time.monotonic() + 5
    context = GLib.MainContext.default()
    while not predicate() and time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)
    return predicate()


@pytest.mark.parametrize("sandbox", [False, True])
def test_stop_restores_buttons_after_worker(monkeypatch, sandbox, entry):
    calls = []
    entry.config.Parameters.sandbox = sandbox

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
    program.ProgramEntry.stop_process(entry, entry.btn_stop)
    assert wait_for(entry.btn_run.get_visible)
    assert calls == (["sandbox"] if sandbox else [(None, "fixture.exe")])
    assert entry.btn_run.get_visible() and entry.btn_run.get_sensitive()
    assert not entry.btn_stop.get_visible() and not entry.btn_stop.get_sensitive()


@pytest.mark.parametrize("sandbox", [False, True])
def test_failed_stop_can_be_retried(monkeypatch, sandbox, entry):
    entry.config.Parameters.sandbox = sandbox
    fail = Mock(side_effect=RuntimeError("Fixture stop failure"))
    monkeypatch.setattr(
        program, "WineDbg", lambda config: SimpleNamespace(kill_process=fail)
    )
    monkeypatch.setattr(
        program, "WineServer", lambda config: SimpleNamespace(force_kill=fail)
    )

    program.ProgramEntry.stop_process(entry, entry.btn_stop)

    assert wait_for(entry.btn_stop.get_sensitive)
    fail.assert_called_once()
    assert entry.btn_stop.get_visible()
    assert not entry.btn_run.get_visible()


def test_failed_launch_restores_run_without_crash_scan(monkeypatch, tmp_path, entry):
    executable = tmp_path / "fixture.exe"
    executable.write_bytes(b"Owned launch fixture")
    entry.program["path"] = str(executable)
    entry.window.settings = SimpleNamespace(get_boolean=lambda _name: True)
    entry._ProgramEntry__offer_eagle_scan = Mock()
    monkeypatch.setattr(
        program,
        "guard_sandbox_launch",
        lambda _window, _config, _path, proceed: proceed(None, None),
    )
    monkeypatch.setattr(
        program.WineExecutor,
        "run_program",
        Mock(side_effect=RuntimeError("Fixture launch failure")),
    )

    program.ProgramEntry._ProgramEntry__launch_program(entry)

    assert wait_for(entry.btn_run.get_visible)
    assert entry.btn_run.get_sensitive()
    assert not entry.btn_stop.get_visible()
    entry._ProgramEntry__offer_eagle_scan.assert_not_called()
