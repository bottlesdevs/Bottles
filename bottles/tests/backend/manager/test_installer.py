import threading

import pytest

from bottles.backend.managers.installer import InstallerManager
from bottles.backend.models.config import BottleConfig
from bottles.backend.models.result import Result


@pytest.mark.parametrize(
    ("channel", "include_unstable", "expected"),
    [
        ("stable", False, True),
        ("rc", False, False),
        ("unstable", False, False),
        ("unstable", True, True),
    ],
)
def test_installer_respects_release_channel(channel, include_unstable, expected):
    installer = ("test", {"Channel": channel})

    assert InstallerManager.supports_channel(installer, include_unstable) is expected


@pytest.mark.parametrize(
    ("runners", "runner", "expected"),
    [
        (None, "soda-11.0-10", True),
        (["soda-11.0-11-experimental"], "soda-11.0-11-experimental", True),
        (
            ["soda-11.0-11-experimental"],
            "soda-11.0-11-experimental-x86_64",
            True,
        ),
        (["soda-11.0-11-experimental"], "soda-11.0-10", False),
        ("soda-11.0-11-experimental", "soda-11.0-11-experimental", False),
    ],
)
def test_installer_respects_compatible_runners(runners, runner, expected):
    metadata = {} if runners is None else {"Runners": runners}
    installer = ("test", metadata)

    assert InstallerManager.supports_runner(installer, runner) is expected


@pytest.mark.parametrize("current_value", [True, False])
def test_installer_applies_window_decoration_parameter(mocker, current_value):
    registry = mocker.patch(
        "bottles.backend.managers.installer.RegKeys",
        autospec=True,
    )
    manager = mocker.Mock()
    installer = object.__new__(InstallerManager)
    installer._InstallerManager__manager = manager
    config = BottleConfig(Name="Test")
    config.Parameters.decorated = current_value

    installer._InstallerManager__set_parameters(config, {"decorated": False})

    registry.assert_called_once_with(config)
    registry.return_value.set_decorated.assert_called_once_with(False)
    manager.update_config.assert_called_once_with(
        config=config,
        key="decorated",
        value=False,
        scope="Parameters",
    )


def test_installer_preserves_file_associations_for_existing_program(
    mocker, monkeypatch, tmp_path
):
    manager = mocker.Mock()
    installer = object.__new__(InstallerManager)
    installer._InstallerManager__manager = manager
    config = BottleConfig(
        Name="Test",
        Path=str(tmp_path),
        External_Programs={
            "existing": {
                "name": "Editor",
                "path": "C:\\Program Files\\Editor\\editor.exe",
                "file_extensions": [".txt", ".json"],
            }
        },
    )
    manifest = {
        "Name": "Editor",
        "Executable": {
            "file": "editor.exe",
            "name": "Editor",
            "path": "Program Files/Editor/editor.exe",
            "icon": "editor.png",
        },
    }
    created = []

    monkeypatch.setattr(installer, "get_installer", lambda _name: manifest)
    monkeypatch.setattr(
        installer,
        "_InstallerManager__download_icon",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "bottles.backend.managers.installer.ManagerUtils.get_bottle_path",
        lambda _config: str(tmp_path),
    )
    monkeypatch.setattr(
        "bottles.backend.managers.installer.ManagerUtils.create_desktop_entry",
        lambda _config, program, *_args: created.append(program),
    )

    result = installer.install(config, ("editor",), lambda: None)

    assert result.status is True
    assert created[0]["file_extensions"] == [".txt", ".json"]
    assert next(iter(config.External_Programs.values()))["file_extensions"] == [
        ".txt",
        ".json",
    ]


def test_installer_registers_program_without_icon(mocker, monkeypatch, tmp_path):
    manager = mocker.Mock()
    installer = object.__new__(InstallerManager)
    installer._InstallerManager__manager = manager
    config = BottleConfig(Name="Test", Path=str(tmp_path))
    manifest = {
        "Name": "Editor",
        "Executable": {
            "file": "editor.exe",
            "name": "Editor",
            "path": "Program Files/Editor/editor.exe",
        },
    }

    monkeypatch.setattr(installer, "get_installer", lambda _name: manifest)
    monkeypatch.setattr(
        "bottles.backend.managers.installer.ManagerUtils.get_bottle_path",
        lambda _config: str(tmp_path),
    )
    desktop_entry = mocker.patch(
        "bottles.backend.managers.installer.ManagerUtils.create_desktop_entry"
    )

    result = installer.install(config, ("editor",), lambda: None)

    assert result.status is True
    desktop_entry.assert_called_once_with(
        config,
        mocker.ANY,
        False,
        "",
    )


