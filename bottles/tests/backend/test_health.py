from bottles.backend.health import HealthChecker


def test_health_results_report_vulkan_support():
    checker = object.__new__(HealthChecker)
    checker.desktop = "GNOME"
    checker.x11 = False
    checker.x11_port = ""
    checker.wayland = True
    checker.gpus = {"vendors": {"amd": {}}}
    checker.vulkan = True
    checker.kernel = "Linux"
    checker.kernel_version = "6.0"
    checker.disk = {}
    checker.ram = {}
    checker.bottles_envs = {}

    results = checker.get_results()

    assert results["Graphics"]["Vulkan"] is True
    assert results["Graphics"]["vendors"] == {"amd": {}}


def test_x_display_uses_the_session_display(monkeypatch):
    from bottles.backend.utils.display import DisplayUtils

    DisplayUtils.get_x_display.cache_clear()
    monkeypatch.setenv("DISPLAY", ":7")
    try:
        assert DisplayUtils.get_x_display() == ":7"
    finally:
        DisplayUtils.get_x_display.cache_clear()


def test_x_display_probe_skips_stalled_displays(monkeypatch):
    import subprocess
    from types import SimpleNamespace
    from bottles.backend.utils import display

    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[-1] == ":0":
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return SimpleNamespace(stdout=b"vendor string: The X.Org Foundation")

    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setattr(display.subprocess, "run", run)
    display.DisplayUtils.get_x_display.cache_clear()
    try:
        assert display.DisplayUtils.get_x_display() == ":1"
        assert [argv[-1] for argv, kwargs in calls] == [":0", ":1"]
        assert all(kwargs["timeout"] == 1 for argv, kwargs in calls)
        assert all(not kwargs.get("shell") for argv, kwargs in calls)
    finally:
        display.DisplayUtils.get_x_display.cache_clear()


def test_x_display_probe_handles_missing_xdpyinfo(monkeypatch):
    from bottles.backend.utils import display

    def run(*args, **kwargs):
        raise FileNotFoundError("xdpyinfo")

    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setattr(display.subprocess, "run", run)
    display.DisplayUtils.get_x_display.cache_clear()
    try:
        assert display.DisplayUtils.get_x_display() is False
    finally:
        display.DisplayUtils.get_x_display.cache_clear()


def test_x_display_probe_terminates_a_stalled_helper(monkeypatch, tmp_path):
    import os
    import sys
    import time
    import pytest
    from bottles.backend.utils.display import DisplayUtils

    pids = tmp_path / "helper-pids"
    helper = tmp_path / "xdpyinfo"
    helper.write_text(
        f"#!{sys.executable}\n"
        "import os, time\n"
        f"with open({str(pids)!r}, 'a') as f: f.write(str(os.getpid()) + '\\n')\n"
        "time.sleep(60)\n"
    )
    helper.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv("DISPLAY", raising=False)
    DisplayUtils.get_x_display.cache_clear()
    try:
        started = time.monotonic()
        assert DisplayUtils.get_x_display() is False
        assert time.monotonic() - started < 6
        helper_pids = pids.read_text().splitlines()
        assert len(helper_pids) == 3
        for pid in helper_pids:
            with pytest.raises(ProcessLookupError):
                os.kill(int(pid), 0)
    finally:
        DisplayUtils.get_x_display.cache_clear()
