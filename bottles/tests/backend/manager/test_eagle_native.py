import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from bottles.backend.managers import eaglenative
from bottles.backend.managers import eagle as eagle_module
from bottles.backend.managers.eagle import EagleManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils


@pytest.fixture
def native_runner(tmp_path):
    runner = tmp_path / "runner with spaces"
    (runner / "bin").mkdir(parents=True)
    executable = runner / "bin/eagle"
    executable.write_text("#!" + sys.executable + "\nimport json,sys\n"
        "if sys.argv[1] == 'capabilities':\n"
        "    print(json.dumps({'data':{'schema':1,'native_static_analyzer':True,'analysis':{'available':True}}}))\n"
        "else:\n"
        "    print(json.dumps({'event':'step','data':'fixture step'}),flush=True)\n"
        "    print(json.dumps({'status':True,'data':{'arguments':sys.argv[2:]}}))\n")
    executable.chmod(0o755)
    return runner, executable


def test_capability_selection_and_quoted_paths(native_runner, tmp_path):
    runner, executable = native_runner
    assert eaglenative.command(str(runner)) == str(executable)
    steps = []
    target = str(tmp_path / "user's app.exe")
    result = eaglenative.analyze(str(executable), target, 7, steps.append, str(tmp_path / "work"))
    assert result["arguments"] == [target, "--scan-limit", "7", "--progress"]
    assert steps == ["fixture step"]


@pytest.mark.parametrize("response", [
    {}, {"data": None}, {"data": []}, {"data": {"schema": 2}},
    {"data": {"schema": 1, "native_static_analyzer": False, "analysis": {"available": True}}},
    {"data": {"schema": 1, "native_static_analyzer": True, "analysis": {"available": False}}},
])
def test_unsupported_runner_uses_existing_engine(native_runner, response):
    runner, executable = native_runner
    executable.write_text("#!" + sys.executable + "\nprint(" + repr(json.dumps(response)) + ")\n")
    assert eaglenative.command(str(runner)) is None


def test_missing_or_nonexecutable_runner_uses_existing_engine(native_runner):
    runner, executable = native_runner
    executable.chmod(0o644)
    assert eaglenative.command(str(runner)) is None
    executable.unlink()
    assert eaglenative.command(str(runner)) is None
    assert eaglenative.command("") is None


@pytest.mark.parametrize("output", [
    "[]\n", "invalid\n", '{"status":true}',
    '{"status":true,"data":[]}\n',
    '{"status":true,"data":{}}\n{"status":true,"data":{}}\n',
    '{"status":false,"error":"fixture failure"}\n',
])
def test_invalid_and_failed_reports_are_errors(native_runner, tmp_path, output):
    _, executable = native_runner
    executable.write_text("#!" + sys.executable + "\nimport sys\nsys.stdout.write(" + repr(output) + ")\n")
    with pytest.raises(ValueError):
        eaglenative.analyze(str(executable), "fixture.exe", 1, lambda text: None, str(tmp_path / "work"))


@pytest.mark.parametrize("messages", [
    [{"status": True, "data": {}}, {"event": "step", "data": "late step"}],
    [{"status": True, "data": {}, "event": "unknown"}],
])
def test_terminal_report_rejects_late_or_unknown_events(native_runner, tmp_path, messages):
    _, executable = native_runner
    output = "".join(json.dumps(message) + "\n" for message in messages)
    executable.write_text("#!" + sys.executable + "\nimport sys\nsys.stdout.write(" + repr(output) + ")\n")
    steps = []
    with pytest.raises(ValueError, match="unexpected analysis response"):
        eaglenative.analyze(str(executable), "fixture.exe", 1, steps.append, str(tmp_path / "work"))
    assert steps == []


def test_stderr_is_drained_and_failure_is_reported(native_runner, tmp_path):
    _, executable = native_runner
    executable.write_text("#!" + sys.executable + "\nimport sys\n"
                          "sys.stderr.write('x'*200000+'fixture failure')\nsys.exit(1)\n")
    with pytest.raises(RuntimeError, match="fixture failure"):
        eaglenative.analyze(str(executable), "fixture.exe", 1, lambda text: None, str(tmp_path / "work"))


def test_cli_error_envelope_is_shown_as_plain_message(native_runner, tmp_path):
    _, executable = native_runner
    executable.write_text("#!" + sys.executable + "\nimport sys\n"
                          "sys.stderr.write('{\"status\":false,\"error\":\"fixture failure\"}')\nsys.exit(1)\n")
    with pytest.raises(RuntimeError) as error:
        eaglenative.analyze(str(executable), "fixture.exe", 1, lambda text: None, str(tmp_path / "work"))
    assert str(error.value) == "fixture failure"


