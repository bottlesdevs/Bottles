import shlex
from pathlib import Path

import pytest

from bottles.backend.globals import Paths
from bottles.backend.managers import steam as steam_module
from bottles.backend.managers.steam import SteamManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils import vdf


def _write_vdf(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as vdf_file:
        vdf.dump(data, vdf_file, pretty=True)


def test_installed_game_is_discovered_without_localconfig_entry(tmp_path, monkeypatch):
    appid = "22380"
    steam_path = tmp_path / "Steam"
    runner_path = steam_path / "compatibilitytools.d" / "GE-Proton10-30"
    _write_vdf(
        runner_path / "toolmanifest.vdf",
        {
            "manifest": {
                "commandline": "/proton %verb%",
                "compatmanager_layer_name": "proton",
            }
        },
    )
    compatdata_path = steam_path / "steamapps" / "compatdata" / appid
    (compatdata_path / "pfx").mkdir(parents=True)
    config_lines = [
        "GE-Proton10-30",
        f"{runner_path}/files/share/fonts/",
    ] + [""] * 10
    (compatdata_path / "config_info").write_text("\n".join(config_lines))
    _write_vdf(
        steam_path / "steamapps" / "libraryfolders.vdf",
        {
            "libraryfolders": {
                "0": {
                    "path": str(steam_path),
                    "apps": {appid: "1"},
                }
            }
        },
    )
    _write_vdf(
        steam_path / "steamapps" / f"appmanifest_{appid}.acf",
        {
            "AppState": {
                "appid": appid,
                "name": "Fallout: New Vegas",
                "installdir": "Fallout New Vegas",
                "LastUpdated": "0",
            }
        },
    )
    _write_vdf(
        steam_path / "userdata" / "123" / "config" / "localconfig.vdf",
        {"UserLocalConfigStore": {"Software": {"Valve": {"Steam": {"Apps": {}}}}}},
    )
    monkeypatch.setattr(
        SteamManager,
        "_SteamManager__find_steam_path",
        lambda _self: str(steam_path),
    )
    monkeypatch.setattr(Paths, "steam", str(tmp_path / "bottles-steam"))
    SteamManager.get_runner_path.cache_clear()

    config = SteamManager().list_prefixes()[appid]

    assert config.Name == "Fallout: New Vegas"
    assert config.Path == str(compatdata_path / "pfx")
    assert config.RunnerPath == str(runner_path)


def test_steam_path_skips_directory_without_steam_data(tmp_path, monkeypatch):
    steam_root = tmp_path / ".steam" / "debian-installation"
    (steam_root / "steamapps").mkdir(parents=True)
    config_dir = steam_root / "userdata" / "123" / "config"
    config_dir.mkdir(parents=True)

    misleading_path = tmp_path / ".local" / "share" / "Steam"
    misleading_path.parent.mkdir(parents=True)
    misleading_path.symlink_to(tmp_path / ".steam", target_is_directory=True)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "bottles.backend.managers.steam.ManagerUtils.get_bottle_path",
        lambda _config: "/bottle",
    )
    monkeypatch.setattr(
        "bottles.backend.managers.steam.ManagerUtils.extract_icon",
        lambda _config, _name, _path: "icon",
    )

    manager = SteamManager(BottleConfig(Name="Test"))
    result = manager.add_shortcut("Game", "/bottle/game.exe")

    assert manager.steam_path == str(steam_root)
    assert manager.steamapps_path == str(steam_root / "steamapps")
    assert manager.userdata_path == str(steam_root / "userdata")
    assert result.ok
    assert (config_dir / "shortcuts.vdf").is_file()


def test_steam_path_keeps_install_without_user_data(tmp_path, monkeypatch):
    steam_root = (
        tmp_path / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam"
    )
    (steam_root / "ubuntu12_32").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    manager = SteamManager(check_only=True)

    assert manager.steam_path == str(steam_root)


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


def test_list_compatibility_tools_keeps_only_valid_proton(tmp_path, monkeypatch):
    flatpak_steam = (
        tmp_path / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam"
    )
    flatpak_steam.mkdir(parents=True)
    steam_root = tmp_path / ".local" / "share" / "Steam"
    tools = steam_root / "compatibilitytools.d"
    proton = tools / "GE-Proton10-4"
    proton.mkdir(parents=True)
    (proton / "toolmanifest.vdf").write_text(
        '"manifest"\n{\n'
        '    "commandline" "/proton run"\n'
        '    "compatmanager_layer_name" "proton"\n'
        "}\n"
    )
    invalid = tools / "Broken-Proton"
    invalid.mkdir()
    (invalid / "toolmanifest.vdf").write_text('"manifest"\n{')
    (tools / "Not-Proton").mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(steam_module, "STEAM_COMPATIBILITY_TOOL_PATHS", ())

    manager = SteamManager(check_only=True)

    assert manager.steam_path == str(flatpak_steam)
    assert manager.list_compatibility_tools() == {
        "GE-Proton10-4": str(proton),
    }


def test_list_compatibility_tools_without_steam(tmp_path, monkeypatch):
    tools = tmp_path / "flatpak-extension"
    proton = tools / "GE-Proton10-4"
    proton.mkdir(parents=True)
    (proton / "toolmanifest.vdf").write_text(
        '"manifest"\n{\n'
        '    "commandline" "/proton run"\n'
        '    "compatmanager_layer_name" "proton"\n'
        "}\n"
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "empty-home")
    monkeypatch.setattr(steam_module, "STEAM_COMPATIBILITY_TOOL_PATHS", (str(tools),))

    manager = SteamManager(check_only=True)

    assert manager.steam_path is None
    assert manager.list_compatibility_tools() == {
        "GE-Proton10-4": str(proton),
    }