def test_installer_registers_multiple_installed_programs(
    mocker, monkeypatch, tmp_path
):
    manager = mocker.Mock()
    installer = object.__new__(InstallerManager)
    installer._InstallerManager__manager = manager
    config = BottleConfig(Name="Test", Path=str(tmp_path))
    manifest = {
        "Name": "Office",
        "Executables": [
            {
                "file": "WINWORD.EXE",
                "name": "Microsoft Word",
                "path": "Program Files/Microsoft Office/WINWORD.EXE",
            },
            {
                "file": "EXCEL.EXE",
                "name": "Microsoft Excel",
                "path": "Program Files/Microsoft Office/EXCEL.EXE",
            },
        ],
    }
    office = tmp_path / "drive_c" / "Program Files" / "Microsoft Office"
    office.mkdir(parents=True)
    (office / "WINWORD.EXE").touch()
    (office / "EXCEL.EXE").touch()

    monkeypatch.setattr(installer, "get_installer", lambda _name: manifest)
    monkeypatch.setattr(
        "bottles.backend.managers.installer.ManagerUtils.get_bottle_path",
        lambda _config: str(tmp_path),
    )
    desktop_entry = mocker.patch(
        "bottles.backend.managers.installer.ManagerUtils.create_desktop_entry"
    )

    def update_config(config, key, value, scope=None):
        if scope == "External_Programs":
            config.External_Programs[key] = value
        else:
            setattr(config, key, value)

    manager.update_config.side_effect = update_config

    result = installer.install(config, ("office",), lambda: None)

    assert result.status is True
    assert {program["name"] for program in config.External_Programs.values()} == {
        "Microsoft Word",
        "Microsoft Excel",
    }
    assert desktop_entry.call_count == 2


def test_installer_skips_missing_optional_programs(mocker, monkeypatch, tmp_path):
    manager = mocker.Mock()
    installer = object.__new__(InstallerManager)
    installer._InstallerManager__manager = manager
    config = BottleConfig(Name="Test", Path=str(tmp_path))
    manifest = {
        "Name": "Office",
        "Executables": [
            {
                "file": "WINWORD.EXE",
                "name": "Microsoft Word",
                "path": "Program Files/Microsoft Office/WINWORD.EXE",
            },
            {
                "file": "MSACCESS.EXE",
                "name": "Microsoft Access",
                "path": "Program Files/Microsoft Office/MSACCESS.EXE",
            },
        ],
    }
    office = tmp_path / "drive_c" / "Program Files" / "Microsoft Office"
    office.mkdir(parents=True)
    (office / "WINWORD.EXE").touch()

    monkeypatch.setattr(installer, "get_installer", lambda _name: manifest)
    monkeypatch.setattr(
        "bottles.backend.managers.installer.ManagerUtils.get_bottle_path",
        lambda _config: str(tmp_path),
    )
    mocker.patch(
        "bottles.backend.managers.installer.ManagerUtils.create_desktop_entry"
    )

    def update_config(config, key, value, scope=None):
        config.External_Programs[key] = value

    manager.update_config.side_effect = update_config

    result = installer.install(config, ("office",), lambda: None)

    assert result.status is True
    assert [program["name"] for program in config.External_Programs.values()] == [
        "Microsoft Word"
    ]


