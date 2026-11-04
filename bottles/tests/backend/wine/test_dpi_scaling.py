import json
import shlex
from pathlib import Path

import pytest

from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result
from bottles.backend.wine.regkeys import RegKeys

KEY = r"HKEY_CURRENT_USER\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"


@pytest.mark.parametrize(("current", "mode", "expected"), [
    (None, "application", "~ HIGHDPIAWARE"),
    (None, "system", "~ DPIUNAWARE"),
    (None, "default", None),
    ("~ RUNASADMIN HIGHDPIAWARE", "system", "~ RUNASADMIN DPIUNAWARE"),
    ("~ RUNASADMIN DPIUNAWARE", "default", "~ RUNASADMIN"),
    ("~ HIGHDPIAWARE", "default", None),
    ("~ GDIDPISCALING DPIUNAWARE", "application", "~ HIGHDPIAWARE"),
    ("WIN7RTM", "application", "WIN7RTM HIGHDPIAWARE"),
])
def test_dpi_scaling_preserves_other_compatibility_flags(tmp_path, monkeypatch, current, mode, expected):
    drive = tmp_path / "drive_c"
    drive.mkdir()
    config = BottleConfig(Path=str(tmp_path), Custom_Path=True)
    keys = RegKeys(config)
    imports = []

    def launch(args, **kwargs):
        operation, path, *rest = shlex.split(args)
        if operation == "export":
            path = rest[0]
            value = "" if current is None else "@=" + json.dumps(current) + "\n"
            content = f'Windows Registry Editor Version 5.00\n\n[{KEY}]\n{value}"game.exe"="DPIUNAWARE"\n\n[{KEY}\\Child]\n@="Do not use this"\n'
            (drive / path[3:]).write_text(content, encoding="utf-16")
        else:
            assert operation == "import"
            imports.append((drive / path[3:]).read_text(encoding="utf-16"))
        return Result(True)

    monkeypatch.setattr(keys.reg, "launch", launch)
    result = keys.set_dpi_scaling(mode)

    assert result.ok, result.message
    assert len(imports) == 2
    assert "@=" not in imports[0]
    value = "-" if expected is None else json.dumps(expected)
    assert imports[1].endswith(f"@={value}\n")
    assert '"game.exe"' not in imports[1]
    assert not list(drive.iterdir())


@pytest.mark.parametrize("failure", ["create", "export", "import", "malformed", "type"])
def test_dpi_scaling_stops_after_registry_errors(tmp_path, monkeypatch, failure):
    drive = tmp_path / "drive_c"
    drive.mkdir()
    keys = RegKeys(BottleConfig(Path=str(tmp_path), Custom_Path=True))
    calls = []

    def launch(args, **kwargs):
        calls.append(args)
        if len(calls) == 1 and failure == "create":
            return Result(False, message="Cannot create key")
        if args.startswith("export"):
            if failure == "export":
                return Result(False, message="Cannot export key")
            path = shlex.split(args)[2]
            content = "bad export" if failure == "malformed" else f"Windows Registry Editor Version 5.00\n\n[{KEY}]\n@=dword:00000001\n"
            if failure == "import":
                content = f'Windows Registry Editor Version 5.00\n\n[{KEY}]\n@="~ RUNASADMIN"\n'
            (drive / path[3:]).write_text(content, encoding="utf-16")
        elif len(calls) > 1:
            return Result(False, message="Cannot import settings")
        return Result(True)

    monkeypatch.setattr(keys.reg, "launch", launch)
    assert not keys.set_dpi_scaling("system").ok
    assert len(calls) == (1 if failure == "create" else 3 if failure == "import" else 2)
    assert not list(drive.iterdir())


def test_dpi_scaling_rejects_unknown_modes_before_running_wine(tmp_path, monkeypatch):
    keys = RegKeys(BottleConfig(Path=str(tmp_path), Custom_Path=True))
    monkeypatch.setattr(keys.reg, "launch", lambda *_args, **_kwargs: pytest.fail("Unexpected Wine launch"))
    assert not keys.set_dpi_scaling("enhanced").ok
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(("flags", "expected"), [("", "default"), ("~ RUNASADMIN", "default"), ("~ HIGHDPIAWARE", "application"), ("~ DPIUNAWARE", "system"), ("HIGHDPIAWARE DPIUNAWARE", "system")])
def test_reading_the_dpi_mode_keeps_existing_flags(tmp_path, monkeypatch, flags, expected):
    drive = tmp_path / "drive_c"
    drive.mkdir()
    keys = RegKeys(BottleConfig(Path=str(tmp_path), Custom_Path=True))
    imported = []

    def launch(args, **kwargs):
        tokens = shlex.split(args)
        if tokens[0] == "import":
            imported.append((drive / tokens[1][3:]).read_text(encoding="utf-16"))
        else:
            (drive / tokens[2][3:]).write_text(f"Windows Registry Editor Version 5.00\n\n[{KEY}]\n@={json.dumps(flags)}\n", encoding="utf-16")
        return Result(True)

    monkeypatch.setattr(keys.reg, "launch", launch)
    result = keys.get_dpi_scaling()

    assert result.ok
    assert result.data == expected
    assert len(imported) == 1
    assert "@=" not in imported[0]
    assert not list(drive.iterdir())
