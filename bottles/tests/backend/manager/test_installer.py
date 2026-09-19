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

    assert result is False
    winecommand.assert_called_once_with(
        mocker.ANY,
        command="reg",
        arguments="query HKCU",
        minimal=True,
        communicate=True,
    )


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

    assert result is False