def test_installer_fails_when_all_optional_programs_are_missing(
    mocker, monkeypatch, tmp_path
):
    manager = mocker.Mock()
    installer = object.__new__(InstallerManager)
    installer._InstallerManager__manager = manager
    config = BottleConfig(Name="Test", Path=str(tmp_path))
    manifest = {
        "Name": "Office",
        "Executables": [
            {
                "file": "WINWORD.EXE",
                "name": "Microsoft Word",
                "path": "Program Files/Microsoft Office/WINWORD.EXE",
            }
        ],
    }

    monkeypatch.setattr(installer, "get_installer", lambda _name: manifest)
    monkeypatch.setattr(
        "bottles.backend.managers.installer.ManagerUtils.get_bottle_path",
        lambda _config: str(tmp_path),
    )
    desktop_entry = mocker.patch(
        "bottles.backend.managers.installer.ManagerUtils.create_desktop_entry"
    )

    result = installer.install(config, ("office",), lambda: None)

    assert result.status is False
    assert config.External_Programs == {}
    desktop_entry.assert_not_called()


def test_run_winecommand_waits_and_reports_failure(mocker):
    winecommand = mocker.patch(
        "bottles.backend.managers.installer.WineCommand",
        autospec=True,
    )
    winecommand.return_value.run.return_value = Result(False, message="failed")

    result = InstallerManager._InstallerManager__step_run_winecommand(
        BottleConfig(Name="Test"),
        {
            "commands": [
                {
                    "command": "reg",
                    "arguments": "query HKCU",
                    "minimal": True,
                    "wait": True,
                }
            ]
        },
    )

    assert not result.ok
    winecommand.assert_called_once_with(
        mocker.ANY,
        command="reg",
        arguments="query HKCU",
        minimal=True,
        communicate=True,
    )


def test_run_winecommand_accepts_configured_exit_status(mocker):
    winecommand = mocker.patch(
        "bottles.backend.managers.installer.WineCommand",
        autospec=True,
    )
    winecommand.return_value.returncode = 49
    winecommand.return_value.run.return_value = Result(False, message="failed")

    result = InstallerManager._InstallerManager__step_run_winecommand(
        BottleConfig(Name="Test"),
        {
            "commands": [
                {
                    "command": "sc",
                    "arguments": "create TestService",
                    "wait": True,
                    "success_codes": [0, 49],
                }
            ]
        },
    )

    assert result.ok


