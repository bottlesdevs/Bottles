import subprocess

import pytest

from bottles.backend.models.config import BottleConfig
from bottles.backend.wine.wineserver import WineServer


def test_is_alive_skips_missing_bottle_directory(monkeypatch, mocker, tmp_path):
    bottle_path = tmp_path / "missing"
    config = BottleConfig(Name="Missing", Runner="sys-wine-11.0")
    pgrep = mocker.Mock()
    pgrep.stdout.read.return_value = b"123\n"
    popen = mocker.patch(
        "bottles.backend.wine.wineserver.subprocess.Popen",
        return_value=pgrep,
    )
    monkeypatch.setattr(
        "bottles.backend.wine.wineserver.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.wineserver.ManagerUtils.get_runner_path",
        lambda _runner: "/usr/bin",
    )

    assert WineServer(config).is_alive() is False
    popen.assert_called_once_with(["pgrep", "wineserver"], stdout=subprocess.PIPE)


def test_is_alive_handles_bottle_removed_during_check(monkeypatch, mocker, tmp_path):
    bottle_path = tmp_path / "removed"
    bottle_path.mkdir()
    config = BottleConfig(Name="Removed", Runner="sys-wine-11.0")
    pgrep = mocker.Mock()
    pgrep.stdout.read.return_value = b"123\n"
    mocker.patch(
        "bottles.backend.wine.wineserver.subprocess.Popen",
        side_effect=[pgrep, FileNotFoundError],
    )
    monkeypatch.setattr(
        "bottles.backend.wine.wineserver.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.wineserver.ManagerUtils.get_runner_path",
        lambda _runner: "/usr/bin",
    )

    assert WineServer(config).is_alive() is False


@pytest.mark.parametrize("signal,argument", [(-1, "-k"), (9, "-k9")])
@pytest.mark.parametrize("kind", ["bundled", "system", "proton", "steam"])
def test_kill_uses_native_server(monkeypatch, mocker, tmp_path, kind, signal, argument):
    bottle = tmp_path / "Bottle with spaces"
    runner = tmp_path / "Runner with spaces"
    config = BottleConfig(Name="Test", Path=str(bottle), Runner="soda-test")
    if kind == "system":
        config.Runner = "sys-wine-11.0"
    if kind == "steam":
        config.Environment = "Steam"
        config.RunnerPath = str(runner)
    monkeypatch.setattr(
        "bottles.backend.wine.wineserver.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.wineserver.ManagerUtils.get_runner_path",
        lambda _runner: str(runner),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.wineserver.SteamUtils.is_proton",
        lambda _runner: kind in ("proton", "steam"),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.wineserver.SteamUtils.get_dist_directory",
        lambda _runner: str(runner / ("files" if kind == "steam" else "dist")),
    )
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    process = mocker.Mock()
    process.wait.return_value = 0
    popen = mocker.patch(
        "bottles.backend.wine.wineserver.subprocess.Popen", return_value=process
    )
    launch = mocker.patch.object(WineServer, "launch")

    server = WineServer(config)
    server.kill(signal)

    launch.assert_not_called()
    args, kwargs = popen.call_args
    expected = "wineserver"
    if kind != "system":
        if kind in ("proton", "steam"):
            runner /= "files" if kind == "steam" else "dist"
        expected = str(runner / "bin/wineserver")
    assert args == ([expected, argument],)
    assert kwargs["cwd"] == str(bottle)
    assert kwargs["env"]["WINEPREFIX"] == str(bottle)
    assert kwargs.get("shell", False) is False
    process.wait.assert_called_once_with()
    assert server.returncode == 0


def test_wait_uses_native_server(monkeypatch, mocker, tmp_path):
    config = BottleConfig(Name="Test", Runner="soda-test")
    monkeypatch.setattr(
        "bottles.backend.wine.wineserver.ManagerUtils.get_bottle_path",
        lambda _config: str(tmp_path),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.wineserver.ManagerUtils.get_runner_path",
        lambda _runner: str(tmp_path / "Runner with spaces"),
    )
    monkeypatch.setattr(
        "bottles.backend.wine.wineserver.SteamUtils.is_proton", lambda _runner: False
    )
    process = mocker.Mock()
    popen = mocker.patch(
        "bottles.backend.wine.wineserver.subprocess.Popen", return_value=process
    )

    WineServer(config).wait()

    assert popen.call_args.args == (
        [str(tmp_path / "Runner with spaces/bin/wineserver"), "-w"],
    )
    assert popen.call_args.kwargs.get("shell", False) is False
    process.wait.assert_called_once_with()


def test_force_kill_keeps_sandbox_launcher_cleanup(monkeypatch, mocker, tmp_path):
    config = BottleConfig(Name="Test", Runner="soda-test")
    config.Parameters.sandbox = True
    monkeypatch.setattr(
        "bottles.backend.wine.wineserver.ManagerUtils.get_bottle_path",
        lambda _config: str(tmp_path),
    )
    terminate = mocker.patch(
        "bottles.backend.managers.sandbox.SandboxManager.terminate_prefix"
    )
    procs = mocker.patch("bottles.backend.wine.wineserver.ProcUtils.get_by_env")
    kill = mocker.patch.object(WineServer, "kill")

    WineServer(config).force_kill()

    terminate.assert_called_once_with(str(tmp_path))
    procs.assert_not_called()
    kill.assert_not_called()
