from pathlib import Path
from types import SimpleNamespace

import pytest

from bottles.backend.globals import Paths, TrdyPaths
from bottles.backend.managers.importer import ImportManager
from bottles.backend.models.result import Result
from bottles.backend.models.config import BottleConfig


def _disable_default_locations(monkeypatch, tmp_path):
    monkeypatch.setattr(TrdyPaths, "wine", str(tmp_path / "missing-wine"))
    monkeypatch.setattr(TrdyPaths, "lutris", str(tmp_path / "missing-lutris"))
    monkeypatch.setattr(
        TrdyPaths,
        "playonlinux",
        str(tmp_path / "missing-playonlinux"),
    )
    monkeypatch.setattr(TrdyPaths, "bottlesv1", str(tmp_path / "missing-bottles"))


def test_search_wineprefixes_accepts_selected_root_or_prefix(tmp_path, monkeypatch):
    _disable_default_locations(monkeypatch, tmp_path)
    root = tmp_path / "PlayOnLinux [prefixes]"
    first = root / "First Prefix"
    first.joinpath("drive_c").mkdir(parents=True)
    direct = tmp_path / "Direct Prefix"
    direct.joinpath("drive_c").mkdir(parents=True)

    result = ImportManager.search_wineprefixes([str(root), str(direct)])

    assert result.status
    assert [
        (prefix["Name"], prefix["Manager"], Path(prefix["Path"]))
        for prefix in result.data["wineprefixes"]
    ] == [
        ("First Prefix", "Manual", first),
        ("Direct Prefix", "Manual", direct),
    ]


def test_import_wineprefix_copies_spaces_hidden_files_and_symlinks(
    tmp_path, monkeypatch
):
    source = tmp_path / "Prefix With Spaces"
    source.joinpath("drive_c").mkdir(parents=True)
    source.joinpath(".registry").write_text("hidden")
    source.joinpath("dosdevices").mkdir()
    source.joinpath("dosdevices", "c:").symlink_to("../drive_c")
    destination = tmp_path / "bottles"
    destination.mkdir()
    monkeypatch.setattr(Paths, "bottles", str(destination))

    manager = SimpleNamespace(
        get_latest_runner=lambda: "soda-9.0-1",
        update_bottles=lambda **_kwargs: None,
    )
    result = ImportManager(manager).import_wineprefix(
        {
            "Name": source.name,
            "Manager": "Manual",
            "Path": str(source),
            "Lock": False,
        }
    )

    imported = destination / f"Imported_{source.name}"
    assert result.status
    assert imported.joinpath(".registry").read_text() == "hidden"
    assert imported.joinpath("dosdevices", "c:").is_symlink()
    assert imported.joinpath("dosdevices", "c:").readlink() == Path("../drive_c")
    assert imported.joinpath("bottle.yml").is_file()
    assert not imported.joinpath("bottle.lock").exists()
    assert source.joinpath("bottle.lock").is_file()


def test_import_wineprefix_rolls_back_when_config_cannot_be_saved(
    tmp_path, monkeypatch
):
    source = tmp_path / "Broken Prefix"
    source.joinpath("drive_c").mkdir(parents=True)
    destination = tmp_path / "bottles"
    destination.mkdir()
    monkeypatch.setattr(Paths, "bottles", str(destination))
    monkeypatch.setattr(
        "bottles.backend.managers.importer.BottleConfig.dump",
        lambda *_args, **_kwargs: Result(False),
    )
    manager = SimpleNamespace(get_latest_runner=lambda: "soda-9.0-1")

    result = ImportManager(manager).import_wineprefix(
        {
            "Name": source.name,
            "Manager": "Manual",
            "Path": str(source),
            "Lock": False,
        }
    )

    assert not result.status
    assert not destination.joinpath(f"Imported_{source.name}").exists()
    assert not source.joinpath("bottle.lock").exists()


@pytest.mark.parametrize("compatible_runner", (True, False))
def test_import_win32_selects_compatible_runner(tmp_path, monkeypatch, compatible_runner):
    source = tmp_path / "32-bit Prefix"
    source.joinpath("drive_c").mkdir(parents=True)
    source.joinpath("system.reg").write_text("WINE REGISTRY Version 2\n#arch=win32\n")
    runners = tmp_path / "runners"
    unix64 = runners / "wow64-only/lib/wine/x86_64-unix/ntdll.so"
    unix64.parent.mkdir(parents=True)
    unix64.touch()
    available = ["wow64-only"]
    if compatible_runner:
        unix32 = runners / "dual-unix/lib/wine/i386-unix/ntdll.so"
        unix32.parent.mkdir(parents=True)
        unix32.touch()
        available.append("dual-unix")
    destination = tmp_path / "bottles"
    destination.mkdir()
    monkeypatch.setattr(Paths, "bottles", str(destination))
    monkeypatch.setattr(Paths, "runners", str(runners))
    manager = SimpleNamespace(
        get_latest_runner=lambda: "wow64-only",
        runners_available=available,
        update_bottles=lambda **_kwargs: None,
    )

    result = ImportManager(manager).import_wineprefix(
        {"Name": source.name, "Path": str(source)}
    )

    imported = destination / f"Imported_{source.name}"
    assert result.ok == compatible_runner
    if compatible_runner:
        config = BottleConfig.load(str(imported / "bottle.yml"))
        assert config.data.Arch == "win32"
        assert config.data.Runner == "dual-unix"
    else:
        assert "32-bit Unix support" in result.message
        assert not imported.exists()
        assert not source.joinpath("bottle.lock").exists()
