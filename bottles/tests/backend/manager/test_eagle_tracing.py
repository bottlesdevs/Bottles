import json
import shlex

import pytest

from bottles.backend.managers import eagletracing
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.executor import WineExecutor
from bottles.backend.wine.winecommand import WineCommand


@pytest.fixture
def tracing_runner(monkeypatch, tmp_path):
    runner = tmp_path / "runner with spaces"
    (runner / "bin").mkdir(parents=True)
    executable = runner / "bin/eagle"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o755)
    (runner / "share/eagle").mkdir(parents=True)
    manifest = runner / "share/eagle/providers.json"
    manifest.write_text(json.dumps({"tracing": 1, "profiles": {
        name: ["32", "64"] for name in ("winrt", "dwrite", "com", "wait")
    }}))
    monkeypatch.setattr(ManagerUtils, "get_runner_path", lambda name: str(runner))
    return runner, manifest


@pytest.mark.parametrize(("name", "supported"), [
    ("soda-11.0-25-experimental", False),
    ("soda-11.0-26-experimental", True),
    ("soda-11.0-26-experimental-x86_64", True),
    ("soda-11.0-27-experimental", True),
    ("soda-12.0-1", True),
    ("wine-11.0-26", False),
    ("proton-11.0-26", False),
])
def test_tracing_requires_new_soda(name, supported, tracing_runner):
    assert eagletracing.tracing_supported(BottleConfig(Runner=name)) is supported


def test_tracing_requires_tools_and_complete_manifest(tracing_runner):
    runner, manifest = tracing_runner
    config = BottleConfig(Runner="soda-11.0-26-experimental-aarch64")
    (runner / "bin/eagle").unlink()
    assert not eagletracing.tracing_supported(config)
    (runner / "bin/eagle").write_text("#!/bin/sh\n")
    (runner / "bin/eagle").chmod(0o755)
    manifest.write_text('{"tracing": 1, "profiles": {"wait": ["64"]}}')
    assert not eagletracing.tracing_supported(config)
    manifest.write_text("invalid")
    assert not eagletracing.tracing_supported(config)


def test_tracing_uses_selected_wine_and_quotes_paths(monkeypatch, tracing_runner, tmp_path):
    runner, _ = tracing_runner
    config = BottleConfig(Runner="soda-11.0-26-experimental", RunnerPath="/stale/runner")
    prefix = str(tmp_path / "bottle's path")
    monkeypatch.setattr(ManagerUtils, "get_bottle_path", lambda config: prefix)
    command = eagletracing.trace_command(config, shlex.quote(str(runner / "bin/wine")), prefix)
    assert shlex.split(command) == [str(runner / "bin/eagle"), "trace", "--wine",
        str(runner / "bin/wine"), "--prefix", prefix, "--logs", prefix + "/logs/runs",
        "--cwd", prefix, "--"]
    with pytest.raises(RuntimeError):
        eagletracing.trace_command(config, shlex.quote(str(tmp_path / "old/bin/wine")), prefix)


def test_every_program_launch_is_wrapped_and_tools_stay_direct(tracing_runner):
    runner, _ = tracing_runner
    config = BottleConfig(Runner="soda-11.0-26-experimental")
    config.Parameters.eagle_tracing = True
    command = WineCommand.__new__(WineCommand)
    command.config = config
    command.runner = shlex.quote(str(runner / "bin/wine"))
    command.runner_runtime = ""
    command.cwd = "/bottle/program"
    command.arguments = ""
    command.gamescope_activated = False
    command.minimal = False
    for target in ("first.exe", "second.exe"):
        assert "eagle" in command.get_cmd(target)
        assert command.get_cmd(target).endswith("-- " + target)
    command.minimal = True
    assert command.get_cmd("winepath --unix file") == command.runner + " winepath --unix file"
    command.minimal = False
    config.Parameters.eagle_tracing = False
    assert command.get_cmd("program.exe") == command.runner + " program.exe"
    config.Parameters.eagle_tracing = True
    config.Runner = "soda-11.0-25-experimental"
    assert command.get_cmd("program.exe") == command.runner + " program.exe"


def test_supported_tracing_bypasses_launch_bridge(tracing_runner):
    config = BottleConfig(Runner="soda-11.0-26-experimental")
    config.Parameters.eagle_tracing = True
    assert not WineExecutor(config, "/bottle/program.exe", program_winebridge=True).use_winebridge
    config.Runner = "soda-11.0-25-experimental"
    assert WineExecutor(config, "/bottle/program.exe", program_winebridge=True).use_winebridge
