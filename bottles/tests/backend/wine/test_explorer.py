from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.wine.explorer import Explorer


def test_virtual_desktop_wraps_hidden_program_in_background_start(monkeypatch):
    captured = {}

    def fake_launch(self, **kwargs):
        captured.update(kwargs)
        return Result(True)

    monkeypatch.setattr(Explorer, "launch", fake_launch)

    config = BottleConfig(Name="TestBottle", Path="TestBottlePath")
    result = Explorer(config).launch_desktop(
        desktop="probe",
        width=1280,
        height=720,
        program=r"'C:\Program Files\Example\example.exe'",
        args="--safe-mode",
        background=True,
        sandbox_override="off",
    )

    assert result.status is True
    assert captured["args"] == (
        r"/desktop=probe,1280x720 start /b /wait "
        r"'C:\Program Files\Example\example.exe' --safe-mode"
    )
    assert captured["sandbox_override"] == "off"
