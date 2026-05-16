"""Core Manager tests"""

from bottles.backend.managers.manager import Manager
from bottles.backend.utils.connection import ConnectionUtils
from bottles.backend.utils.gsettings_stub import GSettingsStub


def test_manager_is_singleton():
    assert Manager(is_cli=True) is Manager(
        is_cli=True
    ), "Manager should be singleton object"
    assert Manager(is_cli=True) is Manager(
        g_settings=GSettingsStub(), is_cli=True
    ), "Manager should be singleton even with different argument"


def test_manager_default_gsettings_stub():
    assert Manager().settings.get_boolean("anything") is False


def test_manager_cli_skips_connection_check(mocker):
    Manager._instances.pop(Manager, None)

    check_connection = mocker.patch.object(
        ConnectionUtils,
        "check_connection",
        autospec=True,
        return_value=True,
    )

    manager = Manager(is_cli=True)
    check_connection.assert_not_called()

    manager.playtime_tracker.shutdown()
    Manager._instances.pop(Manager, None)
