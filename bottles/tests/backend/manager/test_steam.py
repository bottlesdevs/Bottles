import shlex

import pytest

from bottles.backend.managers.steam import SteamManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils import vdf


@pytest.mark.parametrize(
    ("flatpak_id", "expected_exe", "expected_prefix"),
    [
        (None, "bottles-cli", ["run"]),
        (
            "com.usebottles.bottles",
            "flatpak",
            [
                "run",
                "--command=bottles-cli",
                "com.usebottles.bottles",
                "run",
            ],
        ),
    ],
)
def test_steam_shortcut_quotes_apostrophes(
    tmp_path, monkeypatch, flatpak_id, expected_exe, expected_prefix
):
    config_dir = tmp_path / "userdata" / "123" / "config"
    config_dir.mkdir(parents=True)

    manager = object.__new__(SteamManager)
    manager.config = BottleConfig(Name="Hero's bottle")
    manager.userdata_path = str(tmp_path / "userdata")

    if flatpak_id:
        monkeypatch.setenv("FLATPAK_ID", flatpak_id)
    else:
        monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(
        "bottles.backend.managers.steam.ManagerUtils.get_bottle_path",
        lambda _config: "/bottle",
    )
    monkeypatch.setattr(
        "bottles.backend.managers.steam.ManagerUtils.extract_icon",
        lambda _config, _name, _path: "icon",
    )

    result = manager.add_shortcut("Alice's Game", "/bottle/game.exe")

    with open(config_dir / "shortcuts.vdf", "rb") as shortcuts_file:
        shortcut = vdf.binary_loads(shortcuts_file.read())["shortcuts"]["0"]

    assert result.ok
    assert shortcut["Exe"] == expected_exe
    assert shlex.split(shortcut["LaunchOptions"]) == expected_prefix + [
        "-b",
        "Hero's bottle",
        "-p",
        "Alice's Game",
    ]
