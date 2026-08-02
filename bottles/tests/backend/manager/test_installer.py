import pytest

from bottles.backend.managers.installer import InstallerManager
from bottles.backend.models.config import BottleConfig


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
