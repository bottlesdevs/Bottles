"""Core Manager tests"""

import contextlib

import pytest

from bottles.backend.managers.manager import Manager
from bottles.backend.utils.connection import ConnectionUtils
from bottles.backend.utils.gsettings_stub import GSettingsStub


@pytest.fixture(autouse=True)
def reset_manager_singleton():
    existing = Manager._instances.pop(Manager, None)
    if existing and getattr(existing, "playtime_tracker", None):
        with contextlib.suppress(Exception):
            existing.playtime_tracker.shutdown()

    yield

    existing = Manager._instances.pop(Manager, None)
    if existing and getattr(existing, "playtime_tracker", None):
        with contextlib.suppress(Exception):
            existing.playtime_tracker.shutdown()


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
    check_connection = mocker.patch.object(
        ConnectionUtils,
        "check_connection",
        autospec=True,
        return_value=True,
    )

    Manager(is_cli=True)
    check_connection.assert_not_called()
