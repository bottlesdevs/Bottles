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
