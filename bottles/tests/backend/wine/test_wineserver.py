import subprocess

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