@pytest.mark.parametrize(
    ("installed", "expected_calls"),
    [
        (["WINWORD.EXE", "EXCEL.EXE"], 0),
        (["WINWORD.EXE"], 1),
    ],
)
def test_run_winecommand_skips_only_when_all_files_exist(
    mocker, monkeypatch, tmp_path, installed, expected_calls
):
    bottle = tmp_path / "Test"
    office = bottle / "drive_c" / "Program Files" / "Microsoft Office"
    office.mkdir(parents=True)
    for name in installed:
        (office / name).touch()
    monkeypatch.setattr(
        "bottles.backend.managers.installer.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )
    winecommand = mocker.patch(
        "bottles.backend.managers.installer.WineCommand",
        autospec=True,
    )
    winecommand.return_value.run.return_value = Result(True)

    result = InstallerManager._InstallerManager__step_run_winecommand(
        BottleConfig(Name="Test"),
        {
            "commands": [
                {
                    "command": "setup.exe",
                    "wait": True,
                    "skip_if_files_exist": [
                        "Program Files/Microsoft Office/WINWORD.EXE",
                        "Program Files/Microsoft Office/EXCEL.EXE",
                    ],
                }
            ]
        },
    )

    assert result.ok
    assert winecommand.call_count == expected_calls


def test_run_winecommand_does_not_skip_for_paths_outside_drive_c(
    mocker, monkeypatch, tmp_path
):
    bottle = tmp_path / "Test"
    drive_c = bottle / "drive_c"
    drive_c.mkdir(parents=True)
    (bottle / "outside.exe").touch()
    monkeypatch.setattr(
        "bottles.backend.managers.installer.ManagerUtils.get_bottle_path",
        lambda _config: str(bottle),
    )
    winecommand = mocker.patch(
        "bottles.backend.managers.installer.WineCommand",
        autospec=True,
    )
    winecommand.return_value.run.return_value = Result(True)

    result = InstallerManager._InstallerManager__step_run_winecommand(
        BottleConfig(Name="Test"),
        {
            "commands": [
                {
                    "command": "setup.exe",
                    "wait": True,
                    "skip_if_files_exist": ["../outside.exe"],
                }
            ]
        },
    )

    assert result.ok
    winecommand.assert_called_once()


def test_installer_step_reports_failed_executable(mocker):
    manager = mocker.Mock()
    manager.component_manager.download.return_value = True
    installer = object.__new__(InstallerManager)
    installer._InstallerManager__component_manager = manager.component_manager
    executor = mocker.patch(
        "bottles.backend.managers.installer.WineExecutor",
        autospec=True,
    )
    executor.return_value.run.return_value = Result(False, message="failed")

    result = installer._InstallerManager__perform_steps(
        BottleConfig(Name="Test"),
        [
            {
                "action": "install_exe",
                "file_name": "setup.exe",
                "url": "https://example.invalid/setup.exe",
            }
        ],
    )

    assert not result.ok


def test_run_winecommand_reports_activity(mocker):
    winecommand = mocker.patch(
        "bottles.backend.managers.installer.WineCommand",
        autospec=True,
    )
    winecommand.return_value.run.return_value = Result(True)
    activities = []
    logs = []

    result = InstallerManager._InstallerManager__step_run_winecommand(
        BottleConfig(Name="Test"),
        {
            "commands": [
                {
                    "command": "C:/setup.exe",
                    "label": "Microsoft 365 setup",
                    "arguments": "/configure config.xml",
                    "wait": True,
                    "minimal": True,
                }
            ]
        },
        activity_fn=activities.append,
        log_fn=logs.append,
    )

    assert result.ok
    assert activities == ["Microsoft 365 setup", None]
    assert logs == ["Started setup.exe", "Finished setup.exe"]


def test_installer_progress_follows_new_log_entries(mocker, tmp_path):
    bottle = tmp_path / "bottle"
    log_dir = bottle / "drive_c/users/test/AppData/Local/Temp"
    log_dir.mkdir(parents=True)
    log_path = log_dir / "CPAK-test.log"
    log_path.write_text("progress=10\n", encoding="utf-16-le")
    mocker.patch(
        "bottles.backend.managers.installer.ManagerUtils.get_bottle_path",
        return_value=str(bottle),
    )
    config = BottleConfig(Name="Test")
    progress = {
        "path": "users/*/AppData/Local/Temp/CPAK-*.log",
        "encoding": "utf-16-le",
        "pattern": r"progress=([0-9]+)",
    }
    positions = InstallerManager._InstallerManager__progress_positions(
        config, progress
    )
    stop = threading.Event()
    values = []
    lines = []
    watcher = threading.Thread(
        target=InstallerManager._InstallerManager__watch_progress,
        args=(config, progress, positions, stop, values.append, lines.append),
    )
    watcher.start()

    with log_path.open("a", encoding="utf-16-le") as log:
        log.write("progress=40\n")

    stop.set()
    watcher.join(1)

    assert values == [0.4]
    assert lines == ["progress=40"]


def test_run_winecommand_reports_progress_before_returning(mocker, tmp_path):
    bottle = tmp_path / "bottle"
    log_dir = bottle / "drive_c/users/test/AppData/Local/Temp"
    log_dir.mkdir(parents=True)
    log_path = log_dir / "installer.log"
    mocker.patch(
        "bottles.backend.managers.installer.ManagerUtils.get_bottle_path",
        return_value=str(bottle),
    )
    winecommand = mocker.patch(
        "bottles.backend.managers.installer.WineCommand",
        autospec=True,
    )

    def finish_command():
        log_path.write_text("total progress=55\n", encoding="utf-8")
        return Result(True)

    winecommand.return_value.run.side_effect = finish_command
    values = []
    lines = []

    result = InstallerManager._InstallerManager__step_run_winecommand(
        BottleConfig(Name="Test"),
        {
            "commands": [
                {
                    "command": "setup.exe",
                    "wait": True,
                    "progress": {
                        "path": "users/*/AppData/Local/Temp/installer.log",
                        "pattern": r"total progress=([0-9]+)",
                    },
                }
            ]
        },
        progress_fn=values.append,
        log_fn=lines.append,
    )

    assert result.ok
    assert values == [None, 0.55, None]
    assert lines == [
        "Started setup.exe",
        "total progress=55",
        "Finished setup.exe",
    ]
