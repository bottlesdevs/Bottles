import shlex
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from bottles.backend.globals import Paths
from bottles.backend.managers import steam as steam_module
from bottles.backend.managers.steam import SteamManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.utils import vdf
from bottles.backend.utils.steam import SteamUtils


def _write_vdf(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as vdf_file:
        vdf.dump(data, vdf_file, pretty=True)


def _write_ge_proton_prefix(steam_path, appid):
    runner_path = steam_path / "compatibilitytools.d" / "GE-Proton10-30"
    _write_vdf(
        runner_path / "toolmanifest.vdf",
        {
            "manifest": {
                "version": "2",
                "commandline": "/proton %verb%",
                "compatmanager_layer_name": "proton",
            }
        },
    )

    compatdata_path = steam_path / "steamapps" / "compatdata" / str(appid)
    (compatdata_path / "pfx").mkdir(parents=True)
    config_lines = [
        "GE-Proton10-30",
        f"{runner_path}/files/share/fonts/",
        f"{runner_path}/files/lib/",
        str(steam_path),
    ] + [""] * 10
    (compatdata_path / "config_info").write_text("\n".join(config_lines))
    return compatdata_path, runner_path

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


def test_umu_shortcut_uses_umu_cli(tmp_path, monkeypatch):
    config_dir = tmp_path / "userdata" / "123" / "config"
    config_dir.mkdir(parents=True)
    game_id = UUID("e33f87f0-648e-44d2-bb73-78c9f60f77cf")
    game = SimpleNamespace(
        id=game_id,
        name="Test Game",
        executable=tmp_path / "prefix" / "game.exe",
    )
    manager = object.__new__(SteamManager)
    manager.userdata_path = str(tmp_path / "userdata")
    monkeypatch.delenv("FLATPAK_ID", raising=False)

    result = manager.add_umu_shortcut(game)

    with open(config_dir / "shortcuts.vdf", "rb") as shortcuts_file:
        shortcut = vdf.binary_loads(shortcuts_file.read())["shortcuts"]["0"]

    assert result.ok
    assert shortcut["Exe"] == "bottles-cli"
    assert shlex.split(shortcut["LaunchOptions"]) == [
        "umu",
        "run",
        "--game",
        str(game_id),
    ]
    assert shortcut["StartDir"] == str(game.executable.parent)


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


def test_ge_proton_runner_path(tmp_path):
    compatdata_path, runner_path = _write_ge_proton_prefix(tmp_path, "123")
    SteamManager.get_runner_path.cache_clear()

    assert SteamManager.get_runner_path(str(compatdata_path)) == str(runner_path)


@pytest.mark.parametrize("library_name", [None, "SecondaryLibrary"])
def test_non_steam_ge_proton_prefix_is_detected(tmp_path, monkeypatch, library_name):
    appid = 4218887470
    steam_path = tmp_path / "Steam"
    library_path = tmp_path / library_name if library_name else steam_path
    compatdata_path, runner_path = _write_ge_proton_prefix(library_path, appid)
    _write_vdf(
        steam_path / "steamapps" / "libraryfolders.vdf",
        {
            "libraryfolders": {
                "0": {
                    "path": str(library_path),
                    "apps": {},
                }
            }
        },
    )
    _write_vdf(
        steam_path / "userdata" / "123" / "config" / "localconfig.vdf",
        {"UserLocalConfigStore": {"Software": {"Valve": {"Steam": {"Apps": {}}}}}},
    )
    shortcuts_path = steam_path / "userdata" / "123" / "config" / "shortcuts.vdf"
    shortcuts_path.write_bytes(
        vdf.binary_dumps(
            {
                "shortcuts": {
                    "0": {
                        "appid": appid - 2**32,
                        "AppName": "GE Shortcut",
                        "Exe": '"/games/example.exe"',
                        "StartDir": '"/games"',
                        "LaunchOptions": "",
                        "LastPlayTime": 0,
                    }
                }
            }
        )
    )

    monkeypatch.setattr(
        SteamManager,
        "_SteamManager__find_steam_path",
        lambda _self: str(steam_path),
    )
    monkeypatch.setattr(Paths, "steam", str(tmp_path / "bottles-steam"))
    SteamManager.get_runner_path.cache_clear()

    config = SteamManager().list_prefixes()[str(appid)]

    assert config.Name == "GE Shortcut"
    assert config.Path == str(compatdata_path / "pfx")
    assert config.RunnerPath == str(runner_path)


def test_non_steam_shortcut_appid_falls_back_to_crc():
    shortcut = {
        "Exe": '"/games/example.exe"',
        "AppName": "GE Shortcut",
    }

    assert SteamManager._get_shortcut_appid(shortcut) == 3641742335


def test_non_steam_launch_options_are_saved_to_shortcuts_vdf(tmp_path):
    appid = 4218887470
    config_dir = tmp_path / "userdata" / "123" / "config"
    config_dir.mkdir(parents=True)
    shortcuts_path = config_dir / "shortcuts.vdf"
    unrelated = {
        "appid": -1,
        "AppName": "Unrelated",
        "Exe": '"/games/other.exe"',
        "LaunchOptions": "--unchanged",
    }
    trailing_data = b"steam-extra-data"
    shortcuts_path.write_bytes(
        vdf.binary_dumps(
            {
                "shortcuts": {
                    "0": {
                        "appid": appid - 2**32,
                        "AppName": "GE Shortcut",
                        "Exe": '"/games/example.exe"',
                        "LaunchOptions": "DXVK_HUD=1 %command% --old",
                    },
                    "1": unrelated,
                }
            }
        )
        + trailing_data
    )
    manager = object.__new__(SteamManager)
    manager.userdata_path = str(tmp_path / "userdata")
    manager.localconfig = {}

    manager.set_launch_options(
        str(appid),
        {"command": "gamemoderun", "env_vars": {"FOO": "bar"}},
    )

    data = vdf.binary_loads(shortcuts_path.read_bytes(), raise_on_remaining=False)[
        "shortcuts"
    ]
    command, args, env_vars = SteamUtils.handle_launch_options(
        data["0"]["LaunchOptions"]
    )
    assert command == "gamemoderun"
    assert args.strip() == "--old"
    assert env_vars == {"DXVK_HUD": "1", "FOO": "bar"}
    assert data["1"] == unrelated
    assert shortcuts_path.read_bytes().endswith(trailing_data)


def test_regular_steam_launch_options_are_saved_to_localconfig(tmp_path):
    manager = object.__new__(SteamManager)
    manager.userdata_path = None
    manager.localconfig_path = str(tmp_path / "localconfig.vdf")
    manager.localconfig = {
        "UserLocalConfigStore": {
            "Software": {
                "Valve": {
                    "Steam": {
                        "Apps": {"123": {"LaunchOptions": "DXVK_HUD=1 %command% --old"}}
                    }
                }
            }
        }
    }

    manager.set_launch_options(
        "123",
        {"command": "gamemoderun", "env_vars": {"FOO": "bar"}},
    )

    launch_options = manager.localconfig["UserLocalConfigStore"]["Software"]["Valve"][
        "Steam"
    ]["Apps"]["123"]["LaunchOptions"]
    command, args, env_vars = SteamUtils.handle_launch_options(launch_options)
    assert command == "gamemoderun"
    assert args.strip() == "--old"
    assert env_vars == {"DXVK_HUD": "1", "FOO": "bar"}


def test_malformed_shortcuts_file_is_ignored(tmp_path):
    config_dir = tmp_path / "userdata" / "123" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "shortcuts.vdf").write_bytes(b"not a binary vdf")
    manager = object.__new__(SteamManager)
    manager.userdata_path = str(tmp_path / "userdata")

    assert manager.list_shortcuts() == {}
