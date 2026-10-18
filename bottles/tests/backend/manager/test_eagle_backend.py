import os
import json
import shlex
import signal
import time
from pathlib import Path

import pytest

from bottles.backend.managers import eaglebackend
from bottles.backend.state import Signals


def test_packaged_backend_emits_existing_signals(monkeypatch):
    messages = []
    monkeypatch.setattr(eaglebackend.SignalManager, 'send', lambda signal, value: messages.append((signal, value)))
    config = {'RunnerPath': os.environ['EAGLE_PACKAGE']}
    target = str(Path(os.environ['EAGLE_TEST_ROOT']) / 'target64.exe')

    assert eaglebackend.analyze(config, target, 1)
    assert any(signal == Signals.EagleStep for signal, _ in messages)
    assert messages[-1][0] == Signals.EagleFinished
    assert messages[-1][1].status
    assert messages[-1][1].data['arch'] == 'x86_64 (64-bit)'


def test_missing_backend_selects_legacy_path(tmp_path):
    assert not eaglebackend.analyze({'RunnerPath': str(tmp_path)}, 'unused.exe', 1)

def test_tracing_support_and_command_quoting(monkeypatch, tmp_path):
    runner = tmp_path / 'runner with spaces'
    executable = runner / 'bin/eagle'
    executable.parent.mkdir(parents=True)
    executable.write_text('#!/bin/sh\nexit 0\n')
    executable.chmod(0o755)
    config = {'RunnerPath': str(runner)}
    assert not eaglebackend.tracing_supported(config)
    manifest = runner / 'share/eagle/providers.json'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({'tracing': 1, 'profiles': {name: ['32', '64'] for name in ('winrt', 'dwrite', 'com', 'wait')}}))
    assert eaglebackend.tracing_supported(config)
    prefix = str(tmp_path / "bottle 'with spaces")
    monkeypatch.setattr(eaglebackend.ManagerUtils, 'get_bottle_path', lambda config: prefix)
    command = eaglebackend.trace_command(config, shlex.quote(str(runner / 'bin/wine')), prefix)
    assert shlex.split(command) == [str(executable), 'trace', '--wine', str(runner / 'bin/wine'), '--prefix', prefix, '--logs', os.path.join(prefix, 'logs/runs'), '--cwd', prefix, '--']
    stale = dict(config, RunnerPath=str(tmp_path / 'previous runner'))
    assert eaglebackend.trace_command(stale, shlex.quote(str(runner / 'bin/wine')), prefix) == command
    with pytest.raises(RuntimeError, match='does not include Eagle tracing'):
        eaglebackend.trace_command(config, shlex.quote(str(tmp_path / 'unsupported/bin/wine')), prefix)
    manifest.write_text(json.dumps({'tracing': 1, 'profiles': {'wait': ['64']}}))
    assert not eaglebackend.tracing_supported(config)
    with pytest.raises(RuntimeError, match='does not include Eagle tracing'):
        eaglebackend.trace_command(config, 'wine', prefix)


def test_invalid_backend_response_is_rejected(monkeypatch, tmp_path):
    executable = tmp_path / 'bin/eagle'
    executable.parent.mkdir()
    executable.write_text('#!/usr/bin/env python3\nprint("[]")\n')
    executable.chmod(0o755)
    messages = []
    monkeypatch.setattr(eaglebackend.SignalManager, 'send', lambda *args: messages.append(args))
    with pytest.raises(ValueError, match='Invalid Eagle backend response'):
        eaglebackend.analyze({'RunnerPath': str(tmp_path)}, 'unused.exe', 1)
    assert not messages

def test_analysis_watchdog_reaps_backend_that_ignores_termination(monkeypatch, tmp_path):
    executable = tmp_path / 'bin/eagle'
    executable.parent.mkdir()
    executable.write_text('#!/usr/bin/env python3\nimport json, signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nprint(json.dumps({"event": "step", "data": "ready"}), flush=True)\nwhile True: time.sleep(1)\n')
    executable.chmod(0o755)
    messages = []
    processes = []
    popen = eaglebackend.subprocess.Popen
    def start(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(eaglebackend.subprocess, 'Popen', start)
    monkeypatch.setattr(eaglebackend, 'ANALYSIS_TIMEOUT', 0.3)
    monkeypatch.setattr(eaglebackend, 'TERMINATE_TIMEOUT', 0.3)
    monkeypatch.setattr(eaglebackend.SignalManager, 'send', lambda signal, value: messages.append((signal, value.data)))
    started = time.monotonic()
    with pytest.raises(RuntimeError, match='analysis failed'):
        eaglebackend.analyze({'RunnerPath': str(tmp_path)}, 'unused.exe', 1)
    assert (Signals.EagleStep, 'ready') in messages
    assert len(processes) == 1
    assert processes[0].poll() == -signal.SIGKILL
    assert time.monotonic() - started < 3