def test_cancel_stops_own_process(native_runner, tmp_path):
    _, executable = native_runner
    receipt = tmp_path / "pid"
    executable.write_text("#!" + sys.executable + "\nimport os,time\nfrom pathlib import Path\n"
                          "Path(" + repr(str(receipt)) + ").write_text(str(os.getpid()))\ntime.sleep(60)\n")
    cancelled = threading.Event()
    def cancel():
        until = time.monotonic() + 5
        while not receipt.exists() and time.monotonic() < until:
            time.sleep(0.01)
        cancelled.set()
    thread = threading.Thread(target=cancel)
    thread.start()
    try:
        with pytest.raises(RuntimeError, match="analysis cancelled"):
            eaglenative.analyze(str(executable), "fixture.exe", 1, lambda text: None, str(tmp_path / "work"), cancelled)
        pid = int(receipt.read_text())
        assert not Path("/proc", str(pid)).exists()
    finally:
        thread.join(timeout=6)
    assert not thread.is_alive()


def test_cancel_before_start_does_not_launch(native_runner, tmp_path):
    _, executable = native_runner
    receipt = tmp_path / "started"
    executable.write_text("#!" + sys.executable + "\nfrom pathlib import Path\n"
                          "Path(" + repr(str(receipt)) + ").touch()\n")
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(RuntimeError, match="analysis cancelled"):
        eaglenative.analyze(str(executable), "fixture.exe", 1, lambda text: None, str(tmp_path / "work"), cancelled)
    assert not receipt.exists()


@pytest.mark.parametrize("config,expected", [
    (BottleConfig(Runner="soda-test"), "/managed/soda-test"),
    (BottleConfig(Environment="Steam", Runner="proton", RunnerPath="/external/runner"), "/external/runner"),
    (BottleConfig(Runner="sys-wine"), ""),
])
def test_manager_selects_configured_runner_and_preserves_fallback(monkeypatch, config, expected):
    manager = EagleManager.__new__(EagleManager)
    manager.config = config
    monkeypatch.setattr(ManagerUtils, "get_runner_path", lambda name: "/managed/" + name)
    selected = []
    monkeypatch.setattr(eaglenative, "command", lambda runner: selected.append(runner))
    class LegacySelected(Exception):
        pass
    def legacy_step(message, delay=True):
        raise LegacySelected()
    manager._send_step = legacy_step
    with pytest.raises(LegacySelected):
        manager.analyze("fixture.exe")
    assert selected == [expected]


@pytest.mark.parametrize("fails", [False, True])
def test_manager_sends_native_report_or_failure_once(monkeypatch, fails):
    manager = EagleManager.__new__(EagleManager)
    manager.config = BottleConfig(Runner="soda-test")
    monkeypatch.setattr(ManagerUtils, "get_runner_path", lambda name: "/runner")
    monkeypatch.setattr(eaglenative, "command", lambda runner: "/runner/bin/eagle")
    monkeypatch.setattr(eagle_module.Gio.Settings, "new", lambda app: SimpleNamespace(get_int=lambda key: 7))
    steps = []
    manager._send_step = lambda message, delay=True: steps.append((message, delay))
    events = []
    monkeypatch.setattr(eagle_module.SignalManager, "send", lambda kind, result: events.append((kind, result)))
    def analyze(executable, target, limit, progress, work):
        assert (executable, target, limit, work) == ("/runner/bin/eagle", "fixture.exe", 7, eagle_module.Paths.temp)
        progress("native step")
        if fails:
            raise RuntimeError("native failure")
        return {"name": "fixture.exe"}
    monkeypatch.setattr(eaglenative, "analyze", analyze)
    manager.analyze("fixture.exe")
    assert steps == [("native step", False)]
    assert len(events) == 1
    assert events[0][0] == eagle_module.Signals.EagleFinished
    assert events[0][1].status is not fails
    assert events[0][1].eagle_source is manager
    assert events[0][1].data == ({"error": "native failure"} if fails else {"name": "fixture.exe"})


def test_step_signal_identifies_its_manager(monkeypatch):
    manager = EagleManager.__new__(EagleManager)
    events = []
    monkeypatch.setattr(eagle_module.SignalManager, "send", lambda kind, result: events.append((kind, result)))
    manager._send_step("fixture step", delay=False)
    assert len(events) == 1
    assert events[0][0] == eagle_module.Signals.EagleStep
    assert events[0][1].data == "fixture step"
    assert events[0][1].eagle_source is manager
