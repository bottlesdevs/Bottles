from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.wine.start import Start
from bottles.backend.wine.wineprogram import WineProgram


def _make_config() -> BottleConfig:
    return BottleConfig(Name="TestBottle", Path="TestBottlePath", Environment="Custom")


def test_start_background_adds_switch_and_forwards_sandbox(monkeypatch):
    captured = {}

    def fake_launch(self, **kwargs):
        captured.update(kwargs)
        return Result(True)

    monkeypatch.setattr(Start, "launch", fake_launch)

    Start(_make_config()).run(
        file=r"'C:\Program Files\Example\example.exe'",
        terminal=False,
        background=True,
        sandbox_override="off",
    )

    assert captured["args"][0] == (r"/b /wait 'C:\Program Files\Example\example.exe'")
    assert captured["sandbox_override"] == "off"


def test_start_places_unix_path_after_all_options(monkeypatch):
    captured = {}

    def fake_launch(self, **kwargs):
        captured.update(kwargs)
        return Result(True)

    monkeypatch.setattr(Start, "launch", fake_launch)

    Start(_make_config()).run(
        file="/tmp/example.exe",
        terminal=False,
        background=True,
    )

    assert captured["args"][0] == "/b /wait /unix /tmp/example.exe"


def test_start_keeps_unix_working_directory_on_host(monkeypatch):
    captured = {}

    def fake_launch(self, **kwargs):
        captured.update(kwargs)
        return Result(True)

    def fail_conversion(*_args, **_kwargs):
        raise AssertionError("unix working directory was converted")

    monkeypatch.setattr(Start, "launch", fake_launch)
    monkeypatch.setattr(
        "bottles.backend.wine.start.WinePath.to_windows",
        fail_conversion,
    )

    Start(_make_config()).run(
        file="/games/Example/example.exe",
        cwd="/games/Example",
        terminal=False,
        host_cwd=True,
    )

    assert captured["args"][0] == "/wait /unix /games/Example/example.exe"
    assert captured["cwd"] == "/games/Example"


def test_start_quotes_external_unix_path(monkeypatch):
    captured = {}

    def fake_launch(self, **kwargs):
        captured.update(kwargs)
        return Result(True)

    monkeypatch.setattr(Start, "launch", fake_launch)

    Start(_make_config()).run(
        file="'/games/KeePass Portable/KeePass.exe'",
        cwd="/games/KeePass Portable",
        terminal=False,
        host_cwd=True,
    )

    assert captured["args"][0] == (
        "/wait /unix '/games/KeePass Portable/KeePass.exe'"
    )
    assert captured["cwd"] == "/games/KeePass Portable"


def test_start_converts_unix_working_directory(monkeypatch):
    captured = {}

    def fake_launch(self, **kwargs):
        captured.update(kwargs)
        return Result(True)

    def fake_to_windows(self, path, native=False, sandbox_override=None):
        captured["converted_cwd"] = path
        captured["native"] = native
        captured["conversion_sandbox_override"] = sandbox_override
        return r"Z:\Games\Example"

    monkeypatch.setattr(Start, "launch", fake_launch)
    monkeypatch.setattr(
        "bottles.backend.wine.start.WinePath.to_windows",
        fake_to_windows,
    )

    Start(_make_config()).run(
        file="/games/Example/example.exe",
        cwd="/games/Example",
        terminal=False,
        sandbox_override="off",
    )

    assert captured["converted_cwd"] == "/games/Example"
    assert captured["native"] is False
    assert captured["conversion_sandbox_override"] == "off"
    assert captured["args"][0] == (
        r"/wait /d 'Z:\Games\Example' /unix /games/Example/example.exe"
    )


def test_start_converts_unix_working_directory_for_windows_path(monkeypatch):
    captured = {}

    def fake_launch(self, **kwargs):
        captured.update(kwargs)
        return Result(True)

    def fake_to_windows(self, path, native=False, sandbox_override=None):
        captured["converted_cwd"] = path
        captured["native"] = native
        captured["conversion_sandbox_override"] = sandbox_override
        return r"Z:\Games\Example"

    monkeypatch.setattr(Start, "launch", fake_launch)
    monkeypatch.setattr(
        "bottles.backend.wine.start.WinePath.to_windows",
        fake_to_windows,
    )

    Start(_make_config()).run(
        file=r"C:\Games\Example\example.exe",
        cwd="/games/Example",
        terminal=False,
        background=True,
        sandbox_override="off",
    )

    assert captured["converted_cwd"] == "/games/Example"
    assert captured["native"] is False
    assert captured["conversion_sandbox_override"] == "off"
    assert captured["args"][0] == (
        r"/b /wait /d 'Z:\Games\Example' C:\Games\Example\example.exe"
    )


def test_start_uses_wine_directory_option(monkeypatch):
    captured = {}

    def fake_launch(self, **kwargs):
        captured.update(kwargs)
        return Result(True)

    monkeypatch.setattr(Start, "launch", fake_launch)

    Start(_make_config()).run(
        file=r"'C:\Program Files\Example\example.exe'",
        cwd=r"C:\Working Dir",
        terminal=False,
        background=True,
    )

    assert captured["args"][0] == (
        r"/b /wait /d 'C:\Working Dir' 'C:\Program Files\Example\example.exe'"
    )


def test_wine_program_forwards_sandbox_override(monkeypatch):
    captured = {}

    class FakeWineCommand:
        def __init__(self, _config, **kwargs):
            captured.update(kwargs)

        @staticmethod
        def run():
            return Result(True)

    monkeypatch.setattr(
        "bottles.backend.wine.wineprogram.WineCommand",
        FakeWineCommand,
    )

    result = WineProgram(_make_config()).launch(sandbox_override="off")

    assert result.status is True
    assert captured["sandbox_override"] == "off"
