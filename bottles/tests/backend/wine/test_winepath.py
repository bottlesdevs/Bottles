import shlex

from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.wine.winebridge import WineBridge
from bottles.backend.wine.winepath import WinePath


def test_winepath_shell_quotes_apostrophes(monkeypatch):
    captured = {}

    def fake_launch(self, **kwargs):
        captured.update(kwargs)
        return Result(True, data=r"Z:\tmp\O'Brien App.exe")

    monkeypatch.setattr(WinePath, "launch", fake_launch)

    path = "/tmp/O'Brien App.exe"
    result = WinePath(BottleConfig()).to_windows(
        path,
        sandbox_override="off",
    )

    assert result == r"Z:\tmp\O'Brien App.exe"
    assert captured["args"] == f"--windows {shlex.quote(path)}"
    assert captured["sandbox_override"] == "off"


def test_winepath_preserves_repeated_spaces(monkeypatch):
    captured = {}

    def fake_launch(self, **kwargs):
        captured.update(kwargs)
        return Result(True, data=r"Z:\tmp\My  Game")

    monkeypatch.setattr(WinePath, "launch", fake_launch)

    path = "/tmp/My  Game"
    result = WinePath(BottleConfig()).to_windows(path)

    assert result == r"Z:\tmp\My  Game"
    assert captured["args"] == f"--windows {shlex.quote(path)}"


def test_native_windows_conversion_is_idempotent():
    path = r"C:\Program Files\Example\example.exe"

    result = WinePath(BottleConfig()).to_windows(path, native=True)

    assert result == path


def test_native_steam_conversion_uses_prefix_path(tmp_path):
    prefix = tmp_path / "steamapps" / "compatdata" / "123" / "pfx"
    config = BottleConfig(Environment="Steam", Path=str(prefix), CompatData="123")
    winepath = WinePath(config)

    result = winepath.to_unix(r"C:\Program Files\Example", native=True)

    assert result == str(prefix / "dosdevices/c:/Program Files/Example")


def test_winebridge_preserves_windows_executable_path(monkeypatch):
    captured = {}

    def fake_launch(self, **kwargs):
        captured.update(kwargs)
        return Result(True)

    monkeypatch.setattr(WineBridge, "launch", fake_launch)
    path = r"C:\Program Files\Example\example.exe"

    WineBridge(BottleConfig()).run_exe(path)

    assert captured["args"] == f'runExe "{path}"'


def test_winebridge_forwards_launch_context(monkeypatch):
    captured = {}

    def fake_launch(self, **kwargs):
        captured.update(kwargs)
        return Result(True)

    monkeypatch.setattr(WineBridge, "launch", fake_launch)

    WineBridge(BottleConfig()).run_exe(
        r"C:\Games\example.exe",
        terminal=True,
        environment={"GAME_MODE": "1"},
        cwd=r"C:\Games",
        sandbox_override="off",
    )

    assert captured["terminal"] is True
    assert captured["environment"] == {"GAME_MODE": "1"}
    assert captured["cwd"] == r"C:\Games"
    assert captured["sandbox_override"] == "off"
